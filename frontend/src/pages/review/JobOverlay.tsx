import { Box, Button, Paper, Typography } from '@mui/material';

type Props = {
  open: boolean;
  title: string;
  log: string[];
  onClose: () => void;
};

export function JobOverlay({ open, title, log, onClose }: Props) {
  if (!open) return null;
  return (
    <Paper
      elevation={8}
      sx={{
        position: 'fixed',
        right: 24,
        bottom: 24,
        width: 420,
        maxHeight: 360,
        p: 2,
        zIndex: 20,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
      }}
    >
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Typography fontWeight={700}>{title}</Typography>
        <Button size="small" onClick={onClose}>
          Close
        </Button>
      </Box>
      <Typography
        component="pre"
        sx={{
          m: 0,
          flex: 1,
          overflow: 'auto',
          fontSize: 12,
          bgcolor: '#111',
          color: '#ddd',
          p: 1,
          borderRadius: 1,
          minHeight: 160,
        }}
      >
        {log.slice(-80).join('\n')}
      </Typography>
    </Paper>
  );
}
