"""Confirm / export a reviewed draft (adapter current root + local confirmed)."""

from __future__ import annotations

from typing import Any

from source_extract.review.export import confirm_session, validate_session_for_confirm


class ConfirmExport:
    """Facade used by the review API."""

    @staticmethod
    def confirm(session: dict[str, Any]) -> dict[str, Any]:
        validate_session_for_confirm(session)
        return confirm_session(session)
