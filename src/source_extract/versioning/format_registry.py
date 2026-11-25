"""Registered dataset format versions and change notes."""

from __future__ import annotations

from source_extract.versioning.format_version import FormatVersion

SYSTEM_JSON_V1 = FormatVersion(format_id="phase-diagram-system", version=1)
NBS_ENTRY_V1 = FormatVersion(format_id="nbs-entry", version=1)

_CHANGE_NOTES: dict[tuple[str, int], str] = {
    (SYSTEM_JSON_V1.format_id, SYSTEM_JSON_V1.version): "Initial system JSON shape (components, invariants, liquidus).",
    (NBS_ENTRY_V1.format_id, NBS_ENTRY_V1.version): "Initial NBS Table I entry shape.",
}


class FormatRegistry:
    """Lookup registered formats and change notes."""

    @staticmethod
    def get(format_id: str, version: int) -> FormatVersion:
        key = (format_id, version)
        if key not in _CHANGE_NOTES:
            raise KeyError(f"Unknown format {format_id}@v{version}")
        return FormatVersion(format_id=format_id, version=version)

    @staticmethod
    def change_note(format_id: str, version: int) -> str:
        return _CHANGE_NOTES[(format_id, version)]

    @staticmethod
    def list_formats() -> list[FormatVersion]:
        return [SYSTEM_JSON_V1, NBS_ENTRY_V1]
