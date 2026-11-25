import type { Hit, Point2, SessionView } from '../types';
import {
  BOUNDARY_ARROW,
  BOUNDARY_HANDLE,
  BOUNDARY_STROKE,
  BOUNDARY_STROKE_SEL,
  INVARIANT_FILL,
  NODE_COLORS,
  PICK_STROKE,
  SEED_STROKE,
  type ViewOpacity,
  isothermMissingTemp,
  isothermStrokeColor,
  uniqueIsothermTemps,
} from './curveStyles';

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
    scale: number;
    showHandles: boolean;
    seedWaypoints: Point2[];
    opacity: ViewOpacity;
  },
): void {
  const { view, selected, scale, showHandles, seedWaypoints, opacity } = opts;
  if (!view || opacity.all <= 0) return;

  const curveA = opacity.curves * opacity.all;
  const pointA = opacity.points * opacity.all;
  const nodeA = opacity.nodes * opacity.all;
  const w = Math.max(0.5, Number(opacity.curveWidth) || 1);
  const pr = Math.max(1, Number(opacity.pointSize) || 3);
  const temps = uniqueIsothermTemps(view.isotherms);

  for (const br of view.liquidus || []) {
    if (!br.pixels || br.pixels.length < 2) continue;
    const sel = selected?.kind === 'liquidus' && selected.index === br.index;
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
    const sel = selected?.kind === 'boundary' && selected.index === b.index;
    ctx.globalAlpha = curveA;
    strokeCurve(
      ctx,
      pts,
      sel ? BOUNDARY_STROKE_SEL : BOUNDARY_STROKE,
      w * (sel ? 1.5 : 1),
      !!b.dashed,
      scale,
    );
    if (b.arrows?.length) {
      drawArrows(ctx, pts, b.arrows, sel ? BOUNDARY_STROKE_SEL : BOUNDARY_ARROW, scale);
    }
    // Sparse handles only — never paint every dense polyline vertex
    if (showHandles || sel) {
      ctx.globalAlpha = pointA;
      const idxs = sel ? [...pts.keys()] : boundaryHandleIndices(pts.length);
      const handles = idxs.map((i) => pts[i]).filter(Boolean);
      drawVertices(
        ctx,
        handles,
        sel ? BOUNDARY_STROKE_SEL : BOUNDARY_HANDLE,
        scale,
        sel ? pr * 1.15 : pr,
      );
    }
  }

  for (const iso of view.isotherms || []) {
    const pts = iso.pixels || [];
    if (pts.length < 2) continue;
    const sel = selected?.kind === 'isotherm' && selected.index === iso.index;
    const stroke = isothermStrokeColor(iso, sel, temps);
    ctx.globalAlpha = Math.min(1, curveA + (sel ? 0.15 : 0));
    strokeCurve(ctx, pts, stroke, w * (sel ? 1.35 : 0.9), !!iso.dashed, scale);
    // Controls are sparse waypoints — never fall back to dense pixels
    if ((showHandles || sel) && (iso.controls?.length || 0) > 0) {
      ctx.globalAlpha = pointA;
      drawVertices(ctx, iso.controls!, sel ? '#ffe66d' : stroke, scale, sel ? pr * 1.1 : pr * 0.9);
    }
    if (iso.temperature_C != null && pts.length > 0) {
      const mid = pts[Math.floor(pts.length / 2)];
      ctx.globalAlpha = pointA;
      ctx.fillStyle = isothermMissingTemp(iso) ? '#e10600' : stroke;
      ctx.font = `${10 / scale}px sans-serif`;
      ctx.fillText(String(iso.temperature_C), mid[0] + 4 / scale, mid[1] - 4 / scale);
    }
  }

  for (const inv of view.invariants || []) {
    const p = inv.pixel;
    if (!p || p.length < 2) continue;
    const sel = selected?.kind === 'invariant' && selected.id === inv.id;
    ctx.globalAlpha = pointA;
    ctx.fillStyle = sel ? PICK_STROKE : INVARIANT_FILL;
    ctx.strokeStyle = sel ? '#fff' : '#000';
    ctx.lineWidth = 1 / scale;
    ctx.beginPath();
    ctx.arc(p[0], p[1], (sel ? pr * 1.35 : pr * 1.15) / scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    if (inv.temperature_C != null) {
      ctx.fillStyle = '#111';
      ctx.font = `${10 / scale}px sans-serif`;
      ctx.fillText(String(inv.temperature_C), p[0] + 6 / scale, p[1] - 5 / scale);
    }
  }

  for (const node of view.nodes || []) {
    const p = node.pixel;
    if (!p || p.length < 2) continue;
    const sel = selected?.kind === 'node' && selected.index === node.index;
    ctx.globalAlpha = nodeA;
    const kind = (node as { kind?: string }).kind || '';
    ctx.fillStyle = sel ? PICK_STROKE : NODE_COLORS[kind] || '#cccccc';
    ctx.strokeStyle = sel ? '#fff' : '#111';
    ctx.lineWidth = 1 / scale;
    ctx.beginPath();
    ctx.arc(p[0], p[1], (sel ? pr * 1.2 : pr) / scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
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
