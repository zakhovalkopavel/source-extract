import { Button, CircularProgress, Stack, TextField, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { seClient, type JobDto } from '../shared/api/se-client';

export function JobsPage() {
  const { jobId: routeJobId } = useParams();
  const [jobId, setJobId] = useState(routeJobId || '');
  const activeId = routeJobId || jobId;

  const { data, isFetching, refetch } = useQuery({
    queryKey: ['job', activeId],
    enabled: Boolean(activeId),
    refetchInterval: (query) => {
      const state = (query.state.data as JobDto | undefined)?.state;
      return state === 'queued' || state === 'running' ? 1000 : false;
    },
    queryFn: async () => (await seClient.get(`/jobs/${activeId}`)).data as JobDto,
  });

  return (
    <Stack spacing={2}>
      <Typography variant="h5">Jobs</Typography>
      <Stack direction="row" spacing={1}>
        <TextField
          label="Job id"
          value={jobId}
          onChange={(e) => setJobId(e.target.value)}
          fullWidth
        />
        <Button variant="outlined" onClick={() => refetch()} disabled={!activeId}>
          Refresh
        </Button>
      </Stack>
      {isFetching && <CircularProgress size={24} />}
      {data && (
        <Stack spacing={1}>
          <Typography>
            {data.commandId} — <strong>{data.state}</strong>
            {data.exitCode != null ? ` (exit ${data.exitCode})` : ''}
          </Typography>
          {data.error && <Typography color="error">{data.error}</Typography>}
          <BoxLog lines={data.log || []} />
        </Stack>
      )}
    </Stack>
  );
}

function BoxLog({ lines }: { lines: string[] }) {
  return (
    <Typography
      component="pre"
      sx={{
        bgcolor: '#111',
        color: '#d6ffd6',
        p: 2,
        borderRadius: 1,
        overflow: 'auto',
        maxHeight: 480,
        fontSize: 13,
      }}
    >
      {(lines || []).join('\n') || '(no log yet)'}
    </Typography>
  );
}
