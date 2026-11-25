import { Alert, Link, Stack, Typography } from '@mui/material';

export function HomePage() {
  return (
    <Stack spacing={2}>
      <Typography variant="h4">Source Extractor</Typography>
      <Typography color="text.secondary">
        Single door for adapters, commands, jobs, OCR, review, and dataset history.
      </Typography>
      <Alert severity="info">
        API docs:{' '}
        <Link href="/source-extractor/docs" target="_blank" rel="noreferrer">
          /source-extractor/docs
        </Link>
      </Alert>
    </Stack>
  );
}
