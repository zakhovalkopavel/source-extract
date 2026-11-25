"""Resolve background / overlay PNGs for a draft JSON path."""

from __future__ import annotations

from pathlib import Path


class DraftImagePaths:
    """Probe common work/dataset overlay locations next to a draft."""

    @staticmethod
    def find(draft_path: Path) -> Path | None:
        stem = draft_path.stem
        parent = draft_path.parent
        work = parent.parent if parent.name in {"candidates", "auto-full", "starts", "systems"} else parent
        dataset_overlays = None
        # candidates → …/phase-diagrams/candidates; overlays sit beside that tree
        candidates: list[Path] = [
            parent / f"{stem}.png",
            parent / f"{stem}.overlay.png",
            work / "overlays" / f"{stem}.png",
            work / "auto-full" / f"{stem}.png",
            work / "candidates" / f"{stem}.png",
        ]
        # shared/processed/phase-diagrams/overlays when draft is under reports/…/candidates
        if work.name == "phase-diagrams":
            # /app/reports/phase-diagrams → try /app/shared/processed/phase-diagrams/overlays
            shared = Path("/app/shared/processed/phase-diagrams/overlays") / f"{stem}.png"
            candidates.append(shared)
            # relative climb: reports → shared
            alt = work.parent.parent / "shared" / "processed" / "phase-diagrams" / "overlays" / f"{stem}.png"
            candidates.append(alt)
            dataset_overlays = work.parent.parent / "shared" / "processed" / "phase-diagrams" / "overlays" / f"{stem}.png"
            if dataset_overlays:
                candidates.append(dataset_overlays)
        seen: set[Path] = set()
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            if path.is_file():
                return path
        return None
