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
import { IsothermLegend } from './review/IsothermLegend';
import { JobOverlay } from './review/JobOverlay';
import { ReviewSidePanel } from './review/ReviewSidePanel';
import { ToolTiles, type SeedCurveKind } from './review/ToolTiles';
import type { ReviewSession, SelectedCurve, ToolMode } from './review/types';
import { resolveCanvasTool } from './review/types';

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

const ADAPTER_ID = 'phase-diagrams';

export function ReviewPage() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState('');
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [tool, setTool] = useState<ToolMode>('select');
  const [seedKind, setSeedKind] = useState<SeedCurveKind>('boundary');
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
  const cancelSeedFnRef = useRef<() => void>(() => {});

  const canvasTool = resolveCanvasTool(tool, seedKind);

  const registerDelete = useCallback((fn: () => void) => {
    deleteFnRef.current = fn;
  }, []);

  const registerCommitSeed = useCallback((fn: () => void) => {
    commitSeedFnRef.current = fn;
  }, []);

  const registerCancelSeed = useCallback((fn: () => void) => {
    cancelSeedFnRef.current = fn;
  }, []);

  function requestDeleteSelection() {
    deleteFnRef.current();
  }

  function requestCommitSeed() {
    commitSeedFnRef.current();
  }

  function requestCancelSeed() {
    cancelSeedFnRef.current();
    setSeedCount(0);
    setTool('select');
    setStatus('Seed cancelled');
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
      // Keep external remap index aligned with the curve the user just clicked.
      if (info.curve) {
        setExternalCurveIndex(info.curve.index);
      } else if (!info.invariantId) {
        setExternalCurveIndex(null);
      }
      if (info.invariantId) {
        setFocusInvariantId(info.invariantId);
        setFocusFieldName(null);
        // After placing a point, leave place-mode so the next click does not drop another.
        setTool((t) => (t === 'add-invariant' ? 'select' : t));
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

  async function doUndo() {
    if (!session) return;
    const res = await seClient.post(`/review/sessions/${session.id}/undo`);
    setSession(res.data as ReviewSession);
    setStatus('Undo');
  }

  return (
    <Stack
      direction={{ xs: 'column', md: 'row' }}
      spacing={1.5}
      alignItems="stretch"
      sx={{ minHeight: '82vh' }}
    >
      {/* Left: systems only */}
      <Stack spacing={1} sx={{ width: { xs: '100%', md: 260 }, flexShrink: 0 }}>
        <Typography variant="subtitle1" fontWeight={700}>
          Systems
        </Typography>
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
            maxHeight: { md: '78vh' },
            overflow: 'auto',
            flex: 1,
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
                {s.draftSource} · {s.diagramKind} · {s.n_boundaries ?? 0}b / {s.n_isotherms ?? 0}i
              </Typography>
            </Button>
          ))}
        </Box>
      </Stack>

      {/* Center: tools + canvas + isotherm legend */}
      <Stack spacing={1} flex={1} minWidth={0} minHeight={0}>
        {!session ? (
          <Typography color="text.secondary" sx={{ mt: 2 }}>
            Pick a system to edit the diagram. Use Sources in the header to upload or choose a
            source. Confirm accepts the reviewed dataset.
          </Typography>
        ) : (
          <>
            <ToolTiles
              tool={tool === 'seed-boundary' || tool === 'seed-isotherm' ? 'seed' : tool}
              onTool={handleTool}
              seedKind={seedKind}
              onSeedKind={setSeedKind}
              seedCount={seedCount}
              canDelete={canDelete}
              selectionCount={selectionCount}
              deleteLabel={
                selectedCurve
                  ? `Delete ${selectedCurve.kind} #${selectedCurve.index}`
                  : undefined
              }
              busy={openSystem.isPending}
              undoDepth={session.undoDepth ?? 0}
              canConfirm={session.validation?.canConfirm !== false}
              onUndo={() => void doUndo()}
              onConfirm={async () => {
                const res = await seClient.post(`/review/sessions/${session.id}/confirm`);
                const data = res.data as { session?: ReviewSession };
                if (data.session) setSession(data.session);
                setStatus('Confirmed');
              }}
              onDeleteSelection={requestDeleteSelection}
              onCommitSeed={requestCommitSeed}
              onCancelSeed={requestCancelSeed}
              status={
                status ||
                `${session.systemId} · ${session.draftSource || ''} · undo ${session.undoDepth ?? 0}`
              }
            />

            <Stack direction="row" spacing={1} sx={{ flex: 1, minHeight: 0 }} alignItems="stretch">
              <Box sx={{ flex: 1, minWidth: 0, minHeight: 420 }}>
                <ReviewCanvas
                  session={session}
                  tool={canvasTool}
                  opacity={opacity}
                  onSession={setSession}
                  onStatus={setStatus}
                  externalCurveIndex={externalCurveIndex}
                  invariantDraftId={invariantId}
                  focusInvariantId={focusInvariantId}
                  focusFieldName={focusFieldName}
                  onRegisterDelete={registerDelete}
                  onRegisterCommitSeed={registerCommitSeed}
                  onRegisterCancelSeed={registerCancelSeed}
                  seedField={seedField}
                  seedTemperatureC={seedTemperatureC}
                  onSeedCount={setSeedCount}
                  onSelectionChange={handleSelectionChange}
                  onUndo={() => void doUndo()}
                  onSeedCommitted={(curve) => {
                    setSelectedCurve(curve);
                    setExternalCurveIndex(curve.index);
                    setFocusInvariantId(null);
                    setTool('select');
                  }}
                />
              </Box>
              <IsothermLegend session={session} />
              <ReviewSidePanel
                session={session}
                busy={openSystem.isPending}
                selectedCurve={selectedCurve}
                onCurveIndexChange={(index) => {
                  setSelectedCurve((prev) => (prev ? { ...prev, index } : null));
                  setExternalCurveIndex(index);
                }}
                onClearCurve={() => {
                  setSelectedCurve(null);
                  setExternalCurveIndex(null);
                }}
                onDeleteCurve={requestDeleteSelection}
                selectedInvariantId={focusInvariantId}
                onSelectInvariant={(id) => {
                  setFocusInvariantId(id);
                  if (id) {
                    setFocusFieldName(null);
                    setTool('select');
                  }
                }}
                selectedField={focusFieldName}
                onSelectField={(name) => {
                  setFocusFieldName(name);
                  if (name) {
                    setFocusInvariantId(null);
                    setTool('select');
                  }
                }}
                onSession={setSession}
                onStatus={setStatus}
                opacity={opacity}
                onOpacity={setOpacity}
                onAnalyze={() => void runAnalyze()}
                onClearUnused={async () => {
                  const res = await seClient.post(
                    `/review/sessions/${session.id}/points/clear-unused`,
                  );
                  const next = res.data as ReviewSession;
                  setSession(next);
                  const c = next.lastClearUnused;
                  setStatus(
                    c
                      ? `Cleared unused: −${c.removedNodes ?? 0} nodes, −${c.removedInvariants ?? 0} invariants`
                      : 'Cleared unused points',
                  );
                }}
                onNormalizePoints={async () => {
                  const res = await seClient.post(
                    `/review/sessions/${session.id}/points/normalize`,
                  );
                  const next = res.data as ReviewSession;
                  setSession(next);
                  const n = next.lastNormalizePoints;
                  setStatus(
                    n
                      ? `Normalized: ${n.clusters ?? 0} clusters, replaced ${n.replaced ?? 0}`
                      : 'Normalized points',
                  );
                }}
                onRepositionInvariants={async () => {
                  const res = await seClient.post(
                    `/review/sessions/${session.id}/invariants/reposition`,
                  );
                  const next = res.data as ReviewSession;
                  setSession(next);
                  setStatus('Invariants repositioned from composition');
                }}
                onRestoreInvariants={async () => {
                  const res = await seClient.post(
                    `/review/sessions/${session.id}/invariants/restore`,
                  );
                  const next = res.data as ReviewSession;
                  setSession(next);
                  setStatus('Invariants restored from disk draft');
                }}
                onReload={async () => {
                  const res = await seClient.post(
                    `/review/sessions/${session.id}/reload-draft`,
                    {},
                  );
                  setSession(res.data as ReviewSession);
                  setStatus('Draft reloaded');
                }}
                onGuidance={async () => {
                  const res = await seClient.post(
                    `/review/sessions/${session.id}/guidance/refresh`,
                  );
                  setSession(res.data as ReviewSession);
                }}
                seedField={seedField}
                onSeedField={setSeedField}
                seedTemperatureC={seedTemperatureC}
                onSeedTemperatureC={setSeedTemperatureC}
                seedingIsotherm={tool === 'seed' && seedKind === 'isotherm'}
              />
            </Stack>
          </>
        )}

        {session?.guidance?.cards && session.guidance.cards.length > 0 && (
          <Box
            sx={{
              maxHeight: 100,
              overflow: 'auto',
              borderTop: '1px solid',
              borderColor: 'divider',
              pt: 1,
            }}
          >
            {session.guidance.cards.slice(0, 4).map((c) => (
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
