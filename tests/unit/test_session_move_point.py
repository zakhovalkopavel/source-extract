"""Move point updates polyline_wt and supports undo."""

from __future__ import annotations

import json
from pathlib import Path

from source_extract.review import session as S


def _ternary_draft() -> dict:
    return {
        "system": "A-B-C",
        "components": ["A", "B", "C"],
        "digitization": {
            "calibration": {"A": [100, 100], "B": [500, 100], "C": [300, 400]},
            "method": "test",
        },
        "phases": ["A", "B"],
        "invariantPoints": [],
        "boundaryCurves": [
            {
                "fields": ["A", "B"],
                "path": [],
                "arrows": ["?"],
                "polyline_wt": [[100, 0, 0], [50, 50, 0], [0, 100, 0]],
            }
        ],
        "isotherms": [],
    }


def test_move_point_updates_polyline_and_undo(tmp_path: Path, monkeypatch) -> None:
    work = tmp_path / "work"
    dataset = tmp_path / "dataset"
    (work / "candidates").mkdir(parents=True)
    (dataset / "systems").mkdir(parents=True)
    (dataset / "configs").mkdir(parents=True)
    draft = _ternary_draft()
    (work / "candidates" / "abc.json").write_text(json.dumps(draft), encoding="utf-8")
    monkeypatch.setenv("SE_WORK_ROOT", str(work))
    monkeypatch.setenv("SE_DATASET_ROOT", str(dataset))

    session = S.create_session("abc", preferred_source="candidates", force_new=True)
    before = list(session["draft"]["boundaryCurves"][0]["polyline_wt"][0])
    # Image pixel near triangle centre (pageOrigin may be synthetic crop offset)
    origin = session["image"]["pageOrigin"]
    img_x = 300.0 - float(origin[0])
    img_y = 200.0 - float(origin[1])
    session = S.move_point(
        session,
        contour_kind="boundary",
        contour_index=0,
        point_index=0,
        image_pixel=[img_x, img_y],
    )
    after = session["draft"]["boundaryCurves"][0]["polyline_wt"][0]
    assert after != before
    assert len(session["undo"]) == 1
    session = S.undo(session)
    assert session["draft"]["boundaryCurves"][0]["polyline_wt"][0] == before
