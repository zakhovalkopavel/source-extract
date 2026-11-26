import { Box, Stack, Typography } from '@mui/material';
import {
  ISO_MISSING,
  ISO_PALETTE,
  isothermMissingTemp,
  uniqueIsothermTemps,
} from './canvas/curveStyles';
import type { ReviewSession } from './types';

type Props = {
  session: ReviewSession | null;
};

export function IsothermLegend({ session }: Props) {
  const isotherms = session?.view?.isotherms || [];
  const temps = uniqueIsothermTemps(isotherms);
  if (!temps.length && !isotherms.some(isothermMissingTemp)) {
    return null;
  }

  const missing = isotherms.filter(isothermMissingTemp).length;

  return (
    <Stack
      spacing={0.5}
      sx={{
        width: 56,
        flexShrink: 0,
        alignItems: 'stretch',
        py: 0.5,
      }}
      title="Isotherm temperatures"
    >
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', alignSelf: 'center', mb: 0.5 }}
      >
        °C
      </Typography>
      <Box
        sx={{
          flex: 1,
          minHeight: 120,
          display: 'flex',
          flexDirection: 'column-reverse',
          gap: '2px',
          borderRadius: 1,
          overflow: 'hidden',
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        {temps.map((t, i) => (
          <Box
            key={t}
            sx={{
              flex: 1,
              minHeight: 18,
              bgcolor: ISO_PALETTE[i % ISO_PALETTE.length],
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            title={`${t} °C`}
          >
            <Typography
              variant="caption"
              sx={{
                fontSize: 10,
                fontWeight: 700,
                color: '#111',
                textShadow: '0 0 2px #fff',
                lineHeight: 1,
              }}
            >
              {t}
            </Typography>
          </Box>
        ))}
        {missing > 0 && (
          <Box
            sx={{
              flex: '0 0 22px',
              bgcolor: ISO_MISSING,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            title={`${missing} isotherm(s) missing °C`}
          >
            <Typography variant="caption" sx={{ fontSize: 9, color: '#fff', fontWeight: 700 }}>
              ?
            </Typography>
          </Box>
        )}
      </Box>
    </Stack>
  );
}
