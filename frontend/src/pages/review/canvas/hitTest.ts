import type { Hit, Point2, SessionView } from '../types';
import { pointInPolygon } from './pointInPolygon';
import { viewInvariants } from './viewInvariants';

function dist(a: Point2, b: Point2): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

function asPt(p: number[] | undefined): Point2 | null {
  if (!p || p.length < 2) return null;
  return [Number(p[0]), Number(p[1])];
}

function distToSegment(p: Point2, a: Point2, b: Point2): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  if (len2 < 1e-12) return dist(p, a);
  let t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return dist(p, [a[0] + t * dx, a[1] + t * dy]);
}

function boundaryHandleIndices(pixelCount: number): number[] {
  if (pixelCount <= 0) return [];
  if (pixelCount <= 14) return [...Array(pixelCount).keys()];
  const idxs = new Set([0, pixelCount - 1]);
  const step = Math.max(1, Math.floor((pixelCount - 1) / 12));
  for (let i = step; i < pixelCount - 1; i += step) idxs.add(i);
  return [...idxs].sort((a, b) => a - b);
}

function hitPolylineBody(
  kind: 'boundary' | 'isotherm' | 'liquidus',
  index: number,
  pixels: number[][],
  imgPt: Point2,
  tol: number,
): { hit: Hit; d: number } | null {
  let best: { hit: Hit; d: number } | null = null;
  for (let i = 0; i < pixels.length - 1; i++) {
    const a = asPt(pixels[i]);
    const b = asPt(pixels[i + 1]);
    if (!a || !b) continue;
    const d = distToSegment(imgPt, a, b);
    if (d <= tol && (!best || d < best.d)) {
      best = { hit: { kind, index }, d };
    }
  }
  return best;
}

export type HitTestOpts = {
  /**
   * Radius for discrete handles / invariants / nodes.
   * Defaults to ``curveTol``. Use a smaller value in select/delete so clicking
   * the curve body selects the whole curve instead of a nearby control point.
   */
  pointTol?: number;
};

/**
 * Prefer discrete points/handles within ``pointTol``, else whole-curve body within ``curveTol``.
 * ``curveTol`` / ``pointTol`` are in image pixels.
 */
export function hitTestView(
  view: SessionView | undefined,
  imgPt: Point2,
  curveTol: number,
  opts?: HitTestOpts,
): Hit | null {
  if (!view) return null;
  const pointTol = opts?.pointTol ?? curveTol;

  let bestPoint: { hit: Hit; d: number } | null = null;

  // Calibration triangle corners — easy to grab (slightly larger pick radius)
  const frameTol = Math.max(pointTol, pointTol * 1.35);
  for (let i = 0; i < (view.cornersImage || []).length; i++) {
    const p = asPt(view.cornersImage![i]);
    if (!p) continue;
    const d = dist(p, imgPt);
    if (d <= frameTol && (!bestPoint || d < bestPoint.d)) {
      bestPoint = { hit: { kind: 'frame', index: i }, d };
    }
  }

  for (const inv of viewInvariants(view)) {
    const p = asPt(inv.pixel);
    if (!p) continue;
    const d = dist(p, imgPt);
    if (d <= pointTol && (!bestPoint || d < bestPoint.d)) {
      bestPoint = { hit: { kind: 'invariant', id: inv.id }, d };
    }
  }
  for (const node of view.nodes || []) {
    const p = asPt(node.pixel);
    const idx = node.nodeIndex ?? node.index;
    if (!p || idx == null) continue;
    const d = dist(p, imgPt);
    if (d <= pointTol && (!bestPoint || d < bestPoint.d)) {
      bestPoint = { hit: { kind: 'node', index: idx }, d };
    }
  }
  for (const iso of view.isotherms || []) {
    const controls = iso.controls || [];
    for (let j = 0; j < controls.length; j++) {
      const p = asPt(controls[j]);
      if (!p) continue;
      const d = dist(p, imgPt);
      if (d <= pointTol && (!bestPoint || d < bestPoint.d)) {
        bestPoint = { hit: { kind: 'isotherm', index: iso.index, pointIndex: j }, d };
      }
    }
  }
  for (const b of view.boundaries || []) {
    const pix = b.pixels || [];
    const idxs = boundaryHandleIndices(pix.length);
    for (const j of idxs) {
      const p = asPt(pix[j]);
      if (!p) continue;
      const d = dist(p, imgPt);
      if (d <= pointTol && (!bestPoint || d < bestPoint.d)) {
        bestPoint = { hit: { kind: 'boundary', index: b.index, pointIndex: j }, d };
      }
    }
  }
  for (const liq of view.liquidus || []) {
    const pts = liq.pixels || [];
    for (let j = 0; j < pts.length; j++) {
      const p = asPt(pts[j]);
      if (!p) continue;
      const d = dist(p, imgPt);
      if (d <= pointTol && (!bestPoint || d < bestPoint.d)) {
        bestPoint = { hit: { kind: 'liquidus', index: liq.index, pointIndex: j }, d };
      }
    }
  }
  if (bestPoint) return bestPoint.hit;

  // Curve body (select / highlight / avoid accidental pan)
  let bestCurve: { hit: Hit; d: number } | null = null;
  for (const iso of view.isotherms || []) {
    const h = hitPolylineBody('isotherm', iso.index, iso.pixels || [], imgPt, curveTol);
    if (h && (!bestCurve || h.d < bestCurve.d)) bestCurve = h;
  }
  for (const b of view.boundaries || []) {
    const h = hitPolylineBody('boundary', b.index, b.pixels || [], imgPt, curveTol);
    if (h && (!bestCurve || h.d < bestCurve.d)) bestCurve = h;
  }
  for (const liq of view.liquidus || []) {
    const h = hitPolylineBody('liquidus', liq.index, liq.pixels || [], imgPt, curveTol);
    if (h && (!bestCurve || h.d < bestCurve.d)) bestCurve = h;
  }
  if (bestCurve) return bestCurve.hit;

  // Field fills (under curves) — last so handles/curves win
  for (const field of view.fields || []) {
    for (const ring of field.polygons || []) {
      if (pointInPolygon(imgPt, ring)) {
        return { kind: 'field', name: field.name };
      }
    }
  }
  return null;
}
