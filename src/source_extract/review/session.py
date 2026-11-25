"""Review session public API (split across sibling modules)."""

from __future__ import annotations

from source_extract.review.contour_edits import (
    add_boundary,
    add_isotherm,
    add_point,
    cycle_arrow,
    delete_boundary,
    delete_isotherm,
    delete_point,
    delete_points_batch,
    move_point,
    remap_contour,
    retrace_contour,
    set_arrows,
    update_boundary,
    update_isotherm,
)
from source_extract.review.draft_resolver import (
    create_system_stub,
    draft_content_stats,
    list_available_systems,
    load_draft,
)
from source_extract.review.invariant_edits import (
    add_invariant,
    delete_invariant,
    move_invariant,
    move_node,
    update_invariant,
)
from source_extract.review.nodes_attach import merge_detected_isotherms
from source_extract.review.session_factory import (
    create_session,
    find_reusable_session,
    prune_duplicate_sessions,
    set_session_image,
)
from source_extract.review.session_public import public_session, reload_draft_from_disk
from source_extract.review.session_persist import (
    list_sessions,
    load_session,
    save_session,
    session_path,
    undo,
)
from source_extract.review.session_view import _build_view

__all__ = [
    "add_boundary",
    "add_invariant",
    "add_isotherm",
    "add_point",
    "create_session",
    "create_system_stub",
    "cycle_arrow",
    "delete_boundary",
    "delete_invariant",
    "delete_isotherm",
    "delete_point",
    "delete_points_batch",
    "draft_content_stats",
    "find_reusable_session",
    "list_available_systems",
    "list_sessions",
    "load_draft",
    "load_session",
    "merge_detected_isotherms",
    "move_invariant",
    "move_node",
    "move_point",
    "prune_duplicate_sessions",
    "public_session",
    "reload_draft_from_disk",
    "remap_contour",
    "retrace_contour",
    "save_session",
    "session_path",
    "set_arrows",
    "set_session_image",
    "undo",
    "update_boundary",
    "update_invariant",
    "update_isotherm",
    "_build_view",
]
