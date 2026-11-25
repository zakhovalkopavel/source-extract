/** Diagram-review canvas colours / stroke styles (parity with app.js). */

export const ISO_MISSING = '#e10600';
export const ISO_MISSING_SEL = '#ff2a2a';
export const BOUNDARY_STROKE = '#0d5c2e';
export const BOUNDARY_STROKE_SEL = '#1a8f48';
export const BOUNDARY_HANDLE = '#147a3c';
export const BOUNDARY_ARROW = '#0f6b36';
export const PICK_STROKE = '#c77dff';
export const INVARIANT_FILL = '#ffc800';
export const SEED_STROKE = '#4cc9f0';
export const SEED_SNAP = '#ffd166';
export const IMMISCIBILITY = '#00e5ff';
export const CANVAS_BG = '#0e1014';

/** No reds (missing °C) and no greens (boundaries only). */
export const ISO_PALETTE = [
  '#00e5ff',
  '#4895ef',
  '#7209b7',
  '#9b5de5',
  '#fb5607',
  '#ffbe0b',
  '#c77dff',
  '#8338ec',
  '#3a86ff',
  '#ff9f1c',
  '#5e60ce',
  '#56cfe1',
  '#f15bb5',
  '#4cc9f0',
  '#b5179e',
];

export const NODE_COLORS: Record<string, string> = {
  corner: '#4cc9f0',
  invariant: '#3a86ff',
  junction: '#8338ec',
  edge: '#fb5607',
  'dash-end': '#9b5de5',
  'free-end': '#9c6644',
  ring: '#c77dff',
};

export type ViewOpacity = {
  points: number;
  curves: number;
  all: number;
  reference: number;
  live: number;
  nodes: number;
  /** Curve stroke thickness in screen pixels (≈0.5–4). */
  curveWidth: number;
  /** Handle / invariant / node radius in screen pixels (≈1–8). */
  pointSize: number;
};

export const DEFAULT_VIEW_OPACITY: ViewOpacity = {
  points: 1,
  curves: 1,
  all: 1,
  reference: 0.45,
  // Live PNG already draws thick Pillow strokes — keep off; vectors are the editor overlay
  live: 0,
  nodes: 1,
  curveWidth: 1,
  pointSize: 3,
};

export const CURVE_WIDTH_MIN = 0.5;
export const CURVE_WIDTH_MAX = 4;
export const POINT_SIZE_MIN = 1;
export const POINT_SIZE_MAX = 8;

export function isothermMissingTemp(iso: { temperature_C?: number | null }): boolean {
  const t = iso.temperature_C;
  return t == null || t === ('' as unknown) || !Number.isFinite(Number(t));
}

export function uniqueIsothermTemps(
  isotherms: Array<{ temperature_C?: number | null }> | undefined,
): number[] {
  const set = new Set<number>();
  for (const iso of isotherms || []) {
    if (!isothermMissingTemp(iso)) set.add(Number(iso.temperature_C));
  }
  return [...set].sort((a, b) => a - b);
}

export function isothermStrokeColor(
  iso: { temperature_C?: number | null },
  selected: boolean,
  temps: number[],
): string {
  if (isothermMissingTemp(iso)) return selected ? ISO_MISSING_SEL : ISO_MISSING;
  if (selected) return '#ffe66d';
  const idx = temps.indexOf(Number(iso.temperature_C));
  return ISO_PALETTE[Math.max(0, idx) % ISO_PALETTE.length];
}
