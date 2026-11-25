import { Box, Slider, Stack, Typography } from '@mui/material';
import {
  BOUNDARY_STROKE,
  CURVE_WIDTH_MAX,
  CURVE_WIDTH_MIN,
  DEFAULT_VIEW_OPACITY,
  ISO_MISSING,
  ISO_PALETTE,
  POINT_SIZE_MAX,
  POINT_SIZE_MIN,
  type ViewOpacity,
  uniqueIsothermTemps,
} from './canvas/curveStyles';
import type { ReviewSession } from './types';

type Props = {
  opacity: ViewOpacity;
  onOpacity: (next: ViewOpacity) => void;
  session: ReviewSession | null;
};

function OpacitySlider({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <Box>
      <Stack direction="row" justifyContent="space-between">
        <Typography variant="caption">{label}</Typography>
        <Typography variant="caption" color="text.secondary">
          {Math.round(value * 100)}%
        </Typography>
      </Stack>
      <Slider
        size="small"
        min={0}
        max={100}
        value={Math.round(value * 100)}
        onChange={(_, v) => onChange((v as number) / 100)}
      />
    </Box>
  );
}

export function ViewOptions({ opacity, onOpacity, session }: Props) {
  const temps = uniqueIsothermTemps(session?.view?.isotherms);
  const missing = (session?.view?.isotherms || []).some(
    (iso) => iso.temperature_C == null || !Number.isFinite(Number(iso.temperature_C)),
  );
  const curveWidth = opacity.curveWidth ?? DEFAULT_VIEW_OPACITY.curveWidth;
  const pointSize = opacity.pointSize ?? DEFAULT_VIEW_OPACITY.pointSize;

  return (
    <Stack spacing={1}>
      <Typography variant="subtitle2">View</Typography>
      <Box>
        <Stack direction="row" justifyContent="space-between">
          <Typography variant="caption">Line thickness</Typography>
          <Typography variant="caption" color="text.secondary">
            {curveWidth.toFixed(1)} px
          </Typography>
        </Stack>
        <Slider
          size="small"
          min={CURVE_WIDTH_MIN}
          max={CURVE_WIDTH_MAX}
          step={0.1}
          value={curveWidth}
          onChange={(_, v) => onOpacity({ ...opacity, curveWidth: v as number })}
        />
      </Box>
      <Box>
        <Stack direction="row" justifyContent="space-between">
          <Typography variant="caption">Point size</Typography>
          <Typography variant="caption" color="text.secondary">
            {pointSize.toFixed(1)} px
          </Typography>
        </Stack>
        <Slider
          size="small"
          min={POINT_SIZE_MIN}
          max={POINT_SIZE_MAX}
          step={0.1}
          value={pointSize}
          onChange={(_, v) => onOpacity({ ...opacity, pointSize: v as number })}
        />
      </Box>
      <OpacitySlider
        label="All overlays"
        value={opacity.all}
        onChange={(v) => onOpacity({ ...opacity, all: v })}
      />
      <OpacitySlider
        label="Curves"
        value={opacity.curves}
        onChange={(v) => onOpacity({ ...opacity, curves: v })}
      />
      <OpacitySlider
        label="Points"
        value={opacity.points}
        onChange={(v) => onOpacity({ ...opacity, points: v })}
      />
      <OpacitySlider
        label="Nodes"
        value={opacity.nodes}
        onChange={(v) => onOpacity({ ...opacity, nodes: v })}
      />
      <OpacitySlider
        label="Live overlay"
        value={opacity.live}
        onChange={(v) => onOpacity({ ...opacity, live: v })}
      />
      <OpacitySlider
        label="Reference overlay"
        value={opacity.reference}
        onChange={(v) => onOpacity({ ...opacity, reference: v })}
      />
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ cursor: 'pointer' }}
        onClick={() => onOpacity({ ...DEFAULT_VIEW_OPACITY })}
      >
        Reset view
      </Typography>

      <Typography variant="subtitle2" sx={{ pt: 1 }}>
        Legend
      </Typography>
      <Stack spacing={0.5}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Box sx={{ width: 14, height: 14, bgcolor: BOUNDARY_STROKE, borderRadius: 0.5 }} />
          <Typography variant="caption">boundary</Typography>
        </Stack>
        {temps.map((t, i) => (
          <Stack key={t} direction="row" spacing={1} alignItems="center">
            <Box
              sx={{
                width: 14,
                height: 14,
                bgcolor: ISO_PALETTE[i % ISO_PALETTE.length],
                borderRadius: 0.5,
              }}
            />
            <Typography variant="caption">{t} °C</Typography>
          </Stack>
        ))}
        {missing && (
          <Stack direction="row" spacing={1} alignItems="center">
            <Box sx={{ width: 14, height: 14, bgcolor: ISO_MISSING, borderRadius: 0.5 }} />
            <Typography variant="caption">isotherm (no °C)</Typography>
          </Stack>
        )}
      </Stack>
    </Stack>
  );
}
