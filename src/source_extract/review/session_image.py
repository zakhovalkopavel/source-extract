"""Session base image discovery and meta assembly."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from source_extract.review import review_paths as RP
from source_extract.review.binary_axes import is_binary_draft
from source_extract.review.session_image_synth import (
    _binary_frame_image,
    _clean_scan_crop,
    _copy_pipeline_png_as_base,
    _ensure_page_render,
    _read_image_meta,
    _synthetic_triangle_image,
)

def _find_image_path(
    system_id: str,
    draft_stem: str | None = None,
    *,
    draft_kind: str | None = None,
) -> Path | None:
    stems = [s for s in (draft_stem, system_id) if s]
    # Deduplicate while preserving order
    seen: set[str] = set()
    ordered_stems: list[str] = []
    for stem in stems:
        if stem not in seen:
            seen.add(stem)
            ordered_stems.append(stem)

    # Match background to the draft: candidates/systems → pd-curves overlays first;
    # auto-full → auto-full png first. Never let an empty auto-full png hide overlays/.
    if draft_kind in ("candidates", "systems"):
        roots = [
            RP.work_dir() / "overlays",
            RP.dataset_dir() / "overlays",
            RP.auto_full_dir(),
            RP.work_dir() / "auto",
        ]
    elif draft_kind == "auto-full":
        roots = [
            RP.auto_full_dir(),
            RP.work_dir() / "overlays",
            RP.dataset_dir() / "overlays",
            RP.work_dir() / "auto",
        ]
    else:
        roots = [
            RP.work_dir() / "overlays",
            RP.dataset_dir() / "overlays",
            RP.auto_full_dir(),
            RP.work_dir() / "auto",
        ]

    candidates: list[Path] = []
    for stem in ordered_stems:
        for root in roots:
            candidates.append(root / f"{stem}.png")
    if RP.auto_full_dir().is_dir():
        needle = system_id.lower()
        for path in RP.auto_full_dir().glob("*.png"):
            if path.stem.lower() == needle:
                # Only prefer auto-full png when that is the draft kind
                if draft_kind == "auto-full":
                    candidates.insert(0, path)
                else:
                    candidates.append(path)
    for path in candidates:
        if path and path.is_file():
            return path
    return None


def _image_meta_for_session(
    system_id: str,
    draft: dict[str, Any],
    session_id: str,
    *,
    draft_kind: str | None = None,
    draft_stem: str | None = None,
) -> dict[str, Any]:
    kind = draft_kind
    stem = draft_stem
    if kind is None or stem is None:
        resolved_kind, draft_path = _resolve_draft_path(system_id, preferred=draft_kind)
        kind = kind or resolved_kind
        stem = stem or draft_path.stem
    png = _find_image_path(system_id, stem, draft_kind=kind)
    dest = RP.sessions_dir() / f"{session_id}.base.png"
    if png is not None:
        meta = _read_image_meta(png)
        # overlays/*.png already paint curves — prefer a clean page crop so deletes
        # are visible (editable red/blue geometry alone, no ghost ink).
        if "overlays" in Path(meta["path"]).parts:
            clean = _clean_scan_crop(
                draft,
                page_origin=tuple(meta["pageOrigin"]),  # type: ignore[arg-type]
                width=int(meta["width"]),
                height=int(meta["height"]),
                dest=dest,
            )
            if clean is not None:
                clean["draftSource"] = kind
                return clean
        meta["draftSource"] = kind
        return meta
    if is_binary_draft(draft):
        meta = _binary_frame_image(draft, dest)
    else:
        meta = _synthetic_triangle_image(draft, dest)
    meta["draftSource"] = kind
    return meta

