"""Pydantic bodies for the review REST surface."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateSessionBody(BaseModel):
    systemId: str
    draftSource: str | None = None
    forceNew: bool = False


class ReloadDraftBody(BaseModel):
    draftSource: str | None = None


class PixelBody(BaseModel):
    x: float
    y: float


class MovePointBody(BaseModel):
    contourKind: Literal["boundary", "isotherm"]
    contourIndex: int
    pointIndex: int
    pixel: PixelBody


class DeletePointBody(BaseModel):
    contourKind: Literal["boundary", "isotherm"]
    contourIndex: int
    pointIndex: int


class BatchDeleteItem(BaseModel):
    type: Literal["invariant", "vertex", "node"]
    id: str | None = None
    kind: Literal["boundary", "isotherm"] | None = None
    index: int | None = None
    pointIndex: int | None = None


class DeletePointsBatchBody(BaseModel):
    items: list[BatchDeleteItem] = Field(min_length=1)


class AddPointBody(BaseModel):
    contourKind: Literal["boundary", "isotherm"]
    contourIndex: int
    pixel: PixelBody
    afterIndex: int | None = None


class ArrowsBody(BaseModel):
    contourIndex: int
    arrows: list[str]


class CycleArrowBody(BaseModel):
    contourIndex: int
    segmentIndex: int = 0


class RetraceBody(BaseModel):
    contourKind: Literal["boundary", "isotherm"]
    contourIndex: int
    waypoints: list[PixelBody] = Field(min_length=2)


class AddIsothermBody(BaseModel):
    field: str
    temperature_C: float
    waypoints: list[PixelBody] = Field(min_length=2)
    dashed: bool = False
    replaceIndex: int | None = None


class AddBoundaryBody(BaseModel):
    waypoints: list[PixelBody] = Field(min_length=2)
    fields: list[str | None] | None = None
    dashed: bool = False


class UpdateBoundaryBody(BaseModel):
    contourIndex: int
    fields: list[str | None] | None = None
    dashed: bool | None = None


class DeleteBoundaryBody(BaseModel):
    contourIndex: int


class UpdateIsothermBody(BaseModel):
    contourIndex: int
    field: str | None = None
    temperature_C: float | None = None
    dashed: bool | None = None


class DeleteIsothermBody(BaseModel):
    contourIndex: int


class MoveInvariantBody(BaseModel):
    pointId: str
    pixel: PixelBody


class MoveNodeBody(BaseModel):
    nodeIndex: int
    pixel: PixelBody


class MoveCalibrationCornerBody(BaseModel):
    """``componentIndex`` matches ``view.components`` / ``view.cornersImage`` order."""

    componentIndex: int
    pixel: PixelBody


class AddInvariantBody(BaseModel):
    pointId: str
    pixel: PixelBody
    temperature_C: float | None = None
    phases: list[str] | None = None
    reaction: str | None = None


class UpdateInvariantBody(BaseModel):
    temperature_C: float | None = None
    phases: list[str] | None = None
    reaction: str | None = None
    newId: str | None = None


class RemapContourBody(BaseModel):
    fromKind: Literal["boundary", "isotherm"]
    contourIndex: int
    toKind: Literal["boundary", "isotherm"]
    field: str | None = None
    temperature_C: float | None = None
    fields: list[str | None] | None = None
    dashed: bool | None = None


class AnalyzeBody(BaseModel):
    systemId: str
    adapterId: str = "phase-diagrams"
    force: bool = False
    figure: str | None = None
    triangle: int | None = None
    corners: list[str] | None = None
    step: float = 100.0
    sessionId: str | None = None


class CardUpdateBody(BaseModel):
    status: str
    answer: str | None = None


class CreateStubBody(BaseModel):
    systemId: str
    components: list[str]
    systemName: str | None = None
    figure: str | None = None
    printedPage: int | None = None
    pdfPage: int | None = None
