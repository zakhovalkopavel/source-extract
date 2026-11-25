import { Box, Stack, Typography } from '@mui/material';
import { FIELD_PALETTE } from './canvas/curveStyles';
import { viewInvariants } from './canvas/viewInvariants';
import type { ReviewSession } from './types';

type Props = {
  session: ReviewSession;
  selectedInvariantId?: string | null;
  onSelectInvariant?: (id: string) => void;
  selectedField?: string | null;
  onSelectField?: (name: string) => void;
};

function formatComp(comp?: Record<string, number | null | undefined>): string {
  if (!comp) return '';
  return Object.entries(comp)
    .filter(([, v]) => v != null)
    .map(([k, v]) => `${k} ${Number(v).toFixed(1)}`)
    .join(' · ');
}

export function ReviewLists({
  session,
  selectedInvariantId,
  onSelectInvariant,
  selectedField = null,
  onSelectField,
}: Props) {
  const viewFields = session.view?.fields || [];
  const fields =
    viewFields.length > 0
      ? viewFields
      : (session.phases || []).map((name, colorIndex) => ({
          name,
          colorIndex,
          polygons: [] as number[][][],
        }));
  const invariants = viewInvariants(session.view);

  return (
    <Stack spacing={1}>
      <Box>
        <Typography variant="subtitle2">Fields ({fields.length})</Typography>
        <Box sx={{ maxHeight: 160, overflow: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
          {fields.length === 0 && (
            <Typography variant="caption" color="text.secondary" sx={{ p: 0.75, display: 'block' }}>
              No fields yet
            </Typography>
          )}
          {fields.map((f) => {
            const sel = selectedField === f.name;
            const hasPoly = (f.polygons || []).length > 0;
            return (
              <Box
                key={f.name}
                onClick={() => onSelectField?.(f.name)}
                sx={{
                  px: 0.75,
                  py: 0.5,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.75,
                  bgcolor: sel ? 'action.selected' : 'transparent',
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                  '&:hover': { bgcolor: 'action.hover' },
                }}
              >
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    flexShrink: 0,
                    borderRadius: 0.5,
                    bgcolor: FIELD_PALETTE[(f.colorIndex ?? 0) % FIELD_PALETTE.length],
                    opacity: hasPoly ? 0.9 : 0.35,
                    outline: sel ? '2px solid' : 'none',
                    outlineColor: 'primary.main',
                  }}
                />
                <Typography variant="caption" fontWeight={sel ? 700 : 500} noWrap>
                  {f.name}
                  {!hasPoly ? (
                    <Box component="span" sx={{ color: 'text.secondary', ml: 0.5 }}>
                      (no region)
                    </Box>
                  ) : null}
                </Typography>
              </Box>
            );
          })}
        </Box>
      </Box>
      <Box>
        <Typography variant="subtitle2">Points ({invariants.length})</Typography>
        <Box sx={{ maxHeight: 220, overflow: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
          {invariants.length === 0 && (
            <Typography variant="caption" color="text.secondary" sx={{ p: 0.75, display: 'block' }}>
              None — click a C# ring or use Add invariant
            </Typography>
          )}
          {invariants.map((inv) => {
            const sel = selectedInvariantId === inv.id;
            const missing = inv.temperature_C == null;
            const role = inv.pointRole === 'compound' ? 'compound' : 'invariant';
            return (
              <Box
                key={inv.id}
                onClick={() => onSelectInvariant?.(inv.id)}
                sx={{
                  px: 0.75,
                  py: 0.5,
                  cursor: 'pointer',
                  bgcolor: sel ? 'action.selected' : 'transparent',
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                  '&:hover': { bgcolor: 'action.hover' },
                }}
              >
                <Typography variant="caption" fontWeight={600} display="block" noWrap>
                  {inv.label || inv.notation || inv.id}
                  <Box component="span" sx={{ color: 'text.secondary', ml: 0.5 }}>
                    {role === 'compound' ? 'compound' : 'invariant'}
                  </Box>
                  {inv.label && inv.label !== inv.id ? (
                    <Box component="span" sx={{ color: 'text.secondary', ml: 0.5 }}>
                      ({inv.id})
                    </Box>
                  ) : null}
                  {missing ? (
                    <Box component="span" sx={{ color: 'error.main', ml: 0.5 }}>
                      no °C
                    </Box>
                  ) : (
                    <Box component="span" sx={{ color: 'text.secondary', ml: 0.5 }}>
                      {inv.temperature_C}°C
                    </Box>
                  )}
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block" noWrap>
                  {formatComp(inv.composition)}
                </Typography>
              </Box>
            );
          })}
        </Box>
      </Box>
    </Stack>
  );
}
