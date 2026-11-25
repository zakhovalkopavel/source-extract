"""Draft resolve prefers rich candidates over empty auto-full."""

from __future__ import annotations

import json
from pathlib import Path

from source_extract.review import review_paths as RP
from source_extract.review.draft_resolver import _resolve_draft_path, draft_content_stats


def test_resolve_prefers_rich_candidate(tmp_path: Path, monkeypatch) -> None:
    work = tmp_path / "work"
    dataset = tmp_path / "dataset"
    (work / "auto-full").mkdir(parents=True)
    (work / "candidates").mkdir(parents=True)
    (dataset / "systems").mkdir(parents=True)

    empty = {"components": ["A", "B", "C"], "boundaryCurves": [], "isotherms": [], "invariantPoints": []}
    rich = {
        "components": ["A", "B", "C"],
        "boundaryCurves": [{"polyline_wt": [[100, 0, 0], [0, 100, 0]]}],
        "isotherms": [],
        "invariantPoints": [{"id": "p1"}],
    }
    (work / "auto-full" / "sys.json").write_text(json.dumps(empty), encoding="utf-8")
    (work / "candidates" / "sys.json").write_text(json.dumps(rich), encoding="utf-8")

    monkeypatch.setenv("SE_WORK_ROOT", str(work))
    monkeypatch.setenv("SE_DATASET_ROOT", str(dataset))
    # Clear any cached Path usage — functions read env each call
    kind, path = _resolve_draft_path("sys")
    assert kind == "candidates"
    assert path.name == "sys.json"
    stats = draft_content_stats("sys")
    assert stats["contentScore"] > 0
    assert stats["n_boundaries"] == 1
    assert RP.work_dir() == work
