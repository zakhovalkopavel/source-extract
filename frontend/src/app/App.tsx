import { AppBar, Box, Button, Container, Toolbar, Typography } from '@mui/material';
import { NavLink, Route, Routes } from 'react-router-dom';
import { AdaptersPage } from '../pages/AdaptersPage';
import { CommandsPage } from '../pages/CommandsPage';
import { HistoryPage } from '../pages/HistoryPage';
import { HomePage } from '../pages/HomePage';
import { JobsPage } from '../pages/JobsPage';
import { ModelsPage } from '../pages/ModelsPage';
import { OcrPage } from '../pages/OcrPage';
import { ReviewPage } from '../pages/ReviewPage';

const NAV = [
  { to: '/', label: 'Home', end: true },
  { to: '/adapters', label: 'Adapters' },
  { to: '/commands', label: 'Commands' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/review', label: 'Review' },
  { to: '/ocr', label: 'OCR' },
  { to: '/history', label: 'History' },
  { to: '/models', label: 'Models' },
] as const;

export function App() {
  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="sticky" color="primary">
        <Toolbar>
          <Typography variant="h6" sx={{ mr: 3, fontWeight: 700 }}>
            Source Extractor
          </Typography>
          {NAV.map((item) => (
            <Button
              key={item.to}
              component={NavLink}
              to={item.to}
              end={item.end}
              color="inherit"
              sx={{ '&.active': { bgcolor: 'rgba(255,255,255,0.16)' } }}
            >
              {item.label}
            </Button>
          ))}
        </Toolbar>
      </AppBar>
      <Container maxWidth="xl" sx={{ py: 3, flex: 1 }}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/adapters" element={<AdaptersPage />} />
          <Route path="/commands" element={<CommandsPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/jobs/:jobId" element={<JobsPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/ocr" element={<OcrPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/models" element={<ModelsPage />} />
        </Routes>
      </Container>
    </Box>
  );
}
