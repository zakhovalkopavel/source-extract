import { Box, Typography } from '@mui/material';
import { useCallback, useEffect, useRef, useState } from 'react';
import { seClient } from '../../../shared/api/se-client';
import {
  isPointHit,
  type Hit,
  type Point2,
  type ReviewSession,
  type SelectionInfo,
  type ToolMode,
} from '../types';
import { CANVAS_BG, IMAGE_POINT_TOL_PX, type ViewOpacity } from './curveStyles';
import { withDraggedPoint } from './dragPreview';
import { drawSessionView } from './drawView';
import { hitTestView } from './hitTest';
import {
  collectPointsInRect,
  hitToBatchItem,
  isDeletablePointHit,
  marqueeScreenSize,
  multiKey,
  nextMultiSelection,
  type MarqueeBox,
} from './multiSelect';

const DRAG_THRESHOLD_PX = 4;

type Props = {
  session: ReviewSession;
  tool: ToolMode;
  opacity: ViewOpacity;
  onSession: (s: ReviewSession) => void;
  onStatus: (msg: string) => void;
  onSelectionChange?: (info: SelectionInfo) => void;
  /** Keep curve highlight after Save when join/remap shifts the index. */
  externalCurveIndex?: number | null;
  /** Id / notation for Add invariant (from ToolsRail). */
  invariantDraftId?: string;
  /** Select this invariant when chosen from the off-canvas list. */
  focusInvariantId?: string | null;
  /** Highlight this field when chosen from the Fields list. */
  focusFieldName?: string | null;
  /** Register Delete selected / keyboard handler with the parent. */
  onRegisterDelete?: (fn: () => void) => void;
  /** Register Commit seed handler (Enter / ToolsRail button). */
  onRegisterCommitSeed?: (fn: () => void) => void;
  /** Session undo (Ctrl+Z when not peeling a seed waypoint). */
  onUndo?: () => void | Promise<void>;
  /** Field / °C for Seed isotherm (from ToolsRail — no window.prompt). */
  seedField?: string;
  seedTemperatureC?: string;
  /** Live waypoint count for the ToolsRail Commit button. */
  onSeedCount?: (n: number) => void;
};

function isAdditiveModifier(ev: { ctrlKey: boolean; metaKey: boolean; shiftKey: boolean }): boolean {
  return ev.ctrlKey || ev.metaKey || ev.shiftKey;
}

function formatApiError(e: unknown): string {
  const ax = e as { response?: { data?: { detail?: unknown } }; message?: string };
  const detail = ax.response?.data?.detail;
  if (detail == null) return ax.message || String(e);
  if (typeof detail === 'string') return detail;
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

function apiPath(url: string | undefined): string | null {
  if (!url) return null;
  const marker = '/api/v1/';
  const i = url.indexOf(marker);
  if (i >= 0) return url.slice(i + marker.length);
  if (url.startsWith('/review/')) return url.replace(/^\//, '');
  return url.replace(/^\/+/, '');
}

function hitLabel(hit: Hit, components?: string[]): string {
  if (hit.kind === 'boundary' || hit.kind === 'isotherm' || hit.kind === 'liquidus') {
    return `${hit.kind} #${hit.index}${hit.pointIndex != null ? ` pt ${hit.pointIndex}` : ''}`;
  }
  if (hit.kind === 'invariant') return `invariant ${hit.id}`;
  if (hit.kind === 'frame') {
    const name = components?.[hit.index];
    return name ? `triangle corner ${name}` : `triangle corner #${hit.index}`;
  }
  return `node #${hit.index}`;
}

export function ReviewCanvas({
  session,
  tool,
  opacity,
  onSession,
  onStatus,
  onSelectionChange,
  externalCurveIndex = null,
  invariantDraftId = '',
  focusInvariantId = null,
  focusFieldName = null,
  onRegisterDelete,
  onRegisterCommitSeed,
  onUndo,
  seedField = '',
  seedTemperatureC = '1500',
  onSeedCount,
}: Props) {
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [baseImg, setBaseImg] = useState<HTMLImageElement | null>(null);
  const [liveImg, setLiveImg] = useState<HTMLImageElement | null>(null);
  const [refImg, setRefImg] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState(0.4);
  const [offset, setOffset] = useState<Point2>([16, 16]);
  const [selected, setSelected] = useState<Hit | null>(null);
  const [multi, setMulti] = useState<Hit[]>([]);
  const [marquee, setMarquee] = useState<MarqueeBox | null>(null);
  const [seed, setSeed] = useState<Point2[]>([]);
  /** Live image-space position while dragging a vertex / invariant / node. */
  const [dragPt, setDragPt] = useState<Point2 | null>(null);
  const drag = useRef<{ hit: Hit; last: Point2; moved: boolean } | null>(null);
  /** Select-mode: wait for a small pointer move before treating as drag. */
  const dragCandidate = useRef<{ hit: Hit; screen: Point2 } | null>(null);
  const panDrag = useRef<{ last: Point2 } | null>(null);
  const marqueeDrag = useRef<MarqueeBox | null>(null);
  /** Field under a click that may become a marquee — select field only if no drag. */
  const fieldClickCandidate = useRef<string | null>(null);
  const spaceDown = useRef(false);
  const [panning, setPanning] = useState(false);
  const bust = useRef(0);
  const scaleRef = useRef(scale);
  const offsetRef = useRef(offset);
  const multiRef = useRef(multi);
  const selectedRef = useRef(selected);
  const toolRef = useRef(tool);
  const sessionRef = useRef(session);
  const seedFieldRef = useRef(seedField);
  const seedTempRef = useRef(seedTemperatureC);
  scaleRef.current = scale;
  offsetRef.current = offset;
  multiRef.current = multi;
  selectedRef.current = selected;
  toolRef.current = tool;
  sessionRef.current = session;
  seedFieldRef.current = seedField;
  seedTempRef.current = seedTemperatureC;

  const reloadImages = useCallback(() => {
    bust.current += 1;
    const q = `?t=${bust.current}`;
    const gen = bust.current;
    const basePath = apiPath(session.image?.url) || `review/sessions/${session.id}/image`;
    const livePath =
      apiPath(session.image?.liveOverlayUrl) || `review/sessions/${session.id}/overlay.png`;
    const base = new Image();
    base.crossOrigin = 'anonymous';
    // Keep the previous scan on failure — never blank the canvas after a move.
    base.onload = () => {
      if (bust.current === gen) setBaseImg(base);
    };
    base.src = `${seClient.defaults.baseURL}/${basePath}${q}`;
    if (opacity.live > 0) {
      const live = new Image();
      live.crossOrigin = 'anonymous';
      live.onload = () => {
        if (bust.current === gen) setLiveImg(live);
      };
      live.onerror = () => {
        if (bust.current === gen) setLiveImg(null);
      };
      live.src = `${seClient.defaults.baseURL}/${livePath}${q}`;
    } else {
      setLiveImg(null);
    }
    const refPath = apiPath(session.image?.referenceOverlayUrl || undefined);
    if (refPath && opacity.reference > 0) {
      const ref = new Image();
      ref.crossOrigin = 'anonymous';
      ref.onload = () => {
        if (bust.current === gen) setRefImg(ref);
      };
      ref.onerror = () => {
        if (bust.current === gen) setRefImg(null);
      };
      ref.src = `${seClient.defaults.baseURL}/${refPath}${q}`;
    } else {
      setRefImg(null);
    }
  }, [
    session.id,
    session.image?.url,
    session.image?.liveOverlayUrl,
    session.image?.referenceOverlayUrl,
    opacity.reference,
    opacity.live,
  ]);

  // Base scan only when session / URLs change — NOT after every view edit (that
  // raced the save and cleared the background via onerror).
  useEffect(() => {
    reloadImages();
  }, [reloadImages]);

  // Live Pillow overlay (usually opacity 0) — refresh only when the user shows it.
  useEffect(() => {
    if (opacity.live <= 0) return;
    bust.current += 1;
    const q = `?t=${bust.current}`;
    const gen = bust.current;
    const livePath =
      apiPath(session.image?.liveOverlayUrl) || `review/sessions/${session.id}/overlay.png`;
    const live = new Image();
    live.crossOrigin = 'anonymous';
    live.onload = () => {
      if (bust.current === gen) setLiveImg(live);
    };
    live.onerror = () => {
      if (bust.current === gen) setLiveImg(null);
    };
    live.src = `${seClient.defaults.baseURL}/${livePath}${q}`;
  }, [session.view, session.id, session.image?.liveOverlayUrl, opacity.live]);

  const toImage = useCallback(
    (screen: Point2): Point2 => [(screen[0] - offset[0]) / scale, (screen[1] - offset[1]) / scale],
    [offset, scale],
  );

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const w = wrap.clientWidth || 800;
    const h = wrap.clientHeight || 600;
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = CANVAS_BG;
    ctx.fillRect(0, 0, w, h);
    ctx.setTransform(scale, 0, 0, scale, offset[0], offset[1]);
    if (baseImg) ctx.drawImage(baseImg, 0, 0);
    if (liveImg && opacity.live > 0) {
      ctx.globalAlpha = opacity.live;
      ctx.drawImage(liveImg, 0, 0);
      ctx.globalAlpha = 1;
    }
    if (refImg && opacity.reference > 0) {
      const baseOrigin = session.image?.pageOrigin || [0, 0];
      const refOrigin = session.image?.referencePageOrigin || baseOrigin;
      const dx = (refOrigin[0] || 0) - (baseOrigin[0] || 0);
      const dy = (refOrigin[1] || 0) - (baseOrigin[1] || 0);
      ctx.globalAlpha = opacity.reference;
      ctx.drawImage(refImg, dx, dy);
      ctx.globalAlpha = 1;
    }
    const dragHit = drag.current?.hit;
    const view =
      dragHit && dragPt && session.view
        ? withDraggedPoint(session.view, dragHit, dragPt)
        : session.view;
    drawSessionView(ctx, {
      view,
      selected,
      multi,
      marquee,
      scale,
      showHandles: tool === 'move' || tool === 'add' || tool === 'delete' || tool === 'select',
      seedWaypoints: seed,
      opacity,
      selectedField,
    });
    if (dragPt) {
      ctx.fillStyle = '#fff';
      ctx.strokeStyle = '#111';
      ctx.lineWidth = 1.5 / scale;
      ctx.beginPath();
      ctx.arc(dragPt[0], dragPt[1], 5.5 / scale, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }
  }, [
    baseImg,
    liveImg,
    refImg,
    offset,
    scale,
    session.view,
    session.image?.pageOrigin,
    session.image?.referencePageOrigin,
    selected,
    multi,
    marquee,
    tool,
    seed,
    opacity,
    dragPt,
    selectedField,
  ]);

  useEffect(() => {
    draw();
  }, [draw]);

  const mutate = useCallback(
    async (path: string, body?: unknown) => {
      const res = await seClient.post(
        `/review/sessions/${sessionRef.current.id}${path}`,
        body ?? {},
      );
      const next = res.data as ReviewSession;
      onSession(next);
      return next;
    },
    [onSession],
  );

  const deletePointRefs = useCallback(
    async (hits: Hit[]) => {
      const items = hits.map(hitToBatchItem).filter((x): x is NonNullable<typeof x> => x != null);
      if (!items.length) return;
      await mutate('/points/delete-batch', { items });
      setMulti([]);
      setSelected(null);
    },
    [mutate],
  );

  const confirmDeleteSelection = useCallback(async () => {
    const hits = multiRef.current;
    const sel = selectedRef.current;
    // Prefer multi point selection (nodes / invariants / vertices)
    if (hits.length) {
      const n = hits.length;
      await deletePointRefs(hits);
      onStatus(`Deleted ${n} selected point(s)`);
      return;
    }
    // Single selected point (invariant / node / vertex) without multi
    if (sel && isDeletablePointHit(sel)) {
      await deletePointRefs([sel]);
      onStatus(`Deleted ${hitLabel(sel)}`);
      return;
    }
    // Whole curve
    if (sel && (sel.kind === 'boundary' || sel.kind === 'isotherm')) {
      if (sel.kind === 'boundary') {
        await mutate('/boundaries/delete', { contourIndex: sel.index });
      } else {
        await mutate('/isotherms/delete', { contourIndex: sel.index });
      }
      setSelected(null);
      setMulti([]);
      onStatus(`Deleted ${sel.kind} #${sel.index}`);
      return;
    }
    onStatus('Nothing selected to delete');
  }, [deletePointRefs, mutate, onStatus]);

  const confirmDeleteSelectionRef = useRef(confirmDeleteSelection);
  confirmDeleteSelectionRef.current = confirmDeleteSelection;
  const onStatusRef = useRef(onStatus);
  onStatusRef.current = onStatus;

  useEffect(() => {
    // Whole-curve selection only — a vertex hit must not look like "curve selected".
    const curve =
      selected &&
      (selected.kind === 'boundary' || selected.kind === 'isotherm') &&
      selected.pointIndex == null
        ? { kind: selected.kind, index: selected.index }
        : null;
    const invId = selected?.kind === 'invariant' ? selected.id : null;
    // Only report a field when it is the active selection (avoids sticky highlight flicker).
    const fieldName = selected?.kind === 'field' ? selected.name : null;
    const canDelete =
      multi.length > 0 ||
      !!curve ||
      !!invId ||
      isDeletablePointHit(selected);
    onSelectionChange?.({
      pointCount: multi.length,
      curve,
      canDelete,
      invariantId: invId,
      fieldName,
    });
  }, [multi, selected, onSelectionChange]);

  useEffect(() => {
    if (externalCurveIndex == null || !selected) return;
    if (selected.kind !== 'boundary' && selected.kind !== 'isotherm') return;
    if (selected.index === externalCurveIndex) return;
    setSelected({ kind: selected.kind, index: externalCurveIndex });
  }, [externalCurveIndex, selected]);

  useEffect(() => {
    if (!focusInvariantId) return;
    setSelected((prev) =>
      prev?.kind === 'invariant' && prev.id === focusInvariantId
        ? prev
        : { kind: 'invariant', id: focusInvariantId },
    );
    setMulti([{ kind: 'invariant', id: focusInvariantId }]);
    setSelectedField(null);
  }, [focusInvariantId]);

  useEffect(() => {
    if (!focusFieldName) {
      setSelected((prev) => (prev?.kind === 'field' ? null : prev));
      setSelectedField(null);
      return;
    }
    setSelected((prev) =>
      prev?.kind === 'field' && prev.name === focusFieldName
        ? prev
        : { kind: 'field', name: focusFieldName },
    );
    setSelectedField(focusFieldName);
    setMulti([]);
  }, [focusFieldName]);

  useEffect(() => {
    onRegisterDelete?.(() => {
      void confirmDeleteSelectionRef.current().catch((e) =>
        onStatusRef.current(formatApiError(e)),
      );
    });
  }, [onRegisterDelete]);

  useEffect(() => {
    onSeedCount?.(seed.length);
  }, [seed.length, onSeedCount]);

  useEffect(() => {
    if (tool !== 'seed-boundary' && tool !== 'seed-isotherm' && seed.length) {
      setSeed([]);
    }
  }, [tool, seed.length]);

  const commitSeedRef = useRef<() => Promise<void>>(async () => {});
  const onUndoRef = useRef(onUndo);
  onUndoRef.current = onUndo;
  const seedRef = useRef(seed);
  seedRef.current = seed;

  useEffect(() => {
    onRegisterCommitSeed?.(() => {
      void commitSeedRef.current().catch((e) => onStatusRef.current(formatApiError(e)));
    });
  }, [onRegisterCommitSeed]);

  useEffect(() => {
    const onKeyDown = (ev: KeyboardEvent) => {
      if (ev.code === 'Space' && !ev.repeat) {
        ev.preventDefault();
        spaceDown.current = true;
        setPanning(true);
        return;
      }
      const tag = (ev.target as HTMLElement | null)?.tagName;
      const inField =
        tag === 'INPUT' || tag === 'TEXTAREA' || (ev.target as HTMLElement)?.isContentEditable;
      if (
        (ev.key === 'Enter' || ev.key === 'NumpadEnter') &&
        !inField &&
        (toolRef.current === 'seed-boundary' || toolRef.current === 'seed-isotherm')
      ) {
        ev.preventDefault();
        void commitSeedRef.current().catch((e) => onStatusRef.current(formatApiError(e)));
        return;
      }
      // Ctrl/⌘+Z — peel last seed waypoint while seeding; otherwise session undo.
      if (
        (ev.key === 'z' || ev.key === 'Z') &&
        (ev.ctrlKey || ev.metaKey) &&
        !ev.shiftKey &&
        !ev.altKey
      ) {
        if (inField) return;
        ev.preventDefault();
        const seeding =
          toolRef.current === 'seed-boundary' || toolRef.current === 'seed-isotherm';
        if (seeding && seedRef.current.length > 0) {
          setSeed((s) => s.slice(0, -1));
          onStatusRef.current(
            seedRef.current.length <= 1
              ? 'Cleared last seed waypoint'
              : `Removed last seed waypoint (${seedRef.current.length - 1} left)`,
          );
          return;
        }
        void Promise.resolve(onUndoRef.current?.())
          .then(() => onStatusRef.current('Undo'))
          .catch((e) => onStatusRef.current(formatApiError(e)));
        return;
      }
      if (ev.key !== 'Delete' && ev.key !== 'Backspace') return;
      if (inField) return;
      ev.preventDefault();
      void confirmDeleteSelectionRef.current().catch((e) =>
        onStatusRef.current(formatApiError(e)),
      );
    };
    const onKeyUp = (ev: KeyboardEvent) => {
      if (ev.code === 'Space') {
        spaceDown.current = false;
        if (!panDrag.current) setPanning(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheelNative = (ev: WheelEvent) => {
      ev.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      const curScale = scaleRef.current;
      const [ox, oy] = offsetRef.current;
      const factor = ev.deltaY < 0 ? 1.1 : 0.9;
      const next = Math.min(5, Math.max(0.08, curScale * factor));
      const imgX = (mx - ox) / curScale;
      const imgY = (my - oy) / curScale;
      setScale(next);
      setOffset([mx - imgX * next, my - imgY * next]);
    };
    canvas.addEventListener('wheel', onWheelNative, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheelNative);
  }, []);

  async function persistMove(hit: Hit, imgPt: Point2) {
    if (!isPointHit(hit)) return;
    const pixel = { x: imgPt[0], y: imgPt[1] };
    if ((hit.kind === 'boundary' || hit.kind === 'isotherm') && hit.pointIndex != null) {
      await mutate('/points/move', {
        contourKind: hit.kind,
        contourIndex: hit.index,
        pointIndex: hit.pointIndex,
        pixel,
      });
    } else if (hit.kind === 'invariant') {
      await mutate('/invariants/move', { pointId: hit.id, pixel });
    } else if (hit.kind === 'node') {
      await mutate('/nodes/move', { nodeIndex: hit.index, pixel });
    } else if (hit.kind === 'frame') {
      await mutate('/calibration/corners/move', {
        componentIndex: hit.index,
        pixel,
      });
    }
  }

  function beginPan(ev: React.PointerEvent, screen: Point2) {
    panDrag.current = { last: screen };
    setPanning(true);
    (ev.target as HTMLElement).setPointerCapture(ev.pointerId);
  }

  function beginMarquee(ev: React.PointerEvent, imgPt: Point2, additive: boolean) {
    if (!additive) setMulti([]);
    const box = { x0: imgPt[0], y0: imgPt[1], x1: imgPt[0], y1: imgPt[1] };
    marqueeDrag.current = box;
    setMarquee(box);
    (ev.target as HTMLElement).setPointerCapture(ev.pointerId);
  }

  function onPointerDown(ev: React.PointerEvent) {
    if (ev.button !== 0 && ev.button !== 1) return;
    ev.preventDefault();
    const rect = canvasRef.current!.getBoundingClientRect();
    const screen: Point2 = [ev.clientX - rect.left, ev.clientY - rect.top];
    // Ctrl/⌘/Shift = append to multi-select. Pan: middle / Space / Alt.
    const wantPan = ev.button === 1 || spaceDown.current || ev.altKey;
    if (wantPan) {
      beginPan(ev, screen);
      return;
    }

    const imgPt = toImage(screen);
    // Tolerances are image pixels (screen ≈ IMAGE_POINT_TOL_PX * scale).
    // Select/delete: slightly tighter points so curve-body clicks win.
    // Move/add: full snap radius so nearby shared vertices are easy to grab.
    const pointTol =
      tool === 'select' || tool === 'delete'
        ? IMAGE_POINT_TOL_PX
        : IMAGE_POINT_TOL_PX * 1.5;
    const curveTol = Math.max(IMAGE_POINT_TOL_PX * 2, 8);
    const hit = hitTestView(session.view, imgPt, curveTol, { pointTol });
    const additive = isAdditiveModifier(ev);

    if (tool === 'select' || tool === 'delete') {
      if (hit?.kind === 'frame') {
        fieldClickCandidate.current = null;
        setSelected(hit);
        if (!additive) setMulti([]);
        if (tool === 'select') {
          dragCandidate.current = { hit, screen };
          (ev.target as HTMLElement).setPointerCapture(ev.pointerId);
          onStatus(
            `Selected ${hitLabel(hit, session.view?.components)} — drag to move calibration`,
          );
        } else {
          onStatus('Calibration corners cannot be deleted — drag in Select/Move to relocate');
        }
        return;
      }
      if (isDeletablePointHit(hit)) {
        fieldClickCandidate.current = null;
        // C# compound rings → promote into draft invariants so they edit like I#.
        if (
          hit?.kind === 'node' &&
          tool === 'select' &&
          !additive &&
          (session.view?.nodes || []).find((n) => (n.nodeIndex ?? n.index) === hit.index)
            ?.kind === 'ring'
        ) {
          void mutate('/nodes/ensure-invariant', { nodeIndex: hit.index })
            .then((next) => {
              const ensured = next.lastNodeEnsure;
              const id = ensured?.id;
              if (!id) {
                setSelected(hit);
                onStatus(`Selected ${hitLabel(hit)}`);
                return;
              }
              setSelected({ kind: 'invariant', id });
              setMulti([{ kind: 'invariant', id }]);
              setSelectedField(null);
              onSelectionChange?.({
                pointCount: 1,
                curve: null,
                canDelete: true,
                invariantId: id,
                fieldName: null,
              });
              const role = ensured?.pointRole === 'compound' ? 'compound' : 'invariant';
              onStatus(
                ensured?.created
                  ? `Opened ${role} ${id} from ring — set name / °C and Save`
                  : `Selected ${role} ${id}`,
              );
            })
            .catch((e) => onStatus(formatApiError(e)));
          return;
        }
        const next = nextMultiSelection(multi, hit!, additive);
        setMulti(next);
        setSelected(hit);
        setSelectedField(null);
        if (tool === 'delete' && !additive) {
          void deletePointRefs([hit!])
            .then(() => onStatus(`Deleted ${hitLabel(hit!)}`))
            .catch((e) => onStatus(String(e)));
          return;
        }
        // Select: allow drag-to-move after a small pointer threshold
        if (tool === 'select' && !additive) {
          dragCandidate.current = { hit: hit!, screen };
          (ev.target as HTMLElement).setPointerCapture(ev.pointerId);
        }
        onStatus(
          next.length > 1
            ? `Selected ${next.length} point(s) — Delete/Backspace to remove`
            : `Selected ${hitLabel(hit!)} — drag to move, Ctrl+click to add`,
        );
        return;
      }

      if (hit && (hit.kind === 'boundary' || hit.kind === 'isotherm' || hit.kind === 'liquidus')) {
        fieldClickCandidate.current = null;
        const already =
          selected?.kind === hit.kind &&
          selected.index === hit.index &&
          hit.pointIndex == null;
        if (tool === 'delete' && already && hit.pointIndex == null) {
          void (async () => {
            try {
              if (hit.kind === 'boundary') {
                await mutate('/boundaries/delete', { contourIndex: hit.index });
              } else if (hit.kind === 'isotherm') {
                await mutate('/isotherms/delete', { contourIndex: hit.index });
              }
              setSelected(null);
              setMulti([]);
              onStatus(`Deleted ${hit.kind} #${hit.index}`);
            } catch (e) {
              onStatus(String(e));
            }
          })();
          return;
        }
        setSelected(hit);
        setSelectedField(null);
        if (!additive) setMulti([]);
        onStatus(
          tool === 'delete'
            ? `Selected ${hitLabel(hit)} — click again to delete curve`
            : `Selected ${hitLabel(hit)} — drag a handle to move`,
        );
        return;
      }

      if (hit?.kind === 'field') {
        // Field fills cover the triangle — don't steal marquee / multi-select.
        // Click (no drag) selects the field; drag selects points inside it.
        fieldClickCandidate.current = hit.name;
        beginMarquee(ev, imgPt, additive);
        onStatus(
          additive
            ? 'Drag to add points — click (no drag) selects the field'
            : 'Drag to select points — Ctrl+click/drag to add, click selects the field',
        );
        return;
      }

      // Empty space → marquee (not pan) in select/delete
      fieldClickCandidate.current = null;
      beginMarquee(ev, imgPt, additive);
      onStatus('Drag to select points — Ctrl+click to add, Space/Alt/middle-drag to pan');
      return;
    }

    // Add point: uses the already-selected curve (click does not need to re-hit it).
    if (tool === 'add') {
      const target =
        selected &&
        (selected.kind === 'boundary' || selected.kind === 'isotherm')
          ? selected
          : hit && (hit.kind === 'boundary' || hit.kind === 'isotherm')
            ? hit
            : null;
      if (!target) {
        onStatus('Select an isotherm or boundary first, then Add point');
        return;
      }
      const kind = target.kind as 'boundary' | 'isotherm';
      const index = target.index;
      setSelected({ kind, index });

      // Click a vertex of another same-kind curve → join into one.
      if (
        hit &&
        hit.kind === kind &&
        hit.index !== index &&
        hit.pointIndex != null
      ) {
        void mutate('/points/join', {
          contourKind: kind,
          keepIndex: index,
          otherIndex: hit.index,
          otherPointIndex: hit.pointIndex,
          pixel: { x: imgPt[0], y: imgPt[1] },
        })
          .then((next) => {
            const joined = next.lastContourJoin;
            const keep = joined?.index ?? index;
            setSelected({ kind, index: keep });
            onStatus(`Joined ${kind} #${hit.index} into #${keep} — Undo available`);
          })
          .catch((e) => onStatus(formatApiError(e)));
        return;
      }

      // Snap to an existing point (invariant / node / frame / same-curve vertex).
      let px = imgPt[0];
      let py = imgPt[1];
      let snapNote = '';
      if (hit?.kind === 'invariant') {
        const inv = (session.view?.invariants || session.view?.points || []).find(
          (p) => p.id === hit.id,
        );
        if (inv?.pixel && inv.pixel.length >= 2) {
          px = Number(inv.pixel[0]);
          py = Number(inv.pixel[1]);
          snapNote = ` (snapped to ${inv.label || inv.id})`;
        }
      } else if (hit?.kind === 'node') {
        const node = (session.view?.nodes || []).find(
          (n) => (n.nodeIndex ?? n.index) === hit.index,
        );
        if (node?.pixel && node.pixel.length >= 2) {
          px = Number(node.pixel[0]);
          py = Number(node.pixel[1]);
          snapNote = ` (snapped to ${node.label || `node #${hit.index}`})`;
        }
      } else if (hit?.kind === 'frame') {
        const c = session.view?.cornersImage?.[hit.index];
        if (c && c.length >= 2) {
          px = Number(c[0]);
          py = Number(c[1]);
          snapNote = ` (snapped to triangle corner)`;
        }
      } else if (
        hit &&
        (hit.kind === 'boundary' || hit.kind === 'isotherm') &&
        hit.pointIndex != null
      ) {
        const curve =
          hit.kind === 'isotherm'
            ? session.view?.isotherms?.find((c) => c.index === hit.index)
            : session.view?.boundaries?.find((c) => c.index === hit.index);
        const pts =
          hit.kind === 'isotherm'
            ? curve?.controls || curve?.pixels
            : curve?.pixels;
        const p = pts?.[hit.pointIndex];
        if (p && p.length >= 2) {
          px = Number(p[0]);
          py = Number(p[1]);
          snapNote = ' (snapped to existing vertex)';
        }
      }

      void mutate('/points/add', {
        contourKind: kind,
        contourIndex: index,
        pixel: { x: px, y: py },
      })
        .then(() => {
          setSelected({ kind, index });
          onStatus(`Added point on ${kind} #${index}${snapNote} — Undo available`);
        })
        .catch((e) => onStatus(formatApiError(e)));
      return;
    }

    setSelected(hit);

    if (tool === 'move') {
      if (isPointHit(hit)) {
        drag.current = { hit: hit!, last: imgPt, moved: false };
        setDragPt(imgPt);
        (ev.target as HTMLElement).setPointerCapture(ev.pointerId);
        onStatus(`Moving ${hitLabel(hit!)}`);
        return;
      }
      if (hit && (hit.kind === 'boundary' || hit.kind === 'isotherm' || hit.kind === 'liquidus')) {
        onStatus(`Selected ${hitLabel(hit)} — drag a handle to move vertices`);
        return;
      }
      beginPan(ev, screen);
      onStatus('Panning — drop on a handle / point to move it');
      return;
    }

    if (tool === 'seed-boundary' || tool === 'seed-isotherm') {
      setSeed((s) => [...s, imgPt]);
      return;
    }
    if (tool === 'add-invariant') {
      const id = invariantDraftId.trim();
      if (!id) {
        onStatus('Enter invariant id / notation (e.g. A3S2) in the Tools panel first');
        return;
      }
      void mutate('/invariants', {
        pointId: id,
        pixel: { x: imgPt[0], y: imgPt[1] },
      })
        .then((next) => {
          setSelected({ kind: 'invariant', id });
          setMulti([{ kind: 'invariant', id }]);
          const look = next.lastInvariantLookup;
          if (look?.resolved && look.temperature_C != null) {
            onStatus(
              `Placed ${id} → ${look.compoundId || look.notation} @ ${look.temperature_C}°C`,
            );
          } else if (look?.resolved) {
            onStatus(`Placed ${id} → ${look.compoundId || 'compound'} (no melting °C in compounds.json)`);
          } else {
            onStatus(`Placed ${id} (no compounds.json match — set °C manually if needed)`);
          }
        })
        .catch((e) => onStatus(String(e)));
      return;
    }
    if (tool === 'arrows' && hit?.kind === 'boundary') {
      void mutate('/arrows/cycle', {
        contourIndex: hit.index,
        segmentIndex: Math.max(0, hit.pointIndex ?? 0),
      }).catch((e) => onStatus(String(e)));
      return;
    }
    if (!hit) beginPan(ev, screen);
  }

  function onPointerMove(ev: React.PointerEvent) {
    const rect = canvasRef.current!.getBoundingClientRect();
    const screen: Point2 = [ev.clientX - rect.left, ev.clientY - rect.top];
    if (panDrag.current) {
      const [lx, ly] = panDrag.current.last;
      setOffset(([ox, oy]) => [ox + (screen[0] - lx), oy + (screen[1] - ly)]);
      panDrag.current = { last: screen };
      return;
    }
    if (marqueeDrag.current) {
      const imgPt = toImage(screen);
      const box = {
        ...marqueeDrag.current,
        x1: imgPt[0],
        y1: imgPt[1],
      };
      marqueeDrag.current = box;
      setMarquee(box);
      return;
    }
    // Select: promote click → drag once the pointer moves enough
    if (dragCandidate.current && !drag.current) {
      const [sx, sy] = dragCandidate.current.screen;
      if (Math.hypot(screen[0] - sx, screen[1] - sy) >= DRAG_THRESHOLD_PX) {
        const imgPt = toImage(screen);
        drag.current = { hit: dragCandidate.current.hit, last: imgPt, moved: true };
        dragCandidate.current = null;
        setDragPt(imgPt);
        onStatus(`Moving ${hitLabel(drag.current.hit)}`);
      }
      return;
    }
    if (!drag.current) return;
    const imgPt = toImage(screen);
    drag.current = { ...drag.current, last: imgPt, moved: true };
    setDragPt(imgPt);
  }

  async function onPointerUp(ev: React.PointerEvent) {
    if (panDrag.current) {
      panDrag.current = null;
      if (!spaceDown.current) setPanning(false);
      try {
        (ev.target as HTMLElement).releasePointerCapture(ev.pointerId);
      } catch {
        /* not captured */
      }
      return;
    }
    if (marqueeDrag.current) {
      const box = marqueeDrag.current;
      marqueeDrag.current = null;
      setMarquee(null);
      try {
        (ev.target as HTMLElement).releasePointerCapture(ev.pointerId);
      } catch {
        /* not captured */
      }
      const [sw, sh] = marqueeScreenSize(box, scaleRef.current);
      const fieldName = fieldClickCandidate.current;
      fieldClickCandidate.current = null;
      const additiveUp = isAdditiveModifier(ev);
      if (sw < 6 && sh < 6) {
        // Click without drag on a field → select that field (list click still works too).
        if (
          fieldName &&
          !additiveUp &&
          (toolRef.current === 'select' || toolRef.current === 'delete')
        ) {
          setMulti([]);
          setSelected({ kind: 'field', name: fieldName });
          setSelectedField(fieldName);
          onSelectionChange?.({
            pointCount: 0,
            curve: null,
            canDelete: false,
            invariantId: null,
            fieldName,
          });
          onStatus(`Selected field ${fieldName}`);
          return;
        }
        if (!additiveUp && (toolRef.current === 'select' || toolRef.current === 'delete')) {
          setMulti([]);
          setSelected(null);
          setSelectedField(null);
        }
        return;
      }
      const refs = collectPointsInRect(
        sessionRef.current.view,
        box.x0,
        box.y0,
        box.x1,
        box.y1,
        selectedRef.current,
      );
      setMulti((prev) => {
        if (!additiveUp) return refs;
        const seen = new Set(prev.map(multiKey));
        const merged = [...prev];
        for (const r of refs) {
          const k = multiKey(r);
          if (seen.has(k)) continue;
          seen.add(k);
          merged.push(r);
        }
        return merged;
      });
      setSelected(null);
      setSelectedField(null);
      onStatus(
        refs.length
          ? `Selected ${refs.length} point(s) — Delete/Backspace to remove`
          : 'No points in rectangle',
      );
      return;
    }
    dragCandidate.current = null;
    if (!drag.current) return;
    const { hit, last, moved } = drag.current;
    drag.current = null;
    setDragPt(null);
    try {
      (ev.target as HTMLElement).releasePointerCapture(ev.pointerId);
    } catch {
      /* not captured */
    }
    if (!moved) return;
    try {
      await persistMove(hit, last);
      onStatus(`Moved ${hitLabel(hit)}`);
    } catch (e) {
      onStatus(String(e));
    }
  }

  const commitSeed = useCallback(async () => {
    const waypoints = seed;
    const mode = toolRef.current;
    if (mode !== 'seed-boundary' && mode !== 'seed-isotherm') return;
    if (waypoints.length < 2) {
      onStatus('Need ≥2 seed waypoints — click the diagram, then Commit / Enter');
      return;
    }
    try {
      if (mode === 'seed-boundary') {
        await mutate('/boundaries', {
          waypoints: waypoints.map(([x, y]) => ({ x, y })),
        });
        setSeed([]);
        // Commit = finished — deselect so the next seed can start immediately.
        setSelected(null);
        setMulti([]);
        setSelectedField(null);
        onSelectionChange?.({
          pointCount: 0,
          curve: null,
          canDelete: false,
          invariantId: null,
          fieldName: null,
        });
        onStatus(`Seeded boundary (${waypoints.length} waypoints) — Undo available`);
        return;
      }
      const field =
        seedFieldRef.current.trim() ||
        sessionRef.current.phases?.[0] ||
        '';
      const t = Number(seedTempRef.current);
      if (!Number.isFinite(t)) {
        onStatus('Set a valid Temperature °C in the Tools panel before committing');
        return;
      }
      if (!field) {
        onStatus('Set Field name in the Tools panel before committing');
        return;
      }
      const next = await mutate('/isotherms', {
        field,
        temperature_C: t,
        waypoints: waypoints.map(([x, y]) => ({ x, y })),
      });
      setSeed([]);
      const build = next.lastIsothermBuild;
      const idx = build?.index;
      const removed = build?.removedCount || 0;
      setSelected(null);
      setMulti([]);
      setSelectedField(null);
      onSelectionChange?.({
        pointCount: 0,
        curve: null,
        canDelete: false,
        invariantId: null,
        fieldName: null,
      });
      onStatus(
        `Saved isotherm ${field} @ ${t}°C` +
          (idx != null ? ` (#${idx})` : '') +
          (removed > 0 ? ` — removed ${removed} crossed` : '') +
          ' — click it later to edit',
      );
    } catch (e) {
      onStatus(`Seed failed: ${formatApiError(e)}`);
    }
  }, [seed, mutate, onStatus, onSelectionChange]);

  commitSeedRef.current = commitSeed;

  function onDoubleClick() {
    if (tool === 'seed-boundary' || tool === 'seed-isotherm') void commitSeed();
  }

  if (!session.view) {
    return <Typography color="warning.main">Session has no view payload yet.</Typography>;
  }

  return (
    <Box
      ref={wrapRef}
      sx={{
        flex: 1,
        minHeight: 480,
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        overflow: 'hidden',
        bgcolor: CANVAS_BG,
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
          cursor: panning || spaceDown.current ? 'grab' : 'crosshair',
          touchAction: 'none',
        }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onDoubleClick={onDoubleClick}
      />
    </Box>
  );
}
