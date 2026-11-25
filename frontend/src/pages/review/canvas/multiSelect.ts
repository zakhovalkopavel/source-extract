import type { Hit, Point2, SessionView } from '../types';
import { viewInvariants } from './viewInvariants';

export type BatchDeleteItem =
  | { type: 'invariant'; id: string }
  | { type: 'node'; index: number }
  | { type: 'vertex'; kind: 'boundary' | 'isotherm'; index: number; pointIndex: number };

function boundaryHandleIndices(pixelCount: number): number[] {
  if (pixelCount <= 0) return [];
  if (pixelCount <= 14) return [...Array(pixelCount).keys()];
  const idxs = new Set([0, pixelCount - 1]);
  const step = Math.max(1, Math.floor((pixelCount - 1) / 12));
  for (let i = step; i < pixelCount - 1; i += step) idxs.add(i);
  return [...idxs].sort((a, b) => a - b);
}

export function multiKey(hit: Hit): string {
  if (hit.kind === 'invariant') return `inv:${hit.id}`;
  if (hit.kind === 'node') return `node:${hit.index}`;
  if (hit.kind === 'frame') return `frame:${hit.index}`;
  if (hit.pointIndex != null) return `v:${hit.kind}:${hit.index}:${hit.pointIndex}`;
  return `c:${hit.kind}:${hit.index}`;
}

export function hitsEqual(a: Hit, b: Hit): boolean {
  return multiKey(a) === multiKey(b);
}

export function isMultiSelected(multi: Hit[], hit: Hit): boolean {
  const k = multiKey(hit);
  return multi.some((m) => multiKey(m) === k);
}

/** Toggle or replace multi-selection (Shift = additive / toggle). */
export function nextMultiSelection(prev: Hit[], hit: Hit, additive: boolean): Hit[] {
  if (!additive) return [hit];
  if (isMultiSelected(prev, hit)) return prev.filter((m) => !hitsEqual(m, hit));
  return [...prev, hit];
}

export function hitToBatchItem(hit: Hit): BatchDeleteItem | null {
  if (hit.kind === 'invariant') return { type: 'invariant', id: hit.id };
  if (hit.kind === 'node') return { type: 'node', index: hit.index };
  if ((hit.kind === 'boundary' || hit.kind === 'isotherm') && hit.pointIndex != null) {
    return {
      type: 'vertex',
      kind: hit.kind,
      index: hit.index,
      pointIndex: hit.pointIndex,
    };
  }
  return null;
}

export function isDeletablePointHit(hit: Hit | null): boolean {
  if (!hit) return false;
  // Calibration triangle corners are not deletable
  if (hit.kind === 'frame') return false;
  if (hit.kind === 'invariant' || hit.kind === 'node') return true;
  return hit.pointIndex != null;
}

/** Collect selectable point hits inside an axis-aligned image-space rect. */
export function collectPointsInRect(
  view: SessionView | undefined,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  selectedCurve: Hit | null,
): Hit[] {
  if (!view) return [];
  const left = Math.min(x0, x1);
  const right = Math.max(x0, x1);
  const top = Math.min(y0, y1);
  const bottom = Math.max(y0, y1);
  const inside = (x: number, y: number) => x >= left && x <= right && y >= top && y <= bottom;
  const out: Hit[] = [];

  for (const inv of viewInvariants(view)) {
    const p = inv.pixel;
    if (p && p.length >= 2 && inside(p[0], p[1])) {
      out.push({ kind: 'invariant', id: inv.id });
    }
  }
  for (const node of view.nodes || []) {
    const p = node.pixel;
    const idx = node.nodeIndex ?? node.index;
    if (p && p.length >= 2 && idx != null && inside(p[0], p[1])) {
      out.push({ kind: 'node', index: idx });
    }
  }
  for (const iso of view.isotherms || []) {
    (iso.controls || []).forEach((c, pointIndex) => {
      if (c && c.length >= 2 && inside(c[0], c[1])) {
        out.push({ kind: 'isotherm', index: iso.index, pointIndex });
      }
    });
  }
  for (const b of view.boundaries || []) {
    const pix = b.pixels || [];
    const dense =
      selectedCurve?.kind === 'boundary' && selectedCurve.index === b.index;
    const idxs = dense ? [...pix.keys()] : boundaryHandleIndices(pix.length);
    for (const pointIndex of idxs) {
      const c = pix[pointIndex];
      if (c && c.length >= 2 && inside(c[0], c[1])) {
        out.push({ kind: 'boundary', index: b.index, pointIndex });
      }
    }
  }
  return out;
}

export type MarqueeBox = { x0: number; y0: number; x1: number; y1: number };

export function marqueeScreenSize(box: MarqueeBox, scale: number): Point2 {
  return [Math.abs(box.x1 - box.x0) * scale, Math.abs(box.y1 - box.y0) * scale];
}
