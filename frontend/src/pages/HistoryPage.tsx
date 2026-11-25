import { Button, Stack, TextField, Typography } from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { seClient } from '../shared/api/se-client';

export function HistoryPage() {
  const [adapterId, setAdapterId] = useState('phase-diagrams');
  const [datasetId, setDatasetId] = useState('');

  const list = useMutation({
    mutationFn: async () =>
      (await seClient.get(`/history/${adapterId}/${datasetId}`)).data as Array<Record<string, string>>,
  });

  return (
    <Stack spacing={2} maxWidth={720}>
      <Typography variant="h5">Dataset history</Typography>
      <TextField label="Adapter" value={adapterId} onChange={(e) => setAdapterId(e.target.value)} fullWidth />
      <TextField label="Dataset / system id" value={datasetId} onChange={(e) => setDatasetId(e.target.value)} fullWidth />
      <Button variant="contained" onClick={() => list.mutate()}>
        List history
      </Button>
      {list.data && (
        <Typography component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
          {JSON.stringify(list.data, null, 2)}
        </Typography>
      )}
      {list.error && <Typography color="error">{String(list.error)}</Typography>}
    </Stack>
  );
}
