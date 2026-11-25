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
  components?: string[];
  cornersImage?: number[][];
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
  /** SE alias; diagram-review used ``points``. */
  invariants?: Array<{
    id: string;
    /** Short canvas label (node I#/C#, notation, or id). */
    label?: string | null;
    /** ``compound`` = named formula point; ``invariant`` = composition + °C (e.g. eutectic). */
    pointRole?: 'compound' | 'invariant' | null;
    notation?: string | null;
    reaction?: string | null;
    phases?: string[];
    pixel?: number[];
    temperature_C?: number | null;
    composition?: Record<string, number | null | undefined>;
    wt?: number[];
    provenance?: string;
  }>;
  /** Diagram-review name for invariants (kept for session.view compatibility). */
  points?: Array<{
    id: string;
    label?: string | null;
    notation?: string | null;
    reaction?: string | null;
    phases?: string[];
    pixel?: number[];
    temperature_C?: number | null;
    composition?: Record<string, number | null | undefined>;
    wt?: number[];
    provenance?: string;
  }>;
  liquidus?: Array<{
    index: number;
    pixels?: number[][];
  }>;
  /** Primary-phase field regions (polygons in image pixels). */
  fields?: Array<{
    name: string;
    colorIndex?: number;
    polygons?: number[][][];
    centroid?: number[] | null;
  }>;
  nodes?: Array<{
    /** Prefer ``nodeIndex`` from session.view; ``index`` kept for older payloads. */
    nodeIndex?: number;
    index?: number;
    id?: string;
    kind?: string;
    label?: string | null;
    /** Linked draft invariant id when kind is invariant. */
    invariant?: string | null;
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
  lastIsothermBuild?: { index?: number; removedCount?: number; removedCrossed?: number[] };
  lastIsothermJoin?: { joined?: boolean; mergedCount?: number; closed?: boolean; index?: number };
  lastTemperaturePropagate?: { corrected?: unknown[]; reason?: string };
  lastInvariantLookup?: {
    id?: string;
    compoundId?: string | null;
    notation?: string | null;
    temperature_C?: number | null;
    resolved?: boolean;
  };
  lastInvariantReposition?: { count?: number };
  lastInvariantRestore?: {
    draftSource?: string;
    added?: number;
    filledTemperature?: number;
    filledPhases?: number;
    total?: number;
    nodeCount?: number;
  };
  lastNodesReload?: { count?: number };
  lastNodeEnsure?: {
    nodeIndex?: number;
    id?: string;
    created?: boolean;
    pointRole?: string;
  };
  lastContourJoin?: {
    kind?: string;
    index?: number;
    removed?: number;
    pointIndex?: number;
  };
  lastClearUnused?: {
    removedNodes?: number;
    removedInvariants?: number;
    keptNodes?: number;
    keptInvariants?: number;
  };
  lastNormalizePoints?: {
    clusters?: number;
    replaced?: number;
    joined?: number;
  };
  lastAddNote?: string;
};

export type SelectedCurve = { kind: 'boundary' | 'isotherm'; index: number };

export type SelectionInfo = {
  pointCount: number;
  curve: SelectedCurve | null;
  /** True when Delete selected / Delete key should remove something. */
  canDelete: boolean;
  invariantId?: string | null;
  fieldName?: string | null;
};

export type Hit =
  | { kind: 'boundary'; index: number; pointIndex?: number }
  | { kind: 'isotherm'; index: number; pointIndex?: number }
  | { kind: 'invariant'; id: string }
  | { kind: 'node'; index: number }
  | { kind: 'liquidus'; index: number; pointIndex?: number }
  /** Calibration triangle vertex; ``index`` = ``view.components`` / ``cornersImage`` order. */
  | { kind: 'frame'; index: number }
  | { kind: 'field'; name: string };

/** True when the hit is a draggable vertex / point (not just a curve body). */
export function isPointHit(hit: Hit | null): boolean {
  if (!hit) return false;
  if (hit.kind === 'invariant' || hit.kind === 'node' || hit.kind === 'frame') return true;
  return hit.pointIndex != null;
}
