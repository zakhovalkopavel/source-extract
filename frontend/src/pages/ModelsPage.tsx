import { CircularProgress, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { seClient } from '../shared/api/se-client';

export function ModelsPage() {
  const profiles = useQuery({
    queryKey: ['profiles'],
    queryFn: async () => (await seClient.get('/models/profiles')).data as Array<Record<string, string>>,
  });
  const calls = useQuery({
    queryKey: ['llm-calls'],
    queryFn: async () => (await seClient.get('/models/calls')).data as Array<Record<string, unknown>>,
  });

  if (profiles.isLoading) return <CircularProgress />;

  return (
    <Stack spacing={2}>
      <Typography variant="h5">Models</Typography>
      <Typography variant="h6">Profiles</Typography>
      {(profiles.data || []).map((p) => (
        <Typography key={p.id}>
          {p.id} — {p.defaultProvider}: {p.description}
        </Typography>
      ))}
      <Typography variant="h6">Recent LLM calls</Typography>
      <Typography component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
        {JSON.stringify(calls.data || [], null, 2)}
      </Typography>
    </Stack>
  );
}
