import NearMeOutlinedIcon from '@mui/icons-material/NearMeOutlined';
import OpenWithOutlinedIcon from '@mui/icons-material/OpenWithOutlined';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';
import SwapHorizOutlinedIcon from '@mui/icons-material/SwapHorizOutlined';
import PlaceOutlinedIcon from '@mui/icons-material/PlaceOutlined';
import UndoOutlinedIcon from '@mui/icons-material/UndoOutlined';
import RedoOutlinedIcon from '@mui/icons-material/RedoOutlined';
import CheckOutlinedIcon from '@mui/icons-material/CheckOutlined';
import SaveOutlinedIcon from '@mui/icons-material/SaveOutlined';
import {
  Box,
  Button,
  IconButton,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import type { ReactNode } from 'react';
import type { ToolMode } from './types';

export type SeedCurveKind = 'boundary' | 'isotherm';

type Props = {
  tool: ToolMode;
  onTool: (t: ToolMode) => void;
  seedKind: SeedCurveKind;
  onSeedKind: (k: SeedCurveKind) => void;
  seedCount: number;
  canDelete: boolean;
  selectionCount: number;
  /** e.g. "Delete boundary #12" when a whole curve is selected. */
  deleteLabel?: string;
  busy?: boolean;
  undoDepth?: number;
  canConfirm?: boolean;
  onUndo: () => void;
  onRedo?: () => void;
  onConfirm: () => void;
  onDeleteSelection: () => void;
  onCommitSeed?: () => void;
  onCancelSeed?: () => void;
  onSaveCurve?: () => void;
  canSaveCurve?: boolean;
  status?: string;
};

const TILES: Array<{
  id: ToolMode;
  label: string;
  tip: string;
  icon: ReactNode;
}> = [
  {
    id: 'select',
    label: 'Select',
    tip: 'Select points and curves (Ctrl+click to multi-select)',
    icon: <NearMeOutlinedIcon fontSize="small" />,
  },
  {
    id: 'move',
    label: 'Move',
    tip: 'Drag points; shared vertices move together',
    icon: <OpenWithOutlinedIcon fontSize="small" />,
  },
  {
    id: 'add',
    label: 'Add',
    tip: 'Add a vertex on the selected curve',
    icon: <AddCircleOutlineIcon fontSize="small" />,
  },
  {
    id: 'add-invariant',
    label: 'Point',
    tip: 'Click the diagram to place a point, then set type / name / °C on the right',
    icon: <PlaceOutlinedIcon fontSize="small" />,
  },
  {
    id: 'delete',
    label: 'Delete',
    tip: 'Delete selected points or curves',
    icon: <DeleteOutlineIcon fontSize="small" />,
  },
  {
    id: 'seed',
    label: 'Seed',
    tip: 'Click waypoints to draw a new boundary or isotherm, then Save',
    icon: <TimelineOutlinedIcon fontSize="small" />,
  },
  {
    id: 'arrows',
    label: 'Arrows',
    tip: 'Cycle boundary flow arrows (click a boundary)',
    icon: <SwapHorizOutlinedIcon fontSize="small" />,
  },
];

const tileSx = {
  width: 52,
  height: 52,
  borderRadius: 1.5,
  display: 'flex',
  flexDirection: 'column' as const,
  gap: 0.15,
  px: 0.5,
  textTransform: 'none' as const,
  border: '1px solid',
  borderColor: 'divider',
  bgcolor: 'background.paper',
  '&.Mui-selected': {
    bgcolor: 'primary.main',
    color: 'primary.contrastText',
    borderColor: 'primary.main',
    '&:hover': { bgcolor: 'primary.dark' },
  },
};

export function ToolTiles({
  tool,
  onTool,
  seedKind,
  onSeedKind,
  seedCount,
  canDelete,
  selectionCount,
  deleteLabel,
  busy,
  undoDepth = 0,
  canConfirm = false,
  onUndo,
  onRedo,
  onConfirm,
  onDeleteSelection,
  onCommitSeed,
  onCancelSeed,
  onSaveCurve,
  canSaveCurve,
  status,
}: Props) {
  const seeding = tool === 'seed';

  return (
    <Stack spacing={1}>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
        <ToggleButtonGroup
          exclusive
          size="small"
          value={tool}
          onChange={(_, v) => v && onTool(v)}
          sx={{ gap: 0.75, flexWrap: 'wrap' }}
        >
          {TILES.map((t) => (
            <Tooltip key={t.id} title={t.tip} arrow>
              <ToggleButton
                value={t.id}
                sx={tileSx}
                onClick={() => {
                  if (t.id === 'delete' && tool === 'delete') onDeleteSelection();
                }}
              >
                {t.icon}
                <Typography variant="caption" sx={{ fontSize: 10, lineHeight: 1.1 }}>
                  {t.label}
                </Typography>
              </ToggleButton>
            </Tooltip>
          ))}
        </ToggleButtonGroup>

        <Box
          sx={{
            width: '1px',
            alignSelf: 'stretch',
            bgcolor: 'divider',
            mx: 0.5,
            display: { xs: 'none', sm: 'block' },
          }}
        />

        <Tooltip title={`Undo (Ctrl+Z)${undoDepth ? ` · ${undoDepth}` : ''}`} arrow>
          <span>
            <IconButton
              size="small"
              disabled={busy || undoDepth <= 0}
              onClick={onUndo}
              sx={{
                width: 40,
                height: 40,
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1.5,
              }}
            >
              <UndoOutlinedIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip title="Redo (not available yet)" arrow>
          <span>
            <IconButton
              size="small"
              disabled
              onClick={() => onRedo?.()}
              sx={{
                width: 40,
                height: 40,
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1.5,
              }}
            >
              <RedoOutlinedIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>

        {canSaveCurve && (
          <Tooltip title="Save curve edits" arrow>
            <span>
              <Button
                size="small"
                variant="outlined"
                startIcon={<SaveOutlinedIcon />}
                disabled={busy}
                onClick={onSaveCurve}
                sx={{ height: 40, borderRadius: 1.5, textTransform: 'none' }}
              >
                Save
              </Button>
            </span>
          </Tooltip>
        )}

        {seeding && (
          <>
            <ToggleButtonGroup
              exclusive
              size="small"
              value={seedKind}
              onChange={(_, v) => v && onSeedKind(v)}
              sx={{ ml: 0.5 }}
            >
              <ToggleButton value="boundary" sx={{ textTransform: 'none', px: 1.25 }}>
                Boundary
              </ToggleButton>
              <ToggleButton value="isotherm" sx={{ textTransform: 'none', px: 1.25 }}>
                Isotherm
              </ToggleButton>
            </ToggleButtonGroup>
            <Button
              size="small"
              variant="contained"
              disabled={busy || seedCount < 2}
              onClick={() => onCommitSeed?.()}
              sx={{ height: 40, borderRadius: 1.5, textTransform: 'none' }}
            >
              Save seed{seedCount >= 2 ? ` (${seedCount})` : ''}
            </Button>
            <Button
              size="small"
              variant="outlined"
              disabled={busy}
              onClick={() => onCancelSeed?.()}
              sx={{ height: 40, borderRadius: 1.5, textTransform: 'none' }}
            >
              Cancel
            </Button>
          </>
        )}

        {canDelete && (
          <Button
            size="small"
            color="error"
            variant="contained"
            startIcon={<DeleteOutlineIcon />}
            disabled={busy}
            onClick={onDeleteSelection}
            sx={{ height: 40, borderRadius: 1.5, textTransform: 'none' }}
          >
            {deleteLabel ||
              (selectionCount > 0 ? `Delete (${selectionCount})` : 'Delete')}
          </Button>
        )}

        <Box sx={{ flex: 1 }} />

        <Tooltip title="Accept the reviewed diagram into the dataset" arrow>
          <span>
            <Button
              size="small"
              color="success"
              variant="contained"
              startIcon={<CheckOutlinedIcon />}
              disabled={busy || !canConfirm}
              onClick={onConfirm}
              sx={{ height: 40, borderRadius: 1.5, textTransform: 'none', fontWeight: 700 }}
            >
              Confirm
            </Button>
          </span>
        </Tooltip>
      </Stack>

      {status ? (
        <Typography variant="caption" color="text.secondary" noWrap>
          {status}
        </Typography>
      ) : null}
    </Stack>
  );
}
