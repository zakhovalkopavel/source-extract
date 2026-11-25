import type { Hit, Point2, SessionView } from '../types';
import { mapPixelThroughTriangles } from './triangleMap';
import { viewInvariants } from './viewInvariants';

function asCorners(raw: number[][] | undefined): Point2[] | null {
  if (!raw || raw.length < 3) return null;
  const out: Point2[] = [];
  for (let i = 0; i < 3; i++) {
    const c = raw[i];
    if (!c || c.length < 2) return null;
    out.push([Number(c[0]), Number(c[1])]);
  }
  return out;
}

/** Warp every image-space overlay with the calibration triangle (live frame drag). */
function warpViewToTriangle(
  view: SessionView,
  fromCorners: Point2[],
  toCorners: Point2[],
): SessionView {
  const map = (p: number[] | undefined | null) =>
    mapPixelThroughTriangles(p, fromCorners, toCorners) as number[] | undefined;

  const mapRing = (ring: number[][]) =>
    ring.map((p) => map(p) || p).filter((p): p is number[] => !!p && p.length >= 2);

  return {
    ...view,
    cornersImage: toCorners.map((c) => [c[0], c[1]]),
    boundaries: (view.boundaries || []).map((b) => ({
      ...b,
      pixels: (b.pixels || []).map((p) => map(p) || p),
    })),
    isotherms: (view.isotherms || []).map((iso) => ({
      ...iso,
      pixels: (iso.pixels || []).map((p) => map(p) || p),
      controls: (iso.controls || []).map((p) => map(p) || p),
    })),
    liquidus: (view.liquidus || []).map((br) => ({
      ...br,
      pixels: (br.pixels || []).map((p) => map(p) || p),
    })),
    fields: (view.fields || []).map((f) => ({
      ...f,
      polygons: (f.polygons || []).map(mapRing),
      centroid: f.centroid ? map(f.centroid) || f.centroid : f.centroid,
    })),
    invariants: viewInvariants(view).map((inv) => ({
      ...inv,
      pixel: inv.pixel ? map(inv.pixel) || inv.pixel : inv.pixel,
    })),
    points: (view.points || viewInvariants(view)).map((inv) => ({
      ...inv,
      pixel: inv.pixel ? map(inv.pixel) || inv.pixel : inv.pixel,
    })),
    nodes: (view.nodes || []).map((n) => ({
      ...n,
      pixel: n.pixel ? map(n.pixel) || n.pixel : n.pixel,
    })),
  };
}

/** Return a shallow-cloned view with one point relocated (live drag preview). */
export function withDraggedPoint(view: SessionView, hit: Hit, pt: Point2): SessionView {
  if ((hit.kind === 'boundary' || hit.kind === 'liquidus') && hit.pointIndex != null) {
    const key = hit.kind === 'boundary' ? 'boundaries' : 'liquidus';
    const list = view[key] || [];
    return {
      ...view,
      [key]: list.map((c) => {
        if (c.index !== hit.index) return c;
        const pixels = [...(c.pixels || [])];
        if (hit.pointIndex! >= pixels.length) return c;
        pixels[hit.pointIndex!] = [pt[0], pt[1]];
        return { ...c, pixels };
      }),
    };
  }
  if (hit.kind === 'isotherm' && hit.pointIndex != null) {
    return {
      ...view,
      isotherms: (view.isotherms || []).map((iso) => {
        if (iso.index !== hit.index) return iso;
        const controls = [...(iso.controls || [])];
        if (hit.pointIndex! >= controls.length) return iso;
        controls[hit.pointIndex!] = [pt[0], pt[1]];
        return { ...iso, controls };
      }),
    };
  }
  if (hit.kind === 'invariant') {
    const patch = (list: NonNullable<SessionView['invariants']>) =>
      list.map((inv) => (inv.id === hit.id ? { ...inv, pixel: [pt[0], pt[1]] } : inv));
    return {
      ...view,
      invariants: patch(viewInvariants(view)),
      points: patch(view.points || viewInvariants(view)),
    };
  }
  if (hit.kind === 'node') {
    return {
      ...view,
      nodes: (view.nodes || []).map((n) => {
        const idx = n.nodeIndex ?? n.index;
        if (idx !== hit.index) return n;
        return { ...n, pixel: [pt[0], pt[1]] };
      }),
    };
  }
  if (hit.kind === 'frame') {
    const fromCorners = asCorners(view.cornersImage);
    if (!fromCorners || hit.index < 0 || hit.index >= fromCorners.length) return view;
    const toCorners: Point2[] = fromCorners.map((c) => [c[0], c[1]] as Point2);
    toCorners[hit.index] = [pt[0], pt[1]];
    // Fields / curves / markers track the triangle via the unique affine map.
    return warpViewToTriangle(view, fromCorners, toCorners);
  }
  return view;
}
