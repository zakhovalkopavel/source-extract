export type ToolMode =
  | 'select'
  | 'move'
  | 'add'
  | 'delete'
  | 'arrows'
  | 'seed-boundary'
  | 'seed-isotherm'
  | 'add-invariant';

export type Point2 = [number, number];

export type SessionView = {
  boundaries?: Array<{
    index: number;
    pixels?: number[][];
    controls?: number[][];
    dashed?: boolean;
    arrows?: string[];
    fields?: Array<string | null>;
  }>;
  isotherms?: Array<{
    index: number;
    pixels?: number[][];
    controls?: number[][];
    dashed?: boolean;
    temperature_C?: number | null;
    field?: string | null;
  }>;
  invariants?: Array<{
    id: string;
    pixel?: number[];
    temperature_C?: number | null;
  }>;
  liquidus?: Array<{
    index: number;
    pixels?: number[][];
  }>;
  nodes?: Array<{
    index: number;
    pixel?: number[];
  }>;
};

export type ReviewSession = {
  id: string;
  systemId: string;
  system?: string;
  draftSource?: string;
  diagramKind?: 'binary' | 'ternary';
  status?: string;
  components?: string[];
  phases?: string[];
  view?: SessionView;
  image?: {
    width?: number;
    height?: number;
    pageOrigin?: number[];
    referencePageOrigin?: number[];
    url?: string;
    liveOverlayUrl?: string;
    referenceOverlayUrl?: string | null;
    hasReferenceOverlay?: boolean;
    synthetic?: boolean;
  };
  undoDepth?: number;
  validation?: {
    canConfirm?: boolean;
    missingIsothermTemperatures?: unknown[];
  };
  guidance?: { cards?: Array<Record<string, unknown>>; answers?: unknown[] };
  lastMoveNote?: unknown;
  lastIsothermBuild?: unknown;
};

export type Hit =
  | { kind: 'boundary'; index: number; pointIndex?: number }
  | { kind: 'isotherm'; index: number; pointIndex?: number }
  | { kind: 'invariant'; id: string }
  | { kind: 'node'; index: number }
  | { kind: 'liquidus'; index: number; pointIndex?: number };

/** True when the hit is a draggable vertex / point (not just a curve body). */
export function isPointHit(hit: Hit | null): boolean {
  if (!hit) return false;
  if (hit.kind === 'invariant' || hit.kind === 'node') return true;
  return hit.pointIndex != null;
}
