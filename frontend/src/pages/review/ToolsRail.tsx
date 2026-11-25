import { Button, Divider, Stack, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import type { ViewOpacity } from './canvas/curveStyles';
import type { ReviewSession, ToolMode } from './types';
import { ViewOptions } from './ViewOptions';

type Props = {
  tool: ToolMode;
  onTool: (t: ToolMode) => void;
  session: ReviewSession | null;
  busy?: boolean;
  opacity: ViewOpacity;
  onOpacity: (o: ViewOpacity) => void;
  onUndo: () => void;
  onAnalyze: () => void;
  onConfirm: () => void;
  onGuidance: () => void;
  onReload: () => void;
};

const TOOLS: Array<{ id: ToolMode; label: string }> = [
  { id: 'select', label: 'Select' },
  { id: 'move', label: 'Move' },
  { id: 'add', label: 'Add pt' },
  { id: 'delete', label: 'Delete' },
  { id: 'arrows', label: 'Arrows' },
  { id: 'seed-boundary', label: 'Seed boundary' },
  { id: 'seed-isotherm', label: 'Seed isotherm' },
  { id: 'add-invariant', label: 'Add invariant' },
];

export function ToolsRail({
  tool,
  onTool,
  session,
  busy,
  opacity,
  onOpacity,
  onUndo,
  onAnalyze,
  onConfirm,
  onGuidance,
  onReload,
}: Props) {
  return (
    <Stack
      spacing={1.5}
      sx={{
        width: { xs: '100%', md: 220 },
        flexShrink: 0,
        maxHeight: { md: '78vh' },
        overflow: 'auto',
        pr: 0.5,
      }}
    >
      <Typography variant="subtitle2">Tools</Typography>
      <ToggleButtonGroup
        exclusive
        orientation="vertical"
        size="small"
        value={tool}
        onChange={(_, v) => v && onTool(v)}
        fullWidth
      >
        {TOOLS.map((t) => (
          <ToggleButton key={t.id} value={t.id} sx={{ textTransform: 'none' }}>
            {t.label}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      <Typography variant="caption" color="text.secondary">
        Select: click curve or point. Move: drag handles; empty space pans. Space/Alt/Shift
        also pan. Wheel zooms. Seed: double-click to commit.
      </Typography>
      <Button variant="outlined" disabled={!session || busy} onClick={onUndo}>
        Undo ({session?.undoDepth ?? 0})
      </Button>
      <Button variant="outlined" disabled={!session || busy} onClick={onReload}>
        Reload draft
      </Button>
      <Button variant="contained" disabled={!session || busy} onClick={onAnalyze}>
        Analyze
      </Button>
      <Button
        variant="contained"
        color="success"
        disabled={!session || busy || session.validation?.canConfirm === false}
        onClick={onConfirm}
      >
        Confirm
      </Button>
      <Button variant="text" disabled={!session || busy} onClick={onGuidance}>
        Refresh guidance
      </Button>
      {session?.diagramKind && (
        <Typography variant="caption">Kind: {session.diagramKind}</Typography>
      )}

      <Divider />
      <ViewOptions opacity={opacity} onOpacity={onOpacity} session={session} />
    </Stack>
  );
}
