"""Geometry edit endpoints (points, contours, invariants)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from source_extract.api.routers.review_schemas import (
    AddBoundaryBody,
    AddInvariantBody,
    AddIsothermBody,
    AddPointBody,
    ArrowsBody,
    CycleArrowBody,
    DeleteBoundaryBody,
    DeleteIsothermBody,
    DeletePointBody,
    DeletePointsBatchBody,
    MoveInvariantBody,
    MoveNodeBody,
    MovePointBody,
    RemapContourBody,
    RetraceBody,
    UpdateBoundaryBody,
    UpdateInvariantBody,
    UpdateIsothermBody,
)
from source_extract.api.routers.review_sessions import _load
from source_extract.review import session as S

router = APIRouter(tags=["review"])


def _ok(session: dict[str, Any]) -> dict[str, Any]:
    return S.public_session(session)


@router.post("/sessions/{session_id}/points/move")
def move_point(session_id: str, body: MovePointBody) -> dict[str, Any]:
    try:
        return _ok(
            S.move_point(
                _load(session_id),
                contour_kind=body.contourKind,
                contour_index=body.contourIndex,
                point_index=body.pointIndex,
                image_pixel=[body.pixel.x, body.pixel.y],
            )
        )
    except (IndexError, ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/points/delete")
def delete_point(session_id: str, body: DeletePointBody) -> dict[str, Any]:
    try:
        return _ok(
            S.delete_point(
                _load(session_id),
                contour_kind=body.contourKind,
                contour_index=body.contourIndex,
                point_index=body.pointIndex,
            )
        )
    except (IndexError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/points/delete-batch")
def delete_points_batch(session_id: str, body: DeletePointsBatchBody) -> dict[str, Any]:
    try:
        return _ok(S.delete_points_batch(_load(session_id), items=[it.model_dump() for it in body.items]))
    except (IndexError, ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/points/add")
def add_point(session_id: str, body: AddPointBody) -> dict[str, Any]:
    try:
        return _ok(
            S.add_point(
                _load(session_id),
                contour_kind=body.contourKind,
                contour_index=body.contourIndex,
                image_pixel=[body.pixel.x, body.pixel.y],
                after_index=body.afterIndex,
            )
        )
    except (IndexError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/arrows")
def set_arrows(session_id: str, body: ArrowsBody) -> dict[str, Any]:
    try:
        return _ok(S.set_arrows(_load(session_id), contour_index=body.contourIndex, arrows=body.arrows))
    except (IndexError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/arrows/cycle")
def cycle_arrow(session_id: str, body: CycleArrowBody) -> dict[str, Any]:
    try:
        return _ok(
            S.cycle_arrow(
                _load(session_id),
                contour_index=body.contourIndex,
                segment_index=body.segmentIndex,
            )
        )
    except (IndexError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/retrace")
def retrace(session_id: str, body: RetraceBody) -> dict[str, Any]:
    try:
        return _ok(
            S.retrace_contour(
                _load(session_id),
                contour_kind=body.contourKind,
                contour_index=body.contourIndex,
                image_waypoints=[[p.x, p.y] for p in body.waypoints],
            )
        )
    except (IndexError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/isotherms")
def add_isotherm(session_id: str, body: AddIsothermBody) -> dict[str, Any]:
    try:
        return _ok(
            S.add_isotherm(
                _load(session_id),
                field=body.field,
                temperature_C=body.temperature_C,
                image_waypoints=[[p.x, p.y] for p in body.waypoints],
                dashed=body.dashed,
                replace_index=body.replaceIndex,
            )
        )
    except (ValueError, IndexError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/isotherms/update")
def update_isotherm(session_id: str, body: UpdateIsothermBody) -> dict[str, Any]:
    try:
        return _ok(
            S.update_isotherm(
                _load(session_id),
                contour_index=body.contourIndex,
                field=body.field,
                temperature_C=body.temperature_C,
                dashed=body.dashed,
            )
        )
    except (IndexError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/isotherms/delete")
def delete_isotherm(session_id: str, body: DeleteIsothermBody) -> dict[str, Any]:
    try:
        return _ok(S.delete_isotherm(_load(session_id), contour_index=body.contourIndex))
    except IndexError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/boundaries")
def add_boundary(session_id: str, body: AddBoundaryBody) -> dict[str, Any]:
    try:
        return _ok(
            S.add_boundary(
                _load(session_id),
                image_waypoints=[[p.x, p.y] for p in body.waypoints],
                fields=body.fields,
                dashed=body.dashed,
            )
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/boundaries/update")
def update_boundary(session_id: str, body: UpdateBoundaryBody) -> dict[str, Any]:
    try:
        return _ok(
            S.update_boundary(
                _load(session_id),
                contour_index=body.contourIndex,
                fields=body.fields,
                dashed=body.dashed,
            )
        )
    except (IndexError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/boundaries/delete")
def delete_boundary(session_id: str, body: DeleteBoundaryBody) -> dict[str, Any]:
    try:
        return _ok(S.delete_boundary(_load(session_id), contour_index=body.contourIndex))
    except IndexError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/invariants/move")
def move_invariant(session_id: str, body: MoveInvariantBody) -> dict[str, Any]:
    try:
        return _ok(
            S.move_invariant(
                _load(session_id),
                point_id=body.pointId,
                image_pixel=[body.pixel.x, body.pixel.y],
            )
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/nodes/move")
def move_node(session_id: str, body: MoveNodeBody) -> dict[str, Any]:
    try:
        return _ok(
            S.move_node(
                _load(session_id),
                node_index=body.nodeIndex,
                image_pixel=[body.pixel.x, body.pixel.y],
            )
        )
    except (IndexError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/invariants")
def add_invariant(session_id: str, body: AddInvariantBody) -> dict[str, Any]:
    try:
        return _ok(
            S.add_invariant(
                _load(session_id),
                point_id=body.pointId,
                image_pixel=[body.pixel.x, body.pixel.y],
                temperature_C=body.temperature_C,
                phases=body.phases,
                reaction=body.reaction,
            )
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/invariants/{point_id}")
def update_invariant(session_id: str, point_id: str, body: UpdateInvariantBody) -> dict[str, Any]:
    try:
        return _ok(
            S.update_invariant(
                _load(session_id),
                point_id=point_id,
                temperature_C=body.temperature_C,
                phases=body.phases,
                reaction=body.reaction,
                new_id=body.newId,
            )
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/sessions/{session_id}/invariants/{point_id}")
def delete_invariant(session_id: str, point_id: str) -> dict[str, Any]:
    try:
        return _ok(S.delete_invariant(_load(session_id), point_id=point_id))
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sessions/{session_id}/remap")
def remap_contour(session_id: str, body: RemapContourBody) -> dict[str, Any]:
    try:
        return _ok(
            S.remap_contour(
                _load(session_id),
                from_kind=body.fromKind,
                contour_index=body.contourIndex,
                to_kind=body.toKind,
                field=body.field,
                temperature_C=body.temperature_C,
                fields=body.fields,
                dashed=body.dashed,
            )
        )
    except (IndexError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
