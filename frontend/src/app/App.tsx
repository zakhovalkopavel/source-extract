import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import {
  AppBar,
  Box,
  Button,
  Container,
  Menu,
  MenuItem,
  Toolbar,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { AdaptersPage } from '../pages/AdaptersPage';
import { CommandsPage } from '../pages/CommandsPage';
import { HistoryPage } from '../pages/HistoryPage';
import { JobsPage } from '../pages/JobsPage';
import { ModelsPage } from '../pages/ModelsPage';
import { OcrPage } from '../pages/OcrPage';
import { ReviewPage } from '../pages/ReviewPage';

/** Main Thermal Software UI (same origin via nginx, or absolute URL from env). */
const MAIN_APP_URL = import.meta.env.VITE_MAIN_APP_URL ?? '/';

const PRIMARY_NAV = [
  { to: '/adapters', label: 'Sources' },
  { to: '/review', label: 'Diagrams' },
] as const;

const ADVANCED_NAV = [
  { to: '/commands', label: 'Commands' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/ocr', label: 'OCR' },
  { to: '/history', label: 'History' },
  { to: '/models', label: 'Models' },
] as const;

export function App() {
  const [advancedAnchor, setAdvancedAnchor] = useState<null | HTMLElement>(null);
  const [showAdvanced, setShowAdvanced] = useState(
    () => localStorage.getItem('se-advanced') === '1',
  );

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="sticky" color="primary" elevation={0}>
        <Toolbar variant="dense" sx={{ gap: 0.5 }}>
          <Button
            color="inherit"
            href={MAIN_APP_URL}
            startIcon={<ArrowBackIcon />}
            sx={{ textTransform: 'none', mr: 1 }}
          >
            Thermal Software
          </Button>
          <Typography variant="h6" sx={{ mr: 2, fontWeight: 700, letterSpacing: 0.2 }}>
            Source Extractor
          </Typography>
          {PRIMARY_NAV.map((item) => (
            <Button
              key={item.to}
              component={NavLink}
              to={item.to}
              color="inherit"
              sx={{ '&.active': { bgcolor: 'rgba(255,255,255,0.16)' }, textTransform: 'none' }}
            >
              {item.label}
            </Button>
          ))}
          <Box sx={{ flex: 1 }} />
          {showAdvanced ? (
            <>
              <Button
                color="inherit"
                size="small"
                sx={{ textTransform: 'none', opacity: 0.85 }}
                onClick={(e) => setAdvancedAnchor(e.currentTarget)}
              >
                Advanced
              </Button>
              <Menu
                anchorEl={advancedAnchor}
                open={Boolean(advancedAnchor)}
                onClose={() => setAdvancedAnchor(null)}
              >
                {ADVANCED_NAV.map((item) => (
                  <MenuItem
                    key={item.to}
                    component={NavLink}
                    to={item.to}
                    onClick={() => setAdvancedAnchor(null)}
                  >
                    {item.label}
                  </MenuItem>
                ))}
                <MenuItem
                  onClick={() => {
                    localStorage.removeItem('se-advanced');
                    setShowAdvanced(false);
                    setAdvancedAnchor(null);
                  }}
                >
                  Hide advanced
                </MenuItem>
              </Menu>
            </>
          ) : (
            <Button
              color="inherit"
              size="small"
              sx={{ textTransform: 'none', opacity: 0.55 }}
              onClick={() => {
                localStorage.setItem('se-advanced', '1');
                setShowAdvanced(true);
              }}
              title="Commands, Jobs, OCR, History, Models"
            >
              …
            </Button>
          )}
        </Toolbar>
      </AppBar>
      <Container maxWidth={false} sx={{ py: 2, px: { xs: 1.5, md: 2 }, flex: 1 }}>
        <Routes>
          <Route path="/" element={<Navigate to="/review" replace />} />
          <Route path="/adapters" element={<AdaptersPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/commands" element={<CommandsPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/jobs/:jobId" element={<JobsPage />} />
          <Route path="/ocr" element={<OcrPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/models" element={<ModelsPage />} />
        </Routes>
      </Container>
    </Box>
  );
}
