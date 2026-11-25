import { CircularProgress, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { seClient } from '../shared/api/se-client';

export function AdaptersPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['adapters'],
    queryFn: async () => (await seClient.get('/adapters')).data as Array<Record<string, unknown>>,
  });

  if (isLoading) return <CircularProgress />;
  if (error) return <Typography color="error">{String(error)}</Typography>;

  return (
    <Stack spacing={2}>
      <Typography variant="h5">Adapters</Typography>
      {(data || []).map((row) => (
        <Stack key={String(row.id)} spacing={0.5} sx={{ borderBottom: '1px solid #ddd', pb: 1 }}>
          <Typography fontWeight={600}>
            {String(row.displayName)} ({String(row.id)})
          </Typography>
          <Typography variant="body2">kinds: {JSON.stringify(row.kinds)}</Typography>
          <Typography variant="body2">commands: {JSON.stringify(row.commands)}</Typography>
        </Stack>
      ))}
    </Stack>
  );
}
