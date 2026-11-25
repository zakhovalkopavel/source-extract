import type { Point2 } from '../types';

/**
 * Unclamped barycentric coordinates of ``p`` in triangle ``corners``.
 * Defines the unique affine map that sends the triangle to any other triangle.
 */
export function barycentricUnclamped(
  p: Point2,
  corners: Point2[],
): [number, number, number] {
  const [x1, y1] = corners[0];
  const [x2, y2] = corners[1];
  const [x3, y3] = corners[2];
  const denom = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3);
  if (Math.abs(denom) < 1e-12) return [1 / 3, 1 / 3, 1 / 3];
  const a = ((y2 - y3) * (p[0] - x3) + (x3 - x2) * (p[1] - y3)) / denom;
  const b = ((y3 - y1) * (p[0] - x3) + (x1 - x3) * (p[1] - y3)) / denom;
  return [a, b, 1 - a - b];
}

export function fromBarycentric(
  weights: [number, number, number],
  corners: Point2[],
): Point2 {
  const [a, b, c] = weights;
  return [
    a * corners[0][0] + b * corners[1][0] + c * corners[2][0],
    a * corners[0][1] + b * corners[1][1] + c * corners[2][1],
  ];
}

/** Map a point through the affine triangle map ``fromCorners`` → ``toCorners``. */
export function mapPointThroughTriangles(
  p: Point2,
  fromCorners: Point2[],
  toCorners: Point2[],
): Point2 {
  if (fromCorners.length < 3 || toCorners.length < 3) return p;
  return fromBarycentric(barycentricUnclamped(p, fromCorners), toCorners);
}

export function mapPixelThroughTriangles(
  p: number[] | undefined | null,
  fromCorners: Point2[],
  toCorners: Point2[],
): number[] | undefined | null {
  if (!p || p.length < 2) return p;
  const q = mapPointThroughTriangles([Number(p[0]), Number(p[1])], fromCorners, toCorners);
  return [q[0], q[1]];
}
