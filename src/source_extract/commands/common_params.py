"""Shared ParamSpecs reused across diagram / table commands."""

from __future__ import annotations

from source_extract.params.param_spec import ParamSpec
from source_extract.params.param_type import ParamType

ADAPTER_ID = ParamSpec(
    name="adapter_id",
    param_type=ParamType.STRING,
    description="Adapter id (default: phase-diagrams)",
    default="phase-diagrams",
    group="output",
    cli_flags=("--adapter",),
)

SYSTEM_ID = ParamSpec(
    name="system",
    param_type=ParamType.STRING,
    description="System id, e.g. mgo-sio2",
    required=True,
    positional=True,
    group="basic",
)

DATASET = ParamSpec(
    name="dataset",
    param_type=ParamType.PATH,
    description="Dataset / current root",
    default="shared/processed/phase-diagrams",
    group="output",
    cli_flags=("--dataset",),
)

WORK_DIR = ParamSpec(
    name="work_dir",
    param_type=ParamType.PATH,
    description="Working / scratch root",
    default="reports/phase-diagrams",
    group="output",
    cli_flags=("--work-dir",),
)

VERBOSE = ParamSpec(
    name="verbose",
    param_type=ParamType.BOOLEAN,
    description="Per-step log",
    default=False,
    group="basic",
    cli_flags=("-v", "--verbose"),
)

STEP_C = ParamSpec(
    name="step",
    param_type=ParamType.NUMBER,
    description="Isotherm interval °C",
    default=100.0,
    minimum=1.0,
    group="curves",
    cli_flags=("--step",),
)

FIGURE = ParamSpec(
    name="figure",
    param_type=ParamType.STRING,
    description="Figure number when the index has several",
    group="page",
    advanced=True,
    cli_flags=("--figure",),
)

TRIANGLE = ParamSpec(
    name="triangle",
    param_type=ParamType.INTEGER,
    description="Triangle number when the page has several",
    group="page",
    advanced=True,
    cli_flags=("--triangle",),
)

CORNERS = ParamSpec(
    name="corners",
    param_type=ParamType.STRING_LIST,
    description="Corner components TOP LEFT RIGHT",
    group="calibration",
    advanced=True,
    cli_flags=("--corners",),
)
