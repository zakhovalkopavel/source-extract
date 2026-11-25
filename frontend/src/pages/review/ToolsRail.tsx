import {
  Button,
  Divider,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import type { ViewOpacity } from './canvas/curveStyles';
import { CurveEditPanel } from './CurveEditPanel';
import { InvariantEditPanel } from './InvariantEditPanel';
import { ReviewLists } from './ReviewLists';
import type { ReviewSession, SelectedCurve, ToolMode } from './types';
import { ViewOptions } from './ViewOptions';

type Props = {
  tool: ToolMode;
  onTool: (t: ToolMode) => void;
  /** Delete current multi-selection / selected curve (toolbar Delete action). */
  onDeleteSelection: () => void;
  selectionCount?: number;
  canDelete?: boolean;
  selectedCurve?: SelectedCurve | null;
  onCurveIndexChange?: (index: number) => void;
  invariantId: string;
  onInvariantId: (id: string) => void;
  selectedInvariantId?: string | null;
  onSelectInvariant?: (id: string) => void;
  selectedField?: string | null;
  onSelectField?: (name: string) => void;
  onSession: (s: ReviewSession) => void;
  onStatus: (msg: string) => void;
  session: ReviewSession | null;
  busy?: boolean;
  opacity: ViewOpacity;
  onOpacity: (o: ViewOpacity) => void;
  onUndo: () => void;
  onAnalyze: () => void;
  onRepositionInvariants: () => void;
  onRestoreInvariants: () => void;
  onConfirm: () => void;
  onGuidance: () => void;
  onReload: () => void;
  /** Seed isotherm / boundary commit controls. */
  seedCount?: number;
  seedField?: string;
  onSeedField?: (v: string) => void;
  seedTemperatureC?: string;
  onSeedTemperatureC?: (v: string) => void;
  onCommitSeed?: () => void;
};

const TOOLS: Array<{ id: ToolMode; label: string }> = [
  { id: 'select', label: 'Select' },
  { id: 'move', label: 'Move' },
  { id: 'add', label: 'Add pt' },
  { id: 'delete', label: 'Delete' },
  { id: 'arrows', label: 'Arrows' },
  { id: 'seed-boundary', label: 'Seed boundary' },
  { id: 'seed-isotherm', label: 'Seed isotherm' },
  { id: 'add-invariant', label: 'Add invariant' },
];

export function ToolsRail({
  tool,
  onTool,
  onDeleteSelection,
  selectionCount = 0,
  canDelete = false,
  selectedCurve = null,
  onCurveIndexChange,
  invariantId,
  onInvariantId,
  selectedInvariantId = null,
  onSelectInvariant,
  selectedField = null,
  onSelectField,
  onSession,
  onStatus,
  session,
  busy,
  opacity,
  onOpacity,
  onUndo,
  onAnalyze,
  onRepositionInvariants,
  onRestoreInvariants,
  onConfirm,
  onGuidance,
  onReload,
  seedCount = 0,
  seedField = '',
  onSeedField,
  seedTemperatureC = '1500',
  onSeedTemperatureC,
  onCommitSeed,
}: Props) {
  const seeding = tool === 'seed-boundary' || tool === 'seed-isotherm';
  return (
    <Stack
      spacing={1.5}
      sx={{
        width: { xs: '100%', md: 240 },
        flexShrink: 0,
        maxHeight: { md: '78vh' },
        overflow: 'auto',
        pr: 0.5,
      }}
    >
      <Typography variant="subtitle2">Tools</Typography>
      <ToggleButtonGroup
        exclusive
        orientation="vertical"
        size="small"
        value={tool}
        onChange={(_, v) => v && onTool(v)}
        fullWidth
      >
        {TOOLS.map((t) => (
          <ToggleButton
            key={t.id}
            value={t.id}
            sx={{ textTransform: 'none' }}
            onClick={() => {
              if (t.id === 'delete' && tool === 'delete') onDeleteSelection();
            }}
          >
            {t.label}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>

      {tool === 'add-invariant' && (
        <Stack spacing={0.75} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1 }}>
          <Typography variant="caption">
            Enter id / notation (e.g. A3S2 or mullite), then click the diagram. Melting °C is
            filled from compounds.json when known.
          </Typography>
          <TextField
            size="small"
            label="Invariant id"
            placeholder="A3S2"
            value={invariantId}
            onChange={(e) => onInvariantId(e.target.value)}
            fullWidth
          />
        </Stack>
      )}

      {seeding && (
        <Stack spacing={0.75} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1 }}>
          <Typography variant="caption">
            Click ≥2 waypoints on the diagram, then Commit (or Enter / double-click).
            {seedCount > 0 ? ` Waypoints: ${seedCount}` : ''}
          </Typography>
          {tool === 'seed-isotherm' && (
            <>
              <TextField
                size="small"
                label="Field"
                value={seedField}
                onChange={(e) => onSeedField?.(e.target.value)}
                placeholder={session?.phases?.[0] || 'phase'}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onCommitSeed?.();
                }}
                fullWidth
              />
              <TextField
                size="small"
                label="Temperature °C"
                type="number"
                value={seedTemperatureC}
                onChange={(e) => onSeedTemperatureC?.(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onCommitSeed?.();
                }}
                fullWidth
              />
            </>
          )}
          <Button
            variant="contained"
            size="small"
            disabled={!session || busy || seedCount < 2}
            onClick={() => onCommitSeed?.()}
          >
            Commit seed{seedCount >= 2 ? ` (${seedCount})` : ''}
          </Button>
        </Stack>
      )}

      {canDelete && (
        <Button
          variant="contained"
          color="error"
          size="small"
          disabled={!session || busy}
          onClick={onDeleteSelection}
        >
          {selectionCount > 0
            ? `Delete selected (${selectionCount})`
            : selectedCurve
              ? `Delete ${selectedCurve.kind} #${selectedCurve.index}`
              : 'Delete selected'}
        </Button>
      )}
      {session && selectedCurve && (
        <CurveEditPanel
          session={session}
          selected={selectedCurve}
          busy={busy}
          onSession={onSession}
          onStatus={onStatus}
          onSelectedIndex={onCurveIndexChange}
        />
      )}
      {session && selectedInvariantId && (
        <InvariantEditPanel
          session={session}
          invariantId={selectedInvariantId}
          busy={busy}
          onSession={onSession}
          onStatus={onStatus}
          onInvariantId={onSelectInvariant}
        />
      )}

      {session && (
        <>
          <Divider />
          <ReviewLists
            session={session}
            selectedInvariantId={selectedInvariantId}
            onSelectInvariant={onSelectInvariant}
            selectedField={selectedField}
            onSelectField={onSelectField}
          />
        </>
      )}

      <Typography variant="caption" color="text.secondary">
        Orange dashed triangle = calibration frame (drag corners in Move/Select). Invariants list
        is off-canvas. Pan: Space / Alt / middle-drag.
      </Typography>
      <Button variant="outlined" disabled={!session || busy} onClick={onUndo}>
        Undo ({session?.undoDepth ?? 0})
      </Button>
      <Button variant="outlined" disabled={!session || busy} onClick={onReload}>
        Reload draft
      </Button>
      <Button variant="outlined" disabled={!session || busy} onClick={onRepositionInvariants}>
        Reposition invariants
      </Button>
      <Button
        variant="outlined"
        disabled={!session || busy}
        onClick={onRestoreInvariants}
        title="Reload I#/C# node labels and merge missing invariants from candidates (keeps your edits)"
      >
        Restore invariants
      </Button>
      <Button variant="contained" disabled={!session || busy} onClick={onAnalyze}>
        Analyze
      </Button>
      <Button
        variant="contained"
        color="success"
        disabled={!session || busy || session.validation?.canConfirm === false}
        onClick={onConfirm}
      >
        Confirm
      </Button>
      <Button variant="text" disabled={!session || busy} onClick={onGuidance}>
        Refresh guidance
      </Button>
      {session?.diagramKind && (
        <Typography variant="caption">Kind: {session.diagramKind}</Typography>
      )}

      <Divider />
      <ViewOptions opacity={opacity} onOpacity={onOpacity} session={session} />
    </Stack>
  );
}
