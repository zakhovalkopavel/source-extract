/** Diagram-review canvas colours / stroke styles (parity with app.js). */

export const ISO_MISSING = '#e10600';
export const ISO_MISSING_SEL = '#ff2a2a';
export const BOUNDARY_STROKE = '#0d5c2e';
export const BOUNDARY_STROKE_SEL = '#1a8f48';
export const BOUNDARY_HANDLE = '#147a3c';
export const BOUNDARY_ARROW = '#0f6b36';
export const PICK_STROKE = '#c77dff';
/** Hollow invariant / compound ring stroke (reference-overlay parity). */
export const INVARIANT_STROKE = '#1b9e4b';
export const INVARIANT_STROKE_SEL = '#ffe66d';
export const INVARIANT_LABEL = '#0b3d1c';
export const SEED_STROKE = '#4cc9f0';
export const SEED_SNAP = '#ffd166';
export const IMMISCIBILITY = '#00e5ff';
export const CANVAS_BG = '#0e1014';
/** Calibration triangle / axes frame (cornersImage). */
export const FRAME_STROKE = '#ff9f1c';
export const FRAME_CORNER = '#ffbe0b';

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

/** Soft fills for primary-phase fields (parity with ternary overlay palette). */
export const FIELD_PALETTE = [
  '#e6194b',
  '#3cb44b',
  '#ffe119',
  '#0082c8',
  '#f58231',
  '#911eb4',
  '#46f0f0',
  '#f032e6',
  '#d2f53c',
  '#fabebe',
  '#008080',
  '#e6beff',
  '#aa6e28',
  '#fffac8',
  '#800000',
  '#aaffc3',
  '#808000',
  '#ffd8b1',
  '#000080',
  '#808080',
];

/** Flat palette colour for a field (selection uses outline, not a colour swap). */
export function fieldFillColor(colorIndex: number | undefined, _selected = false): string {
  return FIELD_PALETTE[Math.max(0, colorIndex ?? 0) % FIELD_PALETTE.length];
}

/** Convert ``#rrggbb`` + opacity 0–1 → ``rgba(...)`` for flat monocolour fills. */
export function fieldFillRgba(colorIndex: number | undefined, alpha: number): string {
  const hex = fieldFillColor(colorIndex);
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const a = Math.max(0, Math.min(1, alpha));
  return `rgba(${r},${g},${b},${a})`;
}

export type ViewOpacity = {
  points: number;
  curves: number;
  all: number;
  reference: number;
  live: number;
  nodes: number;
  /** Primary-phase field fills. */
  fields: number;
  /** Curve stroke thickness in screen pixels (≈0.5–4). */
  curveWidth: number;
  /** Handle / invariant / node radius in screen pixels (≈1–8). */
  pointSize: number;
};

export const DEFAULT_VIEW_OPACITY: ViewOpacity = {
  points: 1,
  curves: 1,
  all: 1,
  // Reference / live PNGs superseded by frontend vector drawing
  reference: 0,
  live: 0,
  nodes: 1,
  fields: 0.55,
  curveWidth: 2,
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
