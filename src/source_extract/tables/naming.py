"""File naming for handbook table JSON (slug from title + table id)."""
from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def title_slug(title: str | None) -> str:
    """``CRITICAL PROPERTIES - ORGANIC`` → ``Critical_properties_of_organic``."""
    if not title:
        return ""
    text = title.strip()
    text = re.sub(r"\s*[-–—]\s*", "_of_", text)
    text = text.lower()
    text = _NON_ALNUM.sub("_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        return ""
    return text[0].upper() + text[1:]


def dataset_file_name(title: str | None, table_id: str) -> str:
    """``Critical_properties_…_(table_1-1).json`` from title + id."""
    slug = title_slug(title) or f"table_{table_id.replace('-', '_')}"
    return f"{slug}_(table_{table_id}).json"


def debug_file_name(title: str | None, table_id: str) -> str:
    """Same stem as the dataset file (written under a debug folder)."""
    return dataset_file_name(title, table_id)
