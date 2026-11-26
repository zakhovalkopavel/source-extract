import {
  Button,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useEffect, useState } from 'react';
import { seClient } from '../../shared/api/se-client';
import { viewInvariants } from './canvas/viewInvariants';
import type { ReviewSession } from './types';

type Props = {
  session: ReviewSession;
  invariantId: string | null;
  busy?: boolean;
  onSession: (s: ReviewSession) => void;
  onStatus: (msg: string) => void;
  onInvariantId?: (id: string) => void;
  onCancel?: () => void;
};

function formatComp(comp?: Record<string, number | null | undefined>): string {
  if (!comp) return '';
  return Object.entries(comp)
    .filter(([, v]) => v != null)
    .map(([k, v]) => `${k} ${Number(v).toFixed(1)}`)
    .join(' · ');
}

function isProvisionalId(id: string): boolean {
  return /^pt-\d+$/i.test(id);
}

export function InvariantEditPanel({
  session,
  invariantId,
  busy,
  onSession,
  onStatus,
  onInvariantId,
  onCancel,
}: Props) {
  const [pointType, setPointType] = useState<'invariant' | 'compound'>('invariant');
  const [id, setId] = useState('');
  const [temp, setTemp] = useState('');
  const [phases, setPhases] = useState('');
  const [reaction, setReaction] = useState('');
  const [saving, setSaving] = useState(false);

  const inv = viewInvariants(session.view).find((p) => p.id === invariantId) || null;

  useEffect(() => {
    if (!invariantId || !inv) {
      setId(invariantId && !isProvisionalId(invariantId) ? invariantId : '');
      setTemp('');
      setPhases('');
      setReaction('');
      setPointType('invariant');
      return;
    }
    setPointType(inv.pointRole === 'compound' ? 'compound' : 'invariant');
    setId(isProvisionalId(inv.id) ? '' : inv.id || '');
    setTemp(
      inv.temperature_C != null && Number.isFinite(Number(inv.temperature_C))
        ? String(inv.temperature_C)
        : '',
    );
    setPhases((inv.phases || []).join(', '));
    setReaction(
      inv.reaction && inv.reaction !== 'unknown' && inv.reaction !== 'compound'
        ? String(inv.reaction)
        : '',
    );
  }, [invariantId, inv?.id, inv?.temperature_C, inv?.reaction, inv?.pointRole, session.id, session.view]);

  if (!invariantId) return null;

  async function save() {
    if (!invariantId) return;
    const newId = id.trim();
    if (!newId) {
      onStatus('Enter a name before Save');
      return;
    }
    const tempRaw = temp.trim();
    const temperature_C = tempRaw === '' ? null : Number(tempRaw);
    if (tempRaw !== '' && !Number.isFinite(temperature_C)) {
      onStatus('Temperature °C must be a number (or leave blank)');
      return;
    }
    const phaseList = phases
      .split(/[,;]+/)
      .map((p) => p.trim())
      .filter(Boolean);
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        temperature_C,
        phases: phaseList,
        reaction: reaction.trim() || null,
        pointRole: pointType,
      };
      if (newId !== invariantId) body.newId = newId;
      const res = await seClient.post(
        `/review/sessions/${session.id}/invariants/${encodeURIComponent(invariantId)}`,
        body,
      );
      const next = res.data as ReviewSession;
      onSession(next);
      onInvariantId?.(newId);
      onStatus(
        `Saved ${pointType === 'compound' ? 'compound' : 'invariant'} ${newId}` +
          (temperature_C != null ? ` @ ${temperature_C}°C` : ''),
      );
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: unknown } }; message?: string };
      const detail = ax.response?.data?.detail;
      onStatus(
        detail != null
          ? `Save failed: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`
          : `Save failed: ${ax.message || String(e)}`,
      );
    } finally {
      setSaving(false);
    }
  }

  async function removePoint() {
    if (!invariantId) return;
    setSaving(true);
    try {
      const res = await seClient.delete(
        `/review/sessions/${session.id}/invariants/${encodeURIComponent(invariantId)}`,
      );
      onSession(res.data as ReviewSession);
      onStatus(`Deleted ${invariantId}`);
      onCancel?.();
    } catch (e: unknown) {
      onStatus(`Delete failed: ${String(e)}`);
    } finally {
      setSaving(false);
    }
  }

  async function cancel() {
    if (!invariantId) {
      onCancel?.();
      return;
    }
    // Discard a just-placed provisional point.
    if (isProvisionalId(invariantId) || (inv && isProvisionalId(String(inv.id)))) {
      await removePoint();
      return;
    }
    onCancel?.();
  }

  return (
    <Stack spacing={1} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1 }}>
      <Typography variant="subtitle2">Edit point</Typography>
      {!inv && (
        <Typography variant="caption" color="warning.main">
          Point not in view — try selecting again
        </Typography>
      )}
      <ToggleButtonGroup
        exclusive
        size="small"
        fullWidth
        value={pointType}
        onChange={(_, v) => v && setPointType(v)}
      >
        <ToggleButton value="invariant" sx={{ textTransform: 'none' }}>
          Invariant
        </ToggleButton>
        <ToggleButton value="compound" sx={{ textTransform: 'none' }}>
          Compound
        </ToggleButton>
      </ToggleButtonGroup>

      <TextField
        size="small"
        label="Name"
        value={id}
        onChange={(e) => setId(e.target.value)}
        placeholder={pointType === 'compound' ? 'e.g. A3S2, mullite' : 'e.g. cas-1170'}
        helperText="Label of this marker on the diagram (not the phase list)."
        onKeyDown={(e) => {
          if (e.key === 'Enter') void save();
        }}
        fullWidth
      />
      <TextField
        size="small"
        label="Temperature °C"
        type="number"
        value={temp}
        onChange={(e) => setTemp(e.target.value)}
        placeholder="blank = none"
        onKeyDown={(e) => {
          if (e.key === 'Enter') void save();
        }}
        fullWidth
      />
      <TextField
        size="small"
        label="Phases in equilibrium"
        value={phases}
        onChange={(e) => setPhases(e.target.value)}
        placeholder="silica, anorthite, …"
        helperText="Solids that meet at this point (optional). Different from Name."
        onKeyDown={(e) => {
          if (e.key === 'Enter') void save();
        }}
        fullWidth
      />
      <TextField
        size="small"
        label="Reaction type"
        value={reaction}
        onChange={(e) => setReaction(e.target.value)}
        placeholder="eutectic, peritectic, …"
        helperText="Optional invariant reaction kind (not the point name)."
        onKeyDown={(e) => {
          if (e.key === 'Enter') void save();
        }}
        fullWidth
      />
      {inv?.composition && (
        <Typography variant="caption" color="text.secondary">
          Composition: {formatComp(inv.composition) || '—'}
        </Typography>
      )}

      <Stack direction="row" spacing={1} sx={{ pt: 0.5 }}>
        <Button
          variant="contained"
          size="small"
          disabled={busy || saving}
          onClick={() => void save()}
          sx={{ textTransform: 'none' }}
        >
          Save
        </Button>
        <Button
          variant="outlined"
          size="small"
          disabled={busy || saving}
          onClick={() => void cancel()}
          sx={{ textTransform: 'none' }}
        >
          Cancel
        </Button>
        <Button
          variant="outlined"
          color="error"
          size="small"
          disabled={busy || saving}
          onClick={() => void removePoint()}
          sx={{ textTransform: 'none' }}
        >
          Delete
        </Button>
      </Stack>
    </Stack>
  );
}
