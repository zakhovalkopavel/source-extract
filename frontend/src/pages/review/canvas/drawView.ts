import type { Hit, Point2, SessionView } from '../types';
import {
  BOUNDARY_ARROW,
  BOUNDARY_HANDLE,
  BOUNDARY_STROKE,
  BOUNDARY_STROKE_SEL,
  FRAME_CORNER,
  FRAME_STROKE,
  INVARIANT_LABEL,
  INVARIANT_STROKE,
  INVARIANT_STROKE_SEL,
  NODE_COLORS,
  PICK_STROKE,
  SEED_STROKE,
  fieldFillRgba,
  type ViewOpacity,
  isothermMissingTemp,
  isothermStrokeColor,
  uniqueIsothermTemps,
} from './curveStyles';
import { isMultiSelected, type MarqueeBox } from './multiSelect';
import { viewInvariants } from './viewInvariants';

function invariantDisplayName(inv: {
  id: string;
  label?: string | null;
  notation?: string | null;
}): string {
  return String(inv.label || inv.notation || inv.id);
}

function drawHollowMarker(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  r: number,
  stroke: string,
  lineWidth: number,
  selected: boolean,
) {
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  if (selected) {
    ctx.fillStyle = stroke;
    ctx.fill();
  }
  ctx.strokeStyle = stroke;
  ctx.lineWidth = lineWidth;
  ctx.stroke();
}

function drawMarkerLabel(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  name: string,
  temp: number | null | undefined,
  scale: number,
  color: string,
) {
  // Short leader from hollow ring toward the label (atlas-style callout).
  const tipX = x + 6 / scale;
  const tipY = y - 6 / scale;
  const textX = x + 14 / scale;
  const nameY = y - 10 / scale;
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.1 / scale;
  ctx.beginPath();
  ctx.moveTo(tipX, tipY);
  ctx.lineTo(textX - 2 / scale, nameY);
  ctx.stroke();

  ctx.fillStyle = color;
  ctx.font = `600 ${11 / scale}px sans-serif`;
  ctx.fillText(name, textX, nameY);
  if (temp != null && Number.isFinite(Number(temp))) {
    ctx.font = `${10 / scale}px sans-serif`;
    ctx.fillText(`${Number(temp)}°C`, textX, nameY + 12 / scale);
  }
}

/** Sparse handle indices along a dense boundary polyline (diagram-review parity). */
function boundaryHandleIndices(pixelCount: number): number[] {
  if (pixelCount <= 0) return [];
  if (pixelCount <= 14) return [...Array(pixelCount).keys()];
  const idxs = new Set([0, pixelCount - 1]);
  const step = Math.max(1, Math.floor((pixelCount - 1) / 12));
  for (let i = step; i < pixelCount - 1; i += step) idxs.add(i);
  return [...idxs].sort((a, b) => a - b);
}

function drawVertices(
  ctx: CanvasRenderingContext2D,
  pixels: number[][],
  color: string,
  scale: number,
  r = 3,
) {
  ctx.fillStyle = color;
  for (const p of pixels) {
    if (!p || p.length < 2) continue;
    ctx.beginPath();
    ctx.arc(p[0], p[1], r / scale, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawArrows(
  ctx: CanvasRenderingContext2D,
  pixels: number[][],
  arrows: string[],
  color: string,
  scale: number,
) {
  if (pixels.length < 2 || !arrows.length) return;
  ctx.fillStyle = color;
  ctx.strokeStyle = color;
  const nSeg = Math.min(arrows.length, pixels.length - 1);
  for (let i = 0; i < nSeg; i++) {
    const kind = arrows[i];
    if (!kind || kind === '?' || kind === '') continue;
    const a = pixels[i];
    const b = pixels[i + 1];
    const mx = (a[0] + b[0]) / 2;
    const my = (a[1] + b[1]) / 2;
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const len = Math.hypot(dx, dy) || 1;
    const ux = dx / len;
    const uy = dy / len;
    const size = 8 / scale;
    const tip = (forward: boolean) => {
      const s = forward ? 1 : -1;
      const tx = mx + s * ux * size * 0.2;
      const ty = my + s * uy * size * 0.2;
      const px = -uy;
      const py = ux;
      ctx.beginPath();
      ctx.moveTo(tx + s * ux * size, ty + s * uy * size);
      ctx.lineTo(tx + px * size * 0.55, ty + py * size * 0.55);
      ctx.lineTo(tx - px * size * 0.55, ty - py * size * 0.55);
      ctx.closePath();
      ctx.fill();
    };
    if (kind === '>' || kind === '<>') tip(true);
    if (kind === '<' || kind === '<>') tip(false);
  }
}

function strokeCurve(
  ctx: CanvasRenderingContext2D,
  pts: number[][],
  color: string,
  /** Screen-pixel thickness (constant under zoom). */
  screenPx: number,
  dashed: boolean,
  scale: number,
) {
  if (pts.length < 2) return;
  ctx.strokeStyle = color;
  ctx.lineWidth = screenPx / scale;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.setLineDash(dashed ? [6 / scale, 4 / scale] : []);
  ctx.beginPath();
  pts.forEach((p, j) => (j ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])));
  ctx.stroke();
  ctx.setLineDash([]);
}

export function drawSessionView(
  ctx: CanvasRenderingContext2D,
  opts: {
    view?: SessionView;
    selected: Hit | null;
    multi?: Hit[];
    marquee?: MarqueeBox | null;
    scale: number;
    showHandles: boolean;
    seedWaypoints: Point2[];
    opacity: ViewOpacity;
    selectedField?: string | null;
  },
): void {
  const {
    view,
    selected,
    multi = [],
    marquee,
    scale,
    showHandles,
    seedWaypoints,
    opacity,
    selectedField = null,
  } = opts;
  if (!view || opacity.all <= 0) return;

  const curveA = opacity.curves * opacity.all;
  const pointA = opacity.points * opacity.all;
  const nodeA = opacity.nodes * opacity.all;
  const fieldA = (opacity.fields ?? 0) * opacity.all;
  const w = Math.max(0.5, Number(opacity.curveWidth) || 1);
  const pr = Math.max(1, Number(opacity.pointSize) || 3);
  const temps = uniqueIsothermTemps(view.isotherms);

  // Field fills under curves / markers — flat monocolour per phase (no colour swap on select).
  if (fieldA > 0) {
    ctx.save();
    ctx.globalAlpha = 1; // alpha baked into rgba so overlapping phases stay solid hues
    for (const field of view.fields || []) {
      const sel =
        (selected?.kind === 'field' && selected.name === field.name) ||
        (selectedField === field.name && selected?.kind === 'field');
      const fill = fieldFillRgba(field.colorIndex, Math.min(0.85, fieldA * (sel ? 0.95 : 0.85)));
      ctx.fillStyle = fill;
      ctx.strokeStyle = sel ? PICK_STROKE : 'transparent';
      ctx.lineWidth = (sel ? 2.6 : 0) / scale;
      for (const ring of field.polygons || []) {
        if (ring.length < 3) continue;
        ctx.beginPath();
        ring.forEach((p, j) => (j ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])));
        ctx.closePath();
        ctx.fill('evenodd');
        if (sel) ctx.stroke();
      }
      const c = field.centroid;
      if (c && c.length >= 2) {
        ctx.fillStyle = sel ? '#111111' : 'rgba(10,10,10,0.92)';
        ctx.font = `600 ${11 / scale}px sans-serif`;
        ctx.fillText(field.name, c[0], c[1]);
      }
    }
    ctx.restore();
  }

  // Calibration frame (ternary corners / binary empty)
  const corners = view.cornersImage || [];
  if (corners.length >= 2) {
    ctx.globalAlpha = Math.min(1, opacity.all);
    ctx.strokeStyle = FRAME_STROKE;
    ctx.fillStyle = FRAME_CORNER;
    ctx.lineWidth = Math.max(1.2, w * 1.2) / scale;
    ctx.setLineDash([8 / scale, 5 / scale]);
    ctx.beginPath();
    corners.forEach((c, i) => {
      if (!c || c.length < 2) return;
      if (i === 0) ctx.moveTo(c[0], c[1]);
      else ctx.lineTo(c[0], c[1]);
    });
    if (corners.length >= 3) ctx.closePath();
    ctx.stroke();
    ctx.setLineDash([]);
    for (let i = 0; i < corners.length; i++) {
      const c = corners[i];
      if (!c || c.length < 2) continue;
      const frameSel = selected?.kind === 'frame' && selected.index === i;
      ctx.beginPath();
      ctx.arc(c[0], c[1], ((frameSel ? pr * 1.55 : pr * 1.25)) / scale, 0, Math.PI * 2);
      ctx.fillStyle = frameSel ? PICK_STROKE : FRAME_CORNER;
      ctx.fill();
      ctx.strokeStyle = frameSel ? '#fff' : '#111';
      ctx.lineWidth = (frameSel ? 2 : 1) / scale;
      ctx.stroke();
      ctx.fillStyle = frameSel ? PICK_STROKE : '#111';
      ctx.font = `${11 / scale}px sans-serif`;
      const label = view.components?.[i] || `C${i}`;
      ctx.fillText(label, c[0] + 6 / scale, c[1] - 6 / scale);
      ctx.fillStyle = FRAME_CORNER;
    }
  }

  for (const br of view.liquidus || []) {
    if (!br.pixels || br.pixels.length < 2) continue;
    const sel =
      selected?.kind === 'liquidus' &&
      selected.index === br.index &&
      selected.pointIndex == null;
    ctx.globalAlpha = curveA;
    strokeCurve(
      ctx,
      br.pixels,
      sel ? BOUNDARY_STROKE_SEL : BOUNDARY_STROKE,
      w * (sel ? 1.5 : 1),
      false,
      scale,
    );
  }

  for (const b of view.boundaries || []) {
    const pts = b.pixels || [];
    if (pts.length < 2) continue;
    const curveSel =
      selected?.kind === 'boundary' &&
      selected.index === b.index &&
      selected.pointIndex == null;
    const hasPointOnCurve =
      (selected?.kind === 'boundary' &&
        selected.index === b.index &&
        selected.pointIndex != null) ||
      multi.some((m) => m.kind === 'boundary' && m.index === b.index && m.pointIndex != null);
    const boundaryActive = curveSel || hasPointOnCurve;
    ctx.globalAlpha = curveA;
    strokeCurve(
      ctx,
      pts,
      boundaryActive ? BOUNDARY_STROKE_SEL : BOUNDARY_STROKE,
      w * (boundaryActive ? 2.1 : 1),
      !!b.dashed,
      scale,
    );
    if (b.arrows?.length) {
      drawArrows(
        ctx,
        pts,
        b.arrows,
        boundaryActive ? BOUNDARY_STROKE_SEL : BOUNDARY_ARROW,
        scale,
      );
    }
    // Sparse handles only — never paint every dense polyline vertex (that twinkles).
    if (showHandles || boundaryActive) {
      ctx.globalAlpha = pointA;
      const idxs = boundaryHandleIndices(pts.length);
      for (const j of idxs) {
        const pt = pts[j];
        if (!pt) continue;
        const pointHit: Hit = { kind: 'boundary', index: b.index, pointIndex: j };
        const pointSel =
          (selected?.kind === 'boundary' &&
            selected.index === b.index &&
            selected.pointIndex === j) ||
          isMultiSelected(multi, pointHit);
        drawVertices(
          ctx,
          [pt],
          pointSel ? PICK_STROKE : BOUNDARY_HANDLE,
          scale,
          pointSel ? pr * 1.15 : pr,
        );
      }
    }
  }

  for (const iso of view.isotherms || []) {
    const pts = iso.pixels || [];
    if (pts.length < 2) continue;
    const curveSel =
      selected?.kind === 'isotherm' &&
      selected.index === iso.index &&
      selected.pointIndex == null;
    const hasPointOnCurve =
      (selected?.kind === 'isotherm' &&
        selected.index === iso.index &&
        selected.pointIndex != null) ||
      multi.some((m) => m.kind === 'isotherm' && m.index === iso.index && m.pointIndex != null);
    const isoActive = curveSel || hasPointOnCurve;
    const stroke = isothermStrokeColor(iso, isoActive, temps);
    ctx.globalAlpha = Math.min(1, curveA + (isoActive ? 0.2 : 0));
    strokeCurve(ctx, pts, stroke, w * (isoActive ? 1.85 : 0.9), !!iso.dashed, scale);
    // Controls are sparse waypoints — never fall back to dense pixels
    if ((showHandles || isoActive) && (iso.controls?.length || 0) > 0) {
      ctx.globalAlpha = pointA;
      iso.controls!.forEach((pt, j) => {
        if (!pt) return;
        const pointHit: Hit = { kind: 'isotherm', index: iso.index, pointIndex: j };
        const pointSel =
          (selected?.kind === 'isotherm' &&
            selected.index === iso.index &&
            selected.pointIndex === j) ||
          isMultiSelected(multi, pointHit);
        drawVertices(
          ctx,
          [pt],
          pointSel ? PICK_STROKE : stroke,
          scale,
          pointSel ? pr * 1.1 : pr * 0.9,
        );
      });
    }
    if (iso.temperature_C != null && pts.length > 0) {
      const mid = pts[Math.floor(pts.length / 2)];
      ctx.globalAlpha = pointA;
      ctx.fillStyle = isothermMissingTemp(iso) ? '#e10600' : stroke;
      ctx.font = `${10 / scale}px sans-serif`;
      ctx.fillText(String(iso.temperature_C), mid[0] + 4 / scale, mid[1] - 4 / scale);
    }
  }

  const invariants = viewInvariants(view);
  const invariantIds = new Set(invariants.map((inv) => inv.id));

  for (const inv of invariants) {
    const p = inv.pixel;
    if (!p || p.length < 2) continue;
    const hit: Hit = { kind: 'invariant', id: inv.id };
    const sel =
      (selected?.kind === 'invariant' && selected.id === inv.id) || isMultiSelected(multi, hit);
    ctx.globalAlpha = pointA;
    const stroke = sel ? INVARIANT_STROKE_SEL : INVARIANT_STROKE;
    const r = (sel ? pr * 1.55 : pr * 1.35) / scale;
    drawHollowMarker(ctx, p[0], p[1], r, stroke, (sel ? 2.4 : 2) / scale, sel);
    drawMarkerLabel(
      ctx,
      p[0],
      p[1],
      invariantDisplayName(inv),
      inv.temperature_C,
      scale,
      sel ? INVARIANT_STROKE_SEL : INVARIANT_LABEL,
    );
  }

  for (const node of view.nodes || []) {
    const p = node.pixel;
    const idx = node.nodeIndex ?? node.index;
    if (!p || p.length < 2 || idx == null) continue;
    const kind = node.kind || '';
    // Linked I# / C# nodes duplicate view.invariants — skip so hollow labeled markers win.
    if (kind === 'invariant' || kind === 'ring') {
      const linked = node.invariant || node.id || node.label;
      if (linked && invariantIds.has(String(linked))) continue;
    }
    const hit: Hit = { kind: 'node', index: idx };
    const sel =
      (selected?.kind === 'node' && selected.index === idx) || isMultiSelected(multi, hit);
    ctx.globalAlpha = nodeA;
    if (kind === 'ring') {
      const stroke = sel ? PICK_STROKE : NODE_COLORS.ring;
      const r = (sel ? pr * 1.7 : pr * 1.5) / scale;
      drawHollowMarker(ctx, p[0], p[1], r, stroke, (sel ? 2.2 : 1.8) / scale, sel);
      const name = String(node.label || node.id || `ring-${idx}`);
      drawMarkerLabel(ctx, p[0], p[1], name, null, scale, sel ? PICK_STROKE : INVARIANT_LABEL);
      continue;
    }
    ctx.fillStyle = sel ? PICK_STROKE : NODE_COLORS[kind] || '#cccccc';
    ctx.strokeStyle = sel ? '#fff' : '#111';
    ctx.lineWidth = 1 / scale;
    ctx.beginPath();
    ctx.arc(p[0], p[1], (sel ? pr * 1.2 : pr) / scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }

  if (marquee) {
    const left = Math.min(marquee.x0, marquee.x1);
    const top = Math.min(marquee.y0, marquee.y1);
    const w = Math.abs(marquee.x1 - marquee.x0);
    const h = Math.abs(marquee.y1 - marquee.y0);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = PICK_STROKE;
    ctx.fillStyle = 'rgba(199, 125, 255, 0.12)';
    ctx.lineWidth = 1 / scale;
    ctx.setLineDash([4 / scale, 3 / scale]);
    ctx.fillRect(left, top, w, h);
    ctx.strokeRect(left, top, w, h);
    ctx.setLineDash([]);
  }

  if (seedWaypoints.length) {
    ctx.globalAlpha = 1;
    strokeCurve(
      ctx,
      seedWaypoints.map((p) => [p[0], p[1]]),
      SEED_STROKE,
      w * 1.1,
      true,
      scale,
    );
    drawVertices(
      ctx,
      seedWaypoints.map((p) => [p[0], p[1]]),
      SEED_STROKE,
      scale,
      pr,
    );
  }

  ctx.globalAlpha = 1;
}
