import { Button, Stack, TextField, Typography } from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { seClient } from '../shared/api/se-client';

export function OcrPage() {
  const [imagePath, setImagePath] = useState('');
  const [box, setBox] = useState('0 0 100 40');
  const [engine, setEngine] = useState('page-ocr');

  const run = useMutation({
    mutationFn: async () => {
      const parts = box.trim().split(/\s+/).map(Number);
      const res = await seClient.post('/models/ocr-region', {
        imagePath,
        box: parts,
        engine,
      });
      return res.data as { candidates: Array<Record<string, unknown>> };
    },
  });

  return (
    <Stack spacing={2} maxWidth={720}>
      <Typography variant="h5">OCR zone</Typography>
      <TextField label="Image path (in container)" value={imagePath} onChange={(e) => setImagePath(e.target.value)} fullWidth />
      <TextField label="Box x0 y0 x1 y1" value={box} onChange={(e) => setBox(e.target.value)} fullWidth />
      <TextField label="Engine" value={engine} onChange={(e) => setEngine(e.target.value)} fullWidth />
      <Button variant="contained" onClick={() => run.mutate()} disabled={run.isPending}>
        Re-OCR region
      </Button>
      {run.data && (
        <Typography component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
          {JSON.stringify(run.data, null, 2)}
        </Typography>
      )}
      {run.error && <Typography color="error">{String(run.error)}</Typography>}
    </Stack>
  );
}
