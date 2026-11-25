"""Synthetic frames, page renders, clean crops, and PNG meta read."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image

from source_extract.review import review_paths as RP
from source_extract.review.barycentric import corners_from_calibration
from source_extract.review.binary_axes import axes_from_digitization, is_binary_draft

def _read_image_meta(png: Path) -> dict[str, Any]:
    with Image.open(png) as im:
        origin_raw = im.text.get("pageOrigin", "0,0")
        parts = [int(float(p.strip())) for p in origin_raw.split(",")]
        origin = (parts[0], parts[1]) if len(parts) == 2 else (0, 0)
        return {
            "path": str(png),
            "width": im.width,
            "height": im.height,
            "pageOrigin": list(origin),
            "synthetic": False,
        }


def _synthetic_triangle_image(draft: dict[str, Any], dest: Path, margin: int = 80) -> dict[str, Any]:
    """Build a blank canvas around the calibrated triangle when no scan crop exists."""
    from PIL import ImageDraw
    from PIL.PngImagePlugin import PngInfo

    components = draft["components"]
    calibration = draft["digitization"]["calibration"]
    corners = corners_from_calibration(components, calibration)
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    x0 = int(min(xs) - margin)
    y0 = int(min(ys) - margin)
    x1 = int(max(xs) + margin)
    y1 = int(max(ys) + margin)
    w, h = max(x1 - x0, 100), max(y1 - y0, 100)
    img = Image.new("RGB", (w, h), (236, 236, 236))
    draw = ImageDraw.Draw(img)
    tri = [(c[0] - x0, c[1] - y0) for c in corners]
    draw.line([tri[0], tri[1], tri[2], tri[0]], fill=(40, 40, 40), width=2)
    for (px, py), name in zip(tri, components):
        draw.ellipse((px - 4, py - 4, px + 4, py + 4), fill=(0, 140, 90))
        draw.text((px + 6, py - 6), name, fill=(20, 20, 20))
    dest.parent.mkdir(parents=True, exist_ok=True)
    info = PngInfo()
    info.add_text("pageOrigin", f"{x0},{y0}")
    img.save(dest, pnginfo=info)
    return {
        "path": str(dest),
        "width": w,
        "height": h,
        "pageOrigin": [x0, y0],
        "synthetic": True,
    }


def _binary_frame_image(draft: dict[str, Any], dest: Path, margin: int = 60) -> dict[str, Any]:
    """Crop the atlas page to the binary axes frame, or a blank placeholder."""
    from PIL.PngImagePlugin import PngInfo

    axes = axes_from_digitization(draft)
    if axes is None:
        raise ValueError("Binary draft has no axes — cannot build a review image")
    x0, y0, x1, y1 = axes.page_bbox(margin=float(margin))
    render = _ensure_page_render(draft)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if render is not None:
        with Image.open(render) as page:
            page = page.convert("RGB")
            x1 = min(x1, page.width)
            y1 = min(y1, page.height)
            x0 = max(0, min(x0, x1 - 1))
            y0 = max(0, min(y0, y1 - 1))
            crop = page.crop((x0, y0, x1, y1))
        info = PngInfo()
        info.add_text("pageOrigin", f"{x0},{y0}")
        crop.save(dest, pnginfo=info)
        return {
            "path": str(dest),
            "width": crop.width,
            "height": crop.height,
            "pageOrigin": [x0, y0],
            "synthetic": False,
            "cleanScan": True,
        }
    w, h = max(x1 - x0, 100), max(y1 - y0, 100)
    img = Image.new("RGB", (w, h), (236, 236, 236))
    info = PngInfo()
    info.add_text("pageOrigin", f"{x0},{y0}")
    img.save(dest, pnginfo=info)
    return {
        "path": str(dest),
        "width": w,
        "height": h,
        "pageOrigin": [x0, y0],
        "synthetic": True,
    }


def _render_page_path(draft: dict[str, Any]) -> Path | None:
    source = draft.get("source") or {}
    ref = source.get("ref")
    page = source.get("pdfPage")
    if not ref or page is None:
        return None
    path = RP.work_dir() / "renders" / f"{ref}-p{int(page)}-400dpi.png"
    return path if path.is_file() else None


def _ensure_page_render(draft: dict[str, Any]) -> Path | None:
    """Return the atlas page raster, rendering it via the python container if missing."""
    existing = _render_page_path(draft)
    if existing is not None:
        return existing
    source = draft.get("source") or {}
    ref = source.get("ref")
    page = source.get("pdfPage")
    if not ref or page is None:
        return None
    # Same invoke style as Analyze jobs
    if settings.pd_invoke == "docker":
        cmd = [
            "docker",
            "compose",
            "-f",
            str(RP.repo_root() / "compose.yml"),
            "run",
            "--rm",
            "python",
            "python",
            "-c",
            (
                "from pathlib import Path\n"
                "from phase_diagrams import SourceRegistry\n"
                "from phase_diagrams.cli.common import _page_image\n"
                f"work = Path('reports/phase-diagrams')\n"
                f"_page_image(SourceRegistry(Path('shared/processed/phase-diagrams')), work, {ref!r}, {int(page)})\n"
                f"print('rendered', work / 'renders' / f'{ref}-p{int(page)}-400dpi.png')\n"
            ),
        ]
    else:
        cmd = [
            settings.pd_python,
            "-c",
            (
                "from pathlib import Path\n"
                "from phase_diagrams import SourceRegistry\n"
                "from phase_diagrams.cli.common import _page_image\n"
                f"work = Path({str(RP.work_dir())!r})\n"
                f"dataset = Path({str(RP.dataset_dir())!r})\n"
                f"_page_image(SourceRegistry(dataset), work, {ref!r}, {int(page)})\n"
            ),
        ]
    try:
        subprocess.run(
            cmd,
            cwd=str(RP.repo_root()),
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _render_page_path(draft)
    return _render_page_path(draft)


def _copy_pipeline_png_as_base(png: Path, dest: Path, meta: dict[str, Any]) -> dict[str, Any]:
    """Use an extract/auto overlay as the session base when the page render is unavailable."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    from PIL.PngImagePlugin import PngInfo

    out = dict(meta)
    try:
        with Image.open(png) as im:
            rgb = im.convert("RGB")
            info = PngInfo()
            origin = out.get("pageOrigin") or [0, 0]
            info.add_text("pageOrigin", f"{int(origin[0])},{int(origin[1])}")
            rgb.save(dest, pnginfo=info)
            out["width"] = rgb.width
            out["height"] = rgb.height
        out["path"] = str(dest)
    except OSError:
        out["path"] = str(png)
    out["synthetic"] = False
    out["cleanScan"] = False
    return out


def _clean_scan_crop(
    draft: dict[str, Any],
    *,
    page_origin: tuple[int, int],
    width: int,
    height: int,
    dest: Path,
) -> dict[str, Any] | None:
    """Crop the atlas page raster (no drawn curves) for the canvas background."""
    render = _ensure_page_render(draft)
    if render is None:
        return None
    ox, oy = page_origin
    with Image.open(render) as page:
        page = page.convert("RGB")
        x1 = min(ox + width, page.width)
        y1 = min(oy + height, page.height)
        if x1 <= ox or y1 <= oy:
            return None
        crop = page.crop((ox, oy, x1, y1))
    dest.parent.mkdir(parents=True, exist_ok=True)
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text("pageOrigin", f"{ox},{oy}")
    crop.save(dest, pnginfo=info)
    return {
        "path": str(dest),
        "width": crop.width,
        "height": crop.height,
        "pageOrigin": [ox, oy],
        "synthetic": False,
        "cleanScan": True,
    }

