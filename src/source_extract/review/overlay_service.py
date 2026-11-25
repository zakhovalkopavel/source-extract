"""Overlay path helpers for review sessions."""

from __future__ import annotations

from pathlib import Path

from source_extract.review.draft_image_paths import DraftImagePaths


class OverlayService:
    """Resolve overlay / draft image paths next to a draft JSON."""

    @staticmethod
    def sibling_overlay(draft_path: Path) -> Path | None:
        return DraftImagePaths.find(draft_path)
