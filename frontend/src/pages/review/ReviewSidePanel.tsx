import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Button,
  Divider,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import type { ViewOpacity } from './canvas/curveStyles';
import { CurveEditPanel } from './CurveEditPanel';
import { InvariantEditPanel } from './InvariantEditPanel';
import { ReviewLists } from './ReviewLists';
import type { ReviewSession, SelectedCurve } from './types';
import { ViewOptions } from './ViewOptions';

type Props = {
  session: ReviewSession;
  busy?: boolean;
  selectedCurve?: SelectedCurve | null;
  onCurveIndexChange?: (index: number) => void;
  onClearCurve?: () => void;
  /** Delete the whole selected curve. */
  onDeleteCurve?: () => void;
  selectedInvariantId?: string | null;
  onSelectInvariant?: (id: string | null) => void;
  selectedField?: string | null;
  onSelectField?: (name: string | null) => void;
  onSession: (s: ReviewSession) => void;
  onStatus: (msg: string) => void;
  opacity: ViewOpacity;
  onOpacity: (o: ViewOpacity) => void;
  onAnalyze: () => void;
  onClearUnused?: () => void;
  onNormalizePoints?: () => void;
  onRepositionInvariants: () => void;
  onRestoreInvariants: () => void;
  onReload: () => void;
  onGuidance: () => void;
  seedField?: string;
  onSeedField?: (v: string) => void;
  seedTemperatureC?: string;
  onSeedTemperatureC?: (v: string) => void;
  seedingIsotherm?: boolean;
};

export function ReviewSidePanel({
  session,
  busy,
  selectedCurve = null,
  onCurveIndexChange,
  onClearCurve,
  onDeleteCurve,
  selectedInvariantId = null,
  onSelectInvariant,
  selectedField = null,
  onSelectField,
  onSession,
  onStatus,
  opacity,
  onOpacity,
  onAnalyze,
  onClearUnused,
  onNormalizePoints,
  onRepositionInvariants,
  onRestoreInvariants,
  onReload,
  onGuidance,
  seedField = '',
  onSeedField,
  seedTemperatureC = '1500',
  onSeedTemperatureC,
  seedingIsotherm = false,
}: Props) {
  return (
    <Stack
      spacing={1.25}
      sx={{
        width: { xs: '100%', lg: 280 },
        flexShrink: 0,
        maxHeight: { lg: '82vh' },
        overflow: 'auto',
        pr: 0.5,
      }}
    >
      {(selectedInvariantId || selectedCurve) && (
        <Stack spacing={1}>
          {selectedInvariantId && (
            <InvariantEditPanel
              session={session}
              invariantId={selectedInvariantId}
              busy={busy}
              onSession={onSession}
              onStatus={onStatus}
              onInvariantId={(id) => onSelectInvariant?.(id)}
              onCancel={() => onSelectInvariant?.(null)}
            />
          )}
          {selectedCurve && !selectedInvariantId && (
            <CurveEditPanel
              session={session}
              selected={selectedCurve}
              busy={busy}
              onSession={onSession}
              onStatus={onStatus}
              onSelectedIndex={onCurveIndexChange}
              onCancel={() => onClearCurve?.()}
              onDelete={onDeleteCurve}
            />
          )}
          <Divider />
        </Stack>
      )}

      {seedingIsotherm && (
        <Stack spacing={0.75} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Seed isotherm — field &amp; °C
          </Typography>
          <TextField
            size="small"
            label="Field"
            value={seedField}
            onChange={(e) => onSeedField?.(e.target.value)}
            placeholder={session.phases?.[0] || 'field'}
            fullWidth
          />
          <TextField
            size="small"
            label="Temperature °C"
            type="number"
            value={seedTemperatureC}
            onChange={(e) => onSeedTemperatureC?.(e.target.value)}
            fullWidth
          />
        </Stack>
      )}

      <ReviewLists
        session={session}
        selectedInvariantId={selectedInvariantId}
        onSelectInvariant={(id) => onSelectInvariant?.(id)}
        selectedField={selectedField}
        onSelectField={(name) => onSelectField?.(name ?? null)}
      />

      <Stack direction="row" spacing={1}>
        <Button
          variant="contained"
          size="small"
          fullWidth
          disabled={busy}
          onClick={onAnalyze}
          title="Re-run full analysis (resets toward pipeline defaults)"
          sx={{ textTransform: 'none' }}
        >
          Analyze
        </Button>
        <Button
          variant="outlined"
          size="small"
          fullWidth
          disabled={busy || !onClearUnused}
          onClick={onClearUnused}
          title="Remove unused nodes/points off curves"
          sx={{ textTransform: 'none' }}
        >
          Clear unused
        </Button>
      </Stack>

      <Accordion disableGutters elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, '&:before': { display: 'none' } }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: 36, '& .MuiAccordionSummary-content': { my: 0.5 } }}>
          <Typography variant="caption" color="text.secondary">
            More actions
          </Typography>
        </AccordionSummary>
        <AccordionDetails sx={{ pt: 0 }}>
          <Stack spacing={0.75}>
            <Button size="small" variant="text" disabled={busy} onClick={onReload} sx={{ justifyContent: 'flex-start', textTransform: 'none' }}>
              Reload draft
            </Button>
            <Button size="small" variant="text" disabled={busy} onClick={onRepositionInvariants} sx={{ justifyContent: 'flex-start', textTransform: 'none' }}>
              Reposition invariants
            </Button>
            <Button size="small" variant="text" disabled={busy} onClick={onRestoreInvariants} sx={{ justifyContent: 'flex-start', textTransform: 'none' }} title="Reload I#/C# labels and merge missing invariants">
              Restore invariants
            </Button>
            <Button size="small" variant="text" disabled={busy || !onNormalizePoints} onClick={onNormalizePoints} sx={{ justifyContent: 'flex-start', textTransform: 'none' }} title="Join near-duplicates by priority">
              Normalize points
            </Button>
            <Button size="small" variant="text" disabled={busy} onClick={onGuidance} sx={{ justifyContent: 'flex-start', textTransform: 'none' }}>
              Refresh guidance
            </Button>
            {session.diagramKind && (
              <Typography variant="caption" color="text.secondary">
                Kind: {session.diagramKind}
              </Typography>
            )}
            <Divider />
            <ViewOptions opacity={opacity} onOpacity={onOpacity} session={session} />
          </Stack>
        </AccordionDetails>
      </Accordion>
    </Stack>
  );
}
