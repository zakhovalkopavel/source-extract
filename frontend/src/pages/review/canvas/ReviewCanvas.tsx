import { Box, Typography } from '@mui/material';
import { useCallback, useEffect, useRef, useState } from 'react';
import { seClient } from '../../../shared/api/se-client';
import { isPointHit, type Hit, type Point2, type ReviewSession, type ToolMode } from '../types';
import { CANVAS_BG, type ViewOpacity } from './curveStyles';
import { drawSessionView } from './drawView';
import { hitTestView } from './hitTest';

type Props = {
  session: ReviewSession;
  tool: ToolMode;
  opacity: ViewOpacity;
  onSession: (s: ReviewSession) => void;
  onStatus: (msg: string) => void;
};

function apiPath(url: string | undefined): string | null {
  if (!url) return null;
  const marker = '/api/v1/';
  const i = url.indexOf(marker);
  if (i >= 0) return url.slice(i + marker.length);
  if (url.startsWith('/review/')) return url.replace(/^\//, '');
  return url.replace(/^\/+/, '');
}

export function ReviewCanvas({ session, tool, opacity, onSession, onStatus }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [baseImg, setBaseImg] = useState<HTMLImageElement | null>(null);
  const [liveImg, setLiveImg] = useState<HTMLImageElement | null>(null);
  const [refImg, setRefImg] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState(0.4);
  const [offset, setOffset] = useState<Point2>([16, 16]);
  const [selected, setSelected] = useState<Hit | null>(null);
  const [seed, setSeed] = useState<Point2[]>([]);
  const drag = useRef<{ hit: Hit; last: Point2 } | null>(null);
  const panDrag = useRef<{ last: Point2 } | null>(null);
  const spaceDown = useRef(false);
  const [panning, setPanning] = useState(false);
  const bust = useRef(0);
  const scaleRef = useRef(scale);
  const offsetRef = useRef(offset);
  scaleRef.current = scale;
  offsetRef.current = offset;

  const reloadImages = useCallback(() => {
    bust.current += 1;
    const q = `?t=${bust.current}`;
    const basePath = apiPath(session.image?.url) || `review/sessions/${session.id}/image`;
    const livePath =
      apiPath(session.image?.liveOverlayUrl) || `review/sessions/${session.id}/overlay.png`;
    const base = new Image();
    base.crossOrigin = 'anonymous';
    base.onload = () => setBaseImg(base);
    base.onerror = () => setBaseImg(null);
    base.src = `${seClient.defaults.baseURL}/${basePath}${q}`;
    const live = new Image();
    live.crossOrigin = 'anonymous';
    live.onload = () => setLiveImg(live);
    live.onerror = () => setLiveImg(null);
    live.src = `${seClient.defaults.baseURL}/${livePath}${q}`;
    const refPath = apiPath(session.image?.referenceOverlayUrl || undefined);
    if (refPath && opacity.reference > 0) {
      const ref = new Image();
      ref.crossOrigin = 'anonymous';
      ref.onload = () => setRefImg(ref);
      ref.onerror = () => setRefImg(null);
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
  ]);

  useEffect(() => {
    reloadImages();
  }, [reloadImages, session.view]);

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
    // Vector overlay on top of (or instead of) live PNG when curves opacity is on
    drawSessionView(ctx, {
      view: session.view,
      selected,
      scale,
      showHandles: tool === 'move' || tool === 'add' || tool === 'delete' || tool === 'select',
      seedWaypoints: seed,
      opacity,
    });
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
    tool,
    seed,
    opacity,
  ]);

  useEffect(() => {
    draw();
  }, [draw]);

  useEffect(() => {
    const onKeyDown = (ev: KeyboardEvent) => {
      if (ev.code === 'Space' && !ev.repeat) {
        ev.preventDefault();
        spaceDown.current = true;
        setPanning(true);
      }
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

  async function mutate(path: string, body?: unknown) {
    const res = await seClient.post(`/review/sessions/${session.id}${path}`, body ?? {});
    onSession(res.data as ReviewSession);
    onStatus('ok');
  }

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
    }
  }

  function beginPan(ev: React.PointerEvent, screen: Point2) {
    panDrag.current = { last: screen };
    setPanning(true);
    (ev.target as HTMLElement).setPointerCapture(ev.pointerId);
  }

  function onPointerDown(ev: React.PointerEvent) {
    if (ev.button !== 0 && ev.button !== 1) return;
    ev.preventDefault();
    const rect = canvasRef.current!.getBoundingClientRect();
    const screen: Point2 = [ev.clientX - rect.left, ev.clientY - rect.top];
    const wantPan = ev.button === 1 || spaceDown.current || ev.altKey || ev.shiftKey;
    if (wantPan) {
      beginPan(ev, screen);
      return;
    }

    const imgPt = toImage(screen);
    // Generous hit radius so curves/points are easy to click (esp. select)
    const hitTol = Math.max(10, 14 / scale);
    const hit = hitTestView(session.view, imgPt, hitTol);
    setSelected(hit);

    if (tool === 'select') {
      if (hit) {
        const label =
          hit.kind === 'boundary' || hit.kind === 'isotherm' || hit.kind === 'liquidus'
            ? `${hit.kind} #${hit.index}${hit.pointIndex != null ? ` pt ${hit.pointIndex}` : ''}`
            : hit.kind === 'invariant'
              ? `invariant ${hit.id}`
              : `node #${hit.index}`;
        onStatus(`Selected ${label}`);
        return;
      }
      beginPan(ev, screen);
      return;
    }

    // Move: drag a point handle; click curve body → select only; empty → pan
    if (tool === 'move') {
      if (isPointHit(hit)) {
        drag.current = { hit: hit!, last: imgPt };
        (ev.target as HTMLElement).setPointerCapture(ev.pointerId);
        return;
      }
      if (hit) {
        onStatus(`Selected ${hit.kind} — use a handle to move`);
        return;
      }
      beginPan(ev, screen);
      onStatus('Panning — drop on a point to move it');
      return;
    }

    if (tool === 'seed-boundary' || tool === 'seed-isotherm') {
      setSeed((s) => [...s, imgPt]);
      return;
    }
    if (tool === 'add-invariant' && !hit) {
      const id = window.prompt('Invariant id');
      if (!id) return;
      void mutate('/invariants', {
        pointId: id,
        pixel: { x: imgPt[0], y: imgPt[1] },
      }).catch((e) => onStatus(String(e)));
      return;
    }
    if (tool === 'delete' && hit) {
      void (async () => {
        try {
          if ((hit.kind === 'boundary' || hit.kind === 'isotherm') && hit.pointIndex != null) {
            await mutate('/points/delete', {
              contourKind: hit.kind,
              contourIndex: hit.index,
              pointIndex: hit.pointIndex,
            });
          } else if (hit.kind === 'boundary') {
            await mutate('/boundaries/delete', { contourIndex: hit.index });
          } else if (hit.kind === 'isotherm') {
            await mutate('/isotherms/delete', { contourIndex: hit.index });
          } else if (hit.kind === 'invariant') {
            await seClient.delete(`/review/sessions/${session.id}/invariants/${encodeURIComponent(hit.id)}`);
            const again = await seClient.get(`/review/sessions/${session.id}`);
            onSession(again.data as ReviewSession);
          }
        } catch (e) {
          onStatus(String(e));
        }
      })();
      return;
    }
    if (tool === 'arrows' && hit?.kind === 'boundary') {
      void mutate('/arrows/cycle', {
        contourIndex: hit.index,
        segmentIndex: Math.max(0, hit.pointIndex ?? 0),
      }).catch((e) => onStatus(String(e)));
      return;
    }
    if (tool === 'add' && hit && (hit.kind === 'boundary' || hit.kind === 'isotherm')) {
      void mutate('/points/add', {
        contourKind: hit.kind,
        contourIndex: hit.index,
        pixel: { x: imgPt[0], y: imgPt[1] },
      }).catch((e) => onStatus(String(e)));
      return;
    }
    // Empty drag on other tools → pan
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
    if (!drag.current) return;
    drag.current = { ...drag.current, last: toImage(screen) };
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
    if (!drag.current) return;
    const { hit, last } = drag.current;
    drag.current = null;
    try {
      (ev.target as HTMLElement).releasePointerCapture(ev.pointerId);
    } catch {
      /* not captured */
    }
    try {
      await persistMove(hit, last);
    } catch (e) {
      onStatus(String(e));
    }
  }

  async function commitSeed() {
    if (seed.length < 2) {
      onStatus('Need ≥2 seed waypoints');
      return;
    }
    try {
      if (tool === 'seed-boundary') {
        await mutate('/boundaries', {
          waypoints: seed.map(([x, y]) => ({ x, y })),
        });
      } else {
        const field = window.prompt('Field name', session.phases?.[0] || '') || '';
        const t = Number(window.prompt('Temperature °C', '1500') || '1500');
        await mutate('/isotherms', {
          field,
          temperature_C: t,
          waypoints: seed.map(([x, y]) => ({ x, y })),
        });
      }
      setSeed([]);
    } catch (e) {
      onStatus(String(e));
    }
  }

  // Expose seed commit via double-click
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
