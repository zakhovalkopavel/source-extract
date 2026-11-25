import { Button, Stack, TextField, Typography } from '@mui/material';
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
};

function formatComp(comp?: Record<string, number | null | undefined>): string {
  if (!comp) return '';
  return Object.entries(comp)
    .filter(([, v]) => v != null)
    .map(([k, v]) => `${k} ${Number(v).toFixed(1)}`)
    .join(' · ');
}

export function InvariantEditPanel({
  session,
  invariantId,
  busy,
  onSession,
  onStatus,
  onInvariantId,
}: Props) {
  const [id, setId] = useState('');
  const [temp, setTemp] = useState('');
  const [phases, setPhases] = useState('');
  const [reaction, setReaction] = useState('');
  const [saving, setSaving] = useState(false);

  const inv = viewInvariants(session.view).find((p) => p.id === invariantId) || null;

  useEffect(() => {
    if (!invariantId || !inv) {
      setId(invariantId || '');
      setTemp('');
      setPhases('');
      setReaction('');
      return;
    }
    setId(inv.id || '');
    setTemp(
      inv.temperature_C != null && Number.isFinite(Number(inv.temperature_C))
        ? String(inv.temperature_C)
        : '',
    );
    setPhases((inv.phases || []).join(', '));
    setReaction(String(inv.reaction || ''));
  }, [invariantId, inv?.id, inv?.temperature_C, inv?.reaction, session.id, session.view]);

  if (!invariantId) return null;

  async function save() {
    if (!invariantId) return;
    const newId = id.trim();
    if (!newId) {
      onStatus('Invariant id cannot be empty');
      return;
    }
    const tempRaw = temp.trim();
    const temperature_C = tempRaw === '' ? null : Number(tempRaw);
    if (tempRaw !== '' && !Number.isFinite(temperature_C)) {
      onStatus('Invariant °C must be a number (or leave blank)');
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
      };
      if (newId !== invariantId) body.newId = newId;
      const res = await seClient.post(
        `/review/sessions/${session.id}/invariants/${encodeURIComponent(invariantId)}`,
        body,
      );
      const next = res.data as ReviewSession;
      onSession(next);
      onInvariantId?.(newId);
      const saved = viewInvariants(next.view).find((p) => p.id === newId);
      const savedRole = saved?.pointRole === 'compound' ? 'compound' : 'invariant';
      onStatus(
        `Saved ${savedRole} ${newId}` +
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

  const role = inv?.pointRole === 'compound' ? 'compound' : 'invariant';

  return (
    <Stack spacing={1} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1 }}>
      <Typography variant="subtitle2">
        {role === 'compound' ? 'Compound point' : 'Invariant point'}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {role === 'compound'
          ? 'Named formula / compound (e.g. A3S2). Same edit tools as invariants.'
          : 'Composition + melting °C (eutectic / peritectic / …). Add a special name to mark as compound.'}
      </Typography>
      {!inv && (
        <Typography variant="caption" color="warning.main">
          Point not in view — try selecting again
        </Typography>
      )}
      <TextField
        size="small"
        label={role === 'compound' ? 'Compound name / notation' : 'Id / notation'}
        value={id}
        onChange={(e) => setId(e.target.value)}
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
        placeholder="blank = clear"
        onKeyDown={(e) => {
          if (e.key === 'Enter') void save();
        }}
        fullWidth
      />
      <TextField
        size="small"
        label="Phases"
        value={phases}
        onChange={(e) => setPhases(e.target.value)}
        placeholder="silica, anorthite, …"
        helperText="Comma-separated"
        onKeyDown={(e) => {
          if (e.key === 'Enter') void save();
        }}
        fullWidth
      />
      <TextField
        size="small"
        label="Reaction"
        value={reaction}
        onChange={(e) => setReaction(e.target.value)}
        placeholder="eutectic | peritectic | …"
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
      {inv?.provenance && (
        <Typography variant="caption" color="text.secondary">
          Provenance: {inv.provenance}
        </Typography>
      )}
      <Button
        variant="contained"
        size="small"
        disabled={busy || saving}
        onClick={() => void save()}
      >
        Save point
      </Button>
    </Stack>
  );
}
