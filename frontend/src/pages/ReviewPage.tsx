import {
  Box,
  Button,
  CircularProgress,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo, useRef, useState } from 'react';
import { seClient } from '../shared/api/se-client';
import { DEFAULT_VIEW_OPACITY, type ViewOpacity } from './review/canvas/curveStyles';
import { ReviewCanvas } from './review/canvas/ReviewCanvas';
import { JobOverlay } from './review/JobOverlay';
import { ToolsRail } from './review/ToolsRail';
import type { ReviewSession, SelectedCurve, ToolMode } from './review/types';

type SystemRow = {
  id: string;
  system?: string;
  diagramKind?: string;
  draftSource?: string;
  availableSources?: string[];
  n_boundaries?: number;
  n_isotherms?: number;
  n_invariants?: number;
  n_liquidus?: number;
  contentScore?: number;
  hasImage?: boolean;
};

type SessionRow = {
  id: string;
  systemId: string;
  system?: string;
  draftSource?: string;
  status?: string;
  n_boundaries?: number;
};

const ADAPTER_ID = 'phase-diagrams';

export function ReviewPage() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState('');
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [tool, setTool] = useState<ToolMode>('move');
  const [opacity, setOpacity] = useState<ViewOpacity>({ ...DEFAULT_VIEW_OPACITY });
  const [status, setStatus] = useState('');
  const [jobOpen, setJobOpen] = useState(false);
  const [jobTitle, setJobTitle] = useState('');
  const [jobLog, setJobLog] = useState<string[]>([]);
  const [selectionCount, setSelectionCount] = useState(0);
  const [canDelete, setCanDelete] = useState(false);
  const [selectedCurve, setSelectedCurve] = useState<SelectedCurve | null>(null);
  const [externalCurveIndex, setExternalCurveIndex] = useState<number | null>(null);
  const [invariantId, setInvariantId] = useState('');
  const [focusInvariantId, setFocusInvariantId] = useState<string | null>(null);
  const [focusFieldName, setFocusFieldName] = useState<string | null>(null);
  const [seedCount, setSeedCount] = useState(0);
  const [seedField, setSeedField] = useState('');
  const [seedTemperatureC, setSeedTemperatureC] = useState('1500');
  const deleteFnRef = useRef<() => void>(() => {});
  const commitSeedFnRef = useRef<() => void>(() => {});

  const registerDelete = useCallback((fn: () => void) => {
    deleteFnRef.current = fn;
  }, []);

  const registerCommitSeed = useCallback((fn: () => void) => {
    commitSeedFnRef.current = fn;
  }, []);

  function requestDeleteSelection() {
    deleteFnRef.current();
  }

  function requestCommitSeed() {
    commitSeedFnRef.current();
  }

  const handleSelectionChange = useCallback(
    (info: {
      pointCount: number;
      curve: SelectedCurve | null;
      canDelete: boolean;
      invariantId?: string | null;
      fieldName?: string | null;
    }) => {
      setSelectionCount(info.pointCount);
      setCanDelete(info.canDelete);
      setSelectedCurve((prev) => {
        const next = info.curve;
        if (!prev && !next) return prev;
        if (prev && next && prev.kind === next.kind && prev.index === next.index) {
          return prev;
        }
        return next;
      });
      if (info.invariantId) {
        setFocusInvariantId(info.invariantId);
        setFocusFieldName(null);
        return;
      }
      if (info.fieldName) {
        setFocusFieldName(info.fieldName);
        setFocusInvariantId(null);
        return;
      }
      setFocusFieldName(null);
      if (info.curve || info.pointCount > 0) {
        setFocusInvariantId(null);
      }
    },
    [],
  );

  function handleTool(next: ToolMode) {
    // Clicking Delete tool with a selection removes it (diagram-review parity).
    if (next === 'delete' && canDelete) {
      requestDeleteSelection();
      setTool('delete');
      return;
    }
    setTool(next);
  }

  const systems = useQuery({
    queryKey: ['systems', ADAPTER_ID],
    queryFn: async () =>
      (await seClient.get(`/adapters/${ADAPTER_ID}/systems`)).data as SystemRow[],
  });

  const sessions = useQuery({
    queryKey: ['review-sessions'],
    queryFn: async () => {
      const data = (await seClient.get('/review/sessions')).data as {
        sessions?: SessionRow[];
      };
      return data.sessions || [];
    },
  });

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const rows = systems.data || [];
    if (!q) return rows;
    return rows.filter(
      (s) =>
        s.id.toLowerCase().includes(q) ||
        String(s.system || '')
          .toLowerCase()
          .includes(q) ||
        String(s.draftSource || '')
          .toLowerCase()
          .includes(q),
    );
  }, [systems.data, filter]);

  const openSystem = useMutation({
    mutationFn: async (row: SystemRow) => {
      const body = {
        systemId: row.id,
        draftSource: row.draftSource || null,
        forceNew: false,
      };
      return (await seClient.post('/review/sessions', body)).data as ReviewSession;
    },
    onSuccess: (s) => {
      setSession(s);
      setSeedField((prev) => prev || s.phases?.[0] || '');
      setSeedCount(0);
      setStatus(`Opened ${s.systemId}`);
      void qc.invalidateQueries({ queryKey: ['review-sessions'] });
    },
    onError: (e) => setStatus(String(e)),
  });

  const openSession = useMutation({
    mutationFn: async (id: string) =>
      (await seClient.get(`/review/sessions/${id}`)).data as ReviewSession,
    onSuccess: (s) => {
      setSession(s);
      setSeedField((prev) => prev || s.phases?.[0] || '');
      setSeedCount(0);
      setStatus(`Resumed ${s.systemId}`);
    },
  });

  async function pollJob(jobId: string) {
    for (;;) {
      const job = (await seClient.get(`/jobs/${jobId}`)).data as {
        state: string;
        log?: string[];
        exitCode?: number | null;
      };
      setJobLog(job.log || []);
      setJobTitle(`Job ${job.state}`);
      if (['succeeded', 'failed', 'cancelled'].includes(String(job.state).toLowerCase())) {
        return job;
      }
      await new Promise((r) => setTimeout(r, 1200));
    }
  }

  async function runAnalyze() {
    if (!session) return;
    setJobOpen(true);
    setJobTitle(`Analyzing ${session.systemId}…`);
    setJobLog([]);
    try {
      const started = (
        await seClient.post('/review/analyze', {
          systemId: session.systemId,
          adapterId: ADAPTER_ID,
          sessionId: session.id,
          force: false,
        })
      ).data as { job: { id: string; jobId?: string } };
      const jobId = started.job.jobId || started.job.id;
      const done = await pollJob(jobId);
      if (String(done.state).toLowerCase() === 'succeeded') {
        const reloaded = (
          await seClient.post(`/review/sessions/${session.id}/analyze-reload`)
        ).data as { session: ReviewSession };
        setSession(reloaded.session);
        setStatus('Analyze complete — draft reloaded');
      } else {
        setStatus(`Analyze ${done.state}`);
      }
    } catch (e) {
      setStatus(String(e));
    }
  }

  return (
    <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems="stretch" sx={{ minHeight: '78vh' }}>
      <Stack spacing={1.5} sx={{ width: { xs: '100%', md: 300 }, flexShrink: 0 }}>
        <Typography variant="h5">Systems</Typography>
        <TextField
          size="small"
          label="Filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          fullWidth
        />
        {systems.isLoading && <CircularProgress size={22} />}
        <Box
          sx={{
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            maxHeight: '42vh',
            overflow: 'auto',
          }}
        >
          {filtered.map((s) => (
            <Button
              key={s.id}
              fullWidth
              onClick={() => openSystem.mutate(s)}
              disabled={openSystem.isPending}
              sx={{
                display: 'block',
                textAlign: 'left',
                borderRadius: 0,
                px: 1.5,
                py: 1,
                bgcolor: session?.systemId === s.id ? 'action.selected' : 'transparent',
                borderBottom: '1px solid',
                borderColor: 'divider',
                textTransform: 'none',
              }}
            >
              <Typography fontWeight={600} noWrap>
                {s.system || s.id}
              </Typography>
              <Typography variant="caption" color="text.secondary" display="block" noWrap>
                {s.id} · {s.draftSource} · {s.diagramKind} · {s.n_boundaries ?? 0}b /{' '}
                {s.n_isotherms ?? 0}i
              </Typography>
            </Button>
          ))}
        </Box>

        <Typography variant="subtitle1">Sessions</Typography>
        <Box
          sx={{
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            maxHeight: '28vh',
            overflow: 'auto',
          }}
        >
          {(sessions.data || []).map((s) => (
            <Button
              key={s.id}
              fullWidth
              onClick={() => openSession.mutate(s.id)}
              sx={{
                display: 'block',
                textAlign: 'left',
                borderRadius: 0,
                px: 1.5,
                py: 0.75,
                bgcolor: session?.id === s.id ? 'action.selected' : 'transparent',
                borderBottom: '1px solid',
                borderColor: 'divider',
                textTransform: 'none',
              }}
            >
              <Typography fontWeight={600} noWrap variant="body2">
                {s.system || s.systemId}
              </Typography>
              <Typography variant="caption" color="text.secondary" noWrap display="block">
                {s.draftSource} · {s.status}
              </Typography>
            </Button>
          ))}
        </Box>
      </Stack>

      <Stack spacing={1} flex={1} minWidth={0} minHeight={0}>
        <Stack direction="row" spacing={2} alignItems="center">
          <Typography variant="h5">Review</Typography>
          {session && (
            <Typography variant="body2" color="text.secondary">
              {session.systemId} · {session.draftSource} · undo {session.undoDepth ?? 0}
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary">
            {status}
          </Typography>
        </Stack>
        {!session && (
          <Typography color="text.secondary">
            Open a system to edit boundaries, isotherms, invariants (binary + ternary). Analyze runs
            through SE jobs; Confirm writes the reviewed dataset.
          </Typography>
        )}
        {session && (
          <Stack direction={{ xs: 'column', lg: 'row' }} spacing={1.5} sx={{ flex: 1, minHeight: 0 }}>
            <ReviewCanvas
              session={session}
              tool={tool}
              opacity={opacity}
              onSession={setSession}
              onStatus={setStatus}
              externalCurveIndex={externalCurveIndex}
              invariantDraftId={invariantId}
              focusInvariantId={focusInvariantId}
              focusFieldName={focusFieldName}
              onRegisterDelete={registerDelete}
              onRegisterCommitSeed={registerCommitSeed}
              seedField={seedField}
              seedTemperatureC={seedTemperatureC}
              onSeedCount={setSeedCount}
              onSelectionChange={handleSelectionChange}
              onUndo={async () => {
                const res = await seClient.post(`/review/sessions/${session.id}/undo`);
                setSession(res.data as ReviewSession);
              }}
            />
            <ToolsRail
              tool={tool}
              onTool={handleTool}
              onDeleteSelection={requestDeleteSelection}
              selectionCount={selectionCount}
              canDelete={canDelete}
              selectedCurve={selectedCurve}
              onCurveIndexChange={(index) => {
                setSelectedCurve((prev) => (prev ? { ...prev, index } : null));
                setExternalCurveIndex(index);
              }}
              invariantId={invariantId}
              onInvariantId={setInvariantId}
              selectedInvariantId={focusInvariantId}
              onSelectInvariant={(id) => {
                setFocusInvariantId(id);
                setFocusFieldName(null);
                setTool('select');
              }}
              selectedField={focusFieldName}
              onSelectField={(name) => {
                setFocusFieldName(name);
                setFocusInvariantId(null);
                setTool('select');
              }}
              onSession={setSession}
              onStatus={setStatus}
              session={session}
              busy={openSystem.isPending}
              opacity={opacity}
              onOpacity={setOpacity}
              onUndo={async () => {
                const res = await seClient.post(`/review/sessions/${session.id}/undo`);
                setSession(res.data as ReviewSession);
              }}
              onAnalyze={() => void runAnalyze()}
              onRepositionInvariants={async () => {
                const res = await seClient.post(
                  `/review/sessions/${session.id}/invariants/reposition`,
                );
                const next = res.data as ReviewSession;
                setSession(next);
                const n = next.lastInvariantReposition?.count;
                setStatus(
                  n != null
                    ? `Repositioned ${n} invariant(s) from composition (inside triangle)`
                    : 'Invariants repositioned from composition',
                );
              }}
              onRestoreInvariants={async () => {
                const res = await seClient.post(
                  `/review/sessions/${session.id}/invariants/restore`,
                );
                const next = res.data as ReviewSession;
                setSession(next);
                const r = next.lastInvariantRestore;
                setStatus(
                  r
                    ? `Restored invariants from ${r.draftSource}: +${r.added} added, ${r.filledTemperature} °C filled, ${r.nodeCount} nodes (total ${r.total})`
                    : 'Invariants restored from disk draft',
                );
              }}
              seedCount={seedCount}
              seedField={seedField}
              onSeedField={setSeedField}
              seedTemperatureC={seedTemperatureC}
              onSeedTemperatureC={setSeedTemperatureC}
              onCommitSeed={requestCommitSeed}
              onNormalizePoints={async () => {
                const res = await seClient.post(
                  `/review/sessions/${session.id}/points/normalize`,
                );
                const next = res.data as ReviewSession;
                setSession(next);
                const n = next.lastNormalizePoints;
                setStatus(
                  n
                    ? `Normalized points: ${n.clusters ?? 0} cluster(s), replaced ${n.replaced ?? 0}, joined ${n.joined ?? 0} curve(s)`
                    : 'Normalized points',
                );
              }}
              onClearUnused={async () => {
                const res = await seClient.post(
                  `/review/sessions/${session.id}/points/clear-unused`,
                );
                const next = res.data as ReviewSession;
                setSession(next);
                const c = next.lastClearUnused;
                setStatus(
                  c
                    ? `Cleared unused: −${c.removedNodes ?? 0} nodes, −${c.removedInvariants ?? 0} invariants (kept ${c.keptNodes ?? 0} / ${c.keptInvariants ?? 0})`
                    : 'Cleared unused points',
                );
              }}
              onConfirm={async () => {
                const res = await seClient.post(`/review/sessions/${session.id}/confirm`);
                const data = res.data as { session?: ReviewSession };
                if (data.session) setSession(data.session);
                setStatus('Confirmed');
              }}
              onGuidance={async () => {
                const res = await seClient.post(`/review/sessions/${session.id}/guidance/refresh`);
                setSession(res.data as ReviewSession);
              }}
              onReload={async () => {
                const res = await seClient.post(`/review/sessions/${session.id}/reload-draft`, {});
                setSession(res.data as ReviewSession);
              }}
            />
          </Stack>
        )}
        {session?.guidance?.cards && session.guidance.cards.length > 0 && (
          <Box sx={{ maxHeight: 140, overflow: 'auto', borderTop: '1px solid', borderColor: 'divider', pt: 1 }}>
            {session.guidance.cards.slice(0, 6).map((c) => (
              <Typography key={String(c.id)} variant="caption" display="block">
                <strong>{String(c.title)}</strong> — {String(c.body)}
              </Typography>
            ))}
          </Box>
        )}
      </Stack>

      <JobOverlay open={jobOpen} title={jobTitle} log={jobLog} onClose={() => setJobOpen(false)} />
    </Stack>
  );
}
