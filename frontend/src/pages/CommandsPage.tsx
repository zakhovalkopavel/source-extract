import {
  Button,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { seClient, type CommandSpecDto } from '../shared/api/se-client';

export function CommandsPage() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ['commands'],
    queryFn: async () => (await seClient.get('/commands')).data as CommandSpecDto[],
  });
  const [commandId, setCommandId] = useState('extract');
  const [values, setValues] = useState<Record<string, string>>({ system: '', adapter_id: 'phase-diagrams' });

  const selected = useMemo(
    () => (data || []).find((c) => c.id === commandId),
    [data, commandId],
  );

  const run = useMutation({
    mutationFn: async () => {
      const params: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(values)) {
        if (v === '') continue;
        params[k] = v;
      }
      const res = await seClient.post('/jobs', { commandId, params });
      return res.data as { id: string };
    },
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
  });

  if (isLoading) return <CircularProgress />;

  return (
    <Stack spacing={2} maxWidth={720}>
      <Typography variant="h5">Command runner</Typography>
      <FormControl fullWidth>
        <InputLabel id="cmd">Command</InputLabel>
        <Select
          labelId="cmd"
          label="Command"
          value={commandId}
          onChange={(e) => setCommandId(e.target.value)}
        >
          {(data || []).map((c) => (
            <MenuItem key={c.id} value={c.id}>
              {c.title} ({c.id})
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      {selected?.description && (
        <Typography variant="body2" color="text.secondary">
          {selected.description}
        </Typography>
      )}
      {(selected?.params || [])
        .filter((p) => !p.advanced)
        .map((p) => (
          <TextField
            key={p.name}
            label={`${p.name}${p.required ? ' *' : ''}`}
            helperText={p.description}
            value={values[p.name] ?? (p.default != null ? String(p.default) : '')}
            onChange={(e) => setValues((prev) => ({ ...prev, [p.name]: e.target.value }))}
            fullWidth
          />
        ))}
      <Button variant="contained" disabled={run.isPending} onClick={() => run.mutate()}>
        Run as job
      </Button>
      {run.error && <Typography color="error">{String(run.error)}</Typography>}
    </Stack>
  );
}
