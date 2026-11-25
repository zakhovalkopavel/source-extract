"""Reference overlay attach and live base image refresh."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from source_extract.review import review_paths as RP
from source_extract.review.binary_axes import is_binary_draft
from source_extract.review.session_image import _find_image_path, _image_meta_for_session
from source_extract.review.session_image_synth import (
    _binary_frame_image,
    _clean_scan_crop,
    _copy_pipeline_png_as_base,
    _ensure_page_render,
    _read_image_meta,
    _synthetic_triangle_image,
)


def _png_page_origin(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as im:
            raw = im.text.get("pageOrigin") or im.info.get("pageOrigin")
    except OSError:
        return None
    if not raw:
        return None
    try:
        parts = [int(float(v)) for v in str(raw).split(",")]
    except (TypeError, ValueError):
        return None
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def _reference_overlay_candidates(system_id: str) -> list[Path]:
    """Pipeline colored overlays (pd-curves / pd-auto), newest matching stem first."""
    needle = system_id.lower()
    roots = (
        RP.work_dir() / "overlays",
        RP.dataset_dir() / "overlays",
        RP.auto_full_dir(),
        RP.work_dir() / "auto",
    )
    found: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.glob("*.png"):
            if path.stem.lower() != needle:
                continue
            key = str(path.resolve()) if path.exists() else str(path)
            if key in seen:
                continue
            seen.add(key)
            found.append(path)
    return found


def _reference_overlay_path(
    system_id: str,
    *,
    prefer_origin: tuple[int, int] | None = None,
) -> Path | None:
    """Pick a colored overlay; prefer one whose pageOrigin matches the session base."""
    candidates = _reference_overlay_candidates(system_id)
    if not candidates:
        return None
    if prefer_origin is None:
        return candidates[0]
    exact: list[Path] = []
    close: list[Path] = []
    for path in candidates:
        origin = _png_page_origin(path)
        if origin is None:
            continue
        dx = abs(origin[0] - prefer_origin[0])
        dy = abs(origin[1] - prefer_origin[1])
        if dx == 0 and dy == 0:
            exact.append(path)
        elif dx <= 2 and dy <= 2:
            close.append(path)
    if exact:
        return exact[0]
    if close:
        return close[0]
    # Mismatched crop → skip rather than stretch a shifted layer onto the canvas
    return None


def _attach_reference_overlay(session: dict[str, Any]) -> dict[str, Any]:
    image = session.setdefault("image", {})
    origin_raw = image.get("pageOrigin") or [0, 0]
    prefer = (int(origin_raw[0]), int(origin_raw[1])) if len(origin_raw) == 2 else None
    path = _reference_overlay_path(session.get("systemId") or "", prefer_origin=prefer)
    if path is not None:
        image["referenceOverlayPath"] = str(path)
        image["hasReferenceOverlay"] = True
        ref_origin = _png_page_origin(path)
        if ref_origin is not None:
            image["referencePageOrigin"] = [ref_origin[0], ref_origin[1]]
        else:
            image.pop("referencePageOrigin", None)
        try:
            with Image.open(path) as im:
                image["referenceSize"] = [im.width, im.height]
        except OSError:
            image.pop("referenceSize", None)
    else:
        image.pop("referenceOverlayPath", None)
        image.pop("referencePageOrigin", None)
        image.pop("referenceSize", None)
        image["hasReferenceOverlay"] = False
    return session


def _pipeline_image_source(
    system_id: str,
    *,
    draft_kind: str | None,
    draft_stem: str | None = None,
) -> Path | None:
    """Canonical pipeline PNG for this draft (overlay / auto-full), if any."""
    return _find_image_path(system_id, draft_stem or system_id, draft_kind=draft_kind)


def _refresh_session_image(session: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the session base from the current draft's pipeline PNG + pageOrigin.

    Stale ``cleanScan`` crops (wrong origin/size after Analyze / draft switch) are the
    main cause of node / curve / overlay / scan offsets — always re-derive.
    """
    system_id = str(session.get("systemId") or "")
    draft = session.get("draft") or {}
    draft_kind = session.get("draftSource")
    dest = RP.sessions_dir() / f"{session['id']}.base.png"

    if is_binary_draft(draft):
        # Prefer clean atlas crop (axes / extract origin); fall back to extract overlay
        # (includes the scan); never leave a gray synthetic when a page can be rendered.
        png = _pipeline_image_source(system_id, draft_kind=draft_kind)
        image: dict[str, Any] | None = None
        if png is not None:
            meta = _read_image_meta(png)
            image = _clean_scan_crop(
                draft,
                page_origin=tuple(meta["pageOrigin"]),  # type: ignore[arg-type]
                width=int(meta["width"]),
                height=int(meta["height"]),
                dest=dest,
            )
            if image is None:
                # Page missing/unreadable — keep extract overlay (scan + traced ink)
                image = _copy_pipeline_png_as_base(png, dest, meta)
        if image is None:
            image = _binary_frame_image(draft, dest)
        image["draftSource"] = draft_kind
        session["image"] = image
        return _attach_reference_overlay(session)

    png = _pipeline_image_source(system_id, draft_kind=draft_kind)
    if png is not None:
        meta = _read_image_meta(png)
        origin = tuple(meta["pageOrigin"])  # type: ignore[arg-type]
        clean = _clean_scan_crop(
            draft,
            page_origin=origin,
            width=int(meta["width"]),
            height=int(meta["height"]),
            dest=dest,
        )
        if clean is not None:
            clean["draftSource"] = draft_kind
            session["image"] = clean
        else:
            # No page render yet — use the pipeline PNG itself (baked curves OK as fallback)
            meta = dict(meta)
            meta["draftSource"] = draft_kind
            # Copy into the session slot so live overlay size matches
            try:
                Image.open(png).convert("RGB").save(dest)
                meta["path"] = str(dest)
            except OSError:
                pass
            session["image"] = meta
    else:
        # Starts / empty stub: synthetic triangle from calibration
        session["image"] = _synthetic_triangle_image(draft, dest)
        session["image"]["draftSource"] = draft_kind
    return _attach_reference_overlay(session)


def _ensure_clean_session_image(session: dict[str, Any]) -> dict[str, Any]:
    """Keep the session raster aligned with the draft's pipeline crop (see ``_refresh_session_image``)."""
    return _refresh_session_image(session)

