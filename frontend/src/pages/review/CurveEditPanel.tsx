import { Button, Stack, TextField, Typography } from '@mui/material';
import { useEffect, useState } from 'react';
import { seClient } from '../../shared/api/se-client';
import type { ReviewSession, SelectedCurve } from './types';

export type { SelectedCurve };

type Props = {
  session: ReviewSession;
  selected: SelectedCurve | null;
  busy?: boolean;
  onSession: (s: ReviewSession) => void;
  onStatus: (msg: string) => void;
  onSelectedIndex?: (index: number) => void;
};

export function CurveEditPanel({
  session,
  selected,
  busy,
  onSession,
  onStatus,
  onSelectedIndex,
}: Props) {
  const [temp, setTemp] = useState('');
  const [field, setField] = useState('');
  const [saving, setSaving] = useState(false);

  const iso =
    selected?.kind === 'isotherm'
      ? session.view?.isotherms?.find((c) => c.index === selected.index) ||
        session.view?.isotherms?.[selected.index]
      : null;
  const boundary =
    selected?.kind === 'boundary'
      ? session.view?.boundaries?.find((c) => c.index === selected.index) ||
        session.view?.boundaries?.[selected.index]
      : null;

  useEffect(() => {
    if (!selected) {
      setTemp('');
      setField('');
      return;
    }
    if (selected.kind === 'isotherm') {
      const row =
        session.view?.isotherms?.find((c) => c.index === selected.index) ||
        session.view?.isotherms?.[selected.index];
      setTemp(
        row?.temperature_C != null && Number.isFinite(Number(row.temperature_C))
          ? String(row.temperature_C)
          : '',
      );
      setField(String(row?.field || ''));
      return;
    }
    const row =
      session.view?.boundaries?.find((c) => c.index === selected.index) ||
      session.view?.boundaries?.[selected.index];
    const fields = row?.fields || [];
    setField(String(fields[0] || ''));
    setTemp('');
  }, [selected?.kind, selected?.index, session.id, session.view]);

  if (!selected) return null;

  async function save() {
    if (!selected) return;
    setSaving(true);
    try {
      if (selected.kind === 'isotherm') {
        const temperature_C = Number(temp);
        if (!Number.isFinite(temperature_C)) {
          onStatus('Set isotherm temperature (°C) before Save');
          return;
        }
        const name = field.trim();
        if (!name) {
          onStatus('Set isotherm field name before Save');
          return;
        }
        const res = await seClient.post(`/review/sessions/${session.id}/isotherms/update`, {
          contourIndex: selected.index,
          field: name,
          temperature_C,
        });
        const next = res.data as ReviewSession;
        onSession(next);
        const build = next.lastIsothermBuild as { index?: number; removedCount?: number } | undefined;
        const newIndex = build?.index ?? selected.index;
        onSelectedIndex?.(newIndex);
        const removed = build?.removedCount || 0;
        onStatus(
          `Saved isotherm ${name} @ ${temperature_C}°C` +
            (removed > 0 ? ` — removed ${removed} crossed` : ''),
        );
        return;
      }
      const res = await seClient.post(`/review/sessions/${session.id}/boundaries/update`, {
        contourIndex: selected.index,
        fields: [field.trim() || null, null],
      });
      onSession(res.data as ReviewSession);
      onStatus(`Saved boundary #${selected.index}`);
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

  const missingTemp =
    selected.kind === 'isotherm' &&
    (iso?.temperature_C == null || !Number.isFinite(Number(iso.temperature_C)));

  return (
    <Stack spacing={1} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1 }}>
      <Typography variant="subtitle2">
        Curve edit — {selected.kind} #{selected.index}
      </Typography>
      {selected.kind === 'isotherm' ? (
        <>
          {missingTemp && (
            <Typography variant="caption" color="error">
              Temperature required — set °C and Save
            </Typography>
          )}
          <TextField
            size="small"
            label="Temperature °C"
            type="number"
            value={temp}
            onChange={(e) => setTemp(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void save();
            }}
            error={missingTemp && temp === ''}
            fullWidth
          />
          <TextField
            size="small"
            label="Field"
            value={field}
            onChange={(e) => setField(e.target.value)}
            placeholder={session.phases?.[0] || 'phase'}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void save();
            }}
            fullWidth
          />
        </>
      ) : (
        <TextField
          size="small"
          label="Field A"
          value={field}
          onChange={(e) => setField(e.target.value)}
          fullWidth
        />
      )}
      {!iso && selected.kind === 'isotherm' && (
        <Typography variant="caption" color="warning.main">
          Isotherm not in view
        </Typography>
      )}
      {!boundary && selected.kind === 'boundary' && (
        <Typography variant="caption" color="warning.main">
          Boundary not in view
        </Typography>
      )}
      <Button
        variant="contained"
        size="small"
        disabled={busy || saving}
        onClick={() => void save()}
      >
        Save curve
      </Button>
    </Stack>
  );
}
