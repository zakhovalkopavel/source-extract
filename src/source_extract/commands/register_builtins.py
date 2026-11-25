"""Register built-in CommandSpecs (diagram + table + history families)."""

from __future__ import annotations

from source_extract.commands.adapter_command_runner import AdapterCommandRunner
from source_extract.commands.command_catalog import CommandCatalog
from source_extract.commands.command_spec import CommandSpec
from source_extract.commands import common_params as P
from source_extract.params.param_spec import ParamSpec
from source_extract.params.param_type import ParamType

_PD = "phase-diagrams"


def _pd(command_id: str, title: str, description: str, params: list[ParamSpec], family: str = "diagrams") -> CommandSpec:
    return CommandSpec(
        command_id=command_id,
        title=title,
        description=description,
        params=[P.ADAPTER_ID, *params],
        adapter_id=_PD,
        family=family,
        run=AdapterCommandRunner(_PD, command_id),
    )


def register_builtins(catalog: CommandCatalog) -> None:
    """Populate the catalog with migration-phase commands."""
    catalog.register(
        _pd(
            "extract",
            "Extract binary",
            "Binary config → candidates, overlay, review, comparison",
            [P.SYSTEM_ID, P.DATASET, P.WORK_DIR, P.VERBOSE],
        )
    )
    catalog.register(
        _pd(
            "auto",
            "Auto ternary",
            "Fully automatic ternary from the page alone",
            [P.SYSTEM_ID, P.DATASET, P.WORK_DIR, P.STEP_C, P.FIGURE, P.TRIANGLE, P.CORNERS, P.VERBOSE],
        )
    )
    catalog.register(
        _pd(
            "trace-curves",
            "Trace curves",
            "Ternary curves config → candidate with polyline_wt",
            [P.SYSTEM_ID, P.DATASET, P.WORK_DIR, P.VERBOSE],
        )
    )
    catalog.register(
        _pd(
            "nodes",
            "Nodes",
            "Numbered junctions, edge points, invariants and rings",
            [
                P.SYSTEM_ID,
                P.DATASET,
                P.WORK_DIR,
                ParamSpec(
                    name="origin",
                    param_type=ParamType.INTEGER_LIST,
                    description="pixelOrigin as two numbers: --origin X Y",
                    group="calibration",
                    advanced=True,
                    cli_flags=("--origin",),
                ),
                P.VERBOSE,
            ],
        )
    )
    catalog.register(
        _pd(
            "detect-isotherms",
            "Detect isotherms",
            "Isotherms found on the page → isotherms/",
            [P.SYSTEM_ID, P.DATASET, P.WORK_DIR, P.STEP_C, P.VERBOSE],
        )
    )
    catalog.register(
        _pd(
            "index-figures",
            "Index figures",
            "Caption OCR → figure-index/<source>.json",
            [
                P.DATASET,
                P.WORK_DIR,
                ParamSpec(
                    name="source",
                    param_type=ParamType.STRING,
                    description="Source id in the adapter catalog",
                    default="slag-atlas-1995",
                    group="page",
                    cli_flags=("--source",),
                ),
                ParamSpec(
                    name="pages",
                    param_type=ParamType.STRING,
                    description="PDF page range, e.g. 40-200",
                    default="40-200",
                    group="page",
                    cli_flags=("--pages",),
                ),
                P.VERBOSE,
            ],
        )
    )
    catalog.register(
        _pd(
            "calibrate",
            "Calibrate binary",
            "Detect frame and ticks; print tick pixels and residuals",
            [P.SYSTEM_ID, P.DATASET, P.WORK_DIR, P.VERBOSE],
        )
    )
    catalog.register(
        _pd(
            "new",
            "New ternary",
            "Find figure, calibrate triangle → starting file + curves config",
            [
                P.SYSTEM_ID,
                P.DATASET,
                P.WORK_DIR,
                P.FIGURE,
                P.TRIANGLE,
                P.CORNERS,
                ParamSpec(
                    name="pubchem",
                    param_type=ParamType.BOOLEAN,
                    default=False,
                    description="Search PubChem for missing components",
                    cli_flags=("--pubchem",),
                    advanced=True,
                ),
                P.VERBOSE,
            ],
        )
    )
    catalog.register(
        _pd(
            "tile",
            "Tile",
            "Zoom tile with pixel rulers → tiles/",
            [
                P.DATASET,
                P.WORK_DIR,
                ParamSpec(
                    name="source",
                    param_type=ParamType.STRING,
                    default="slag-atlas-1995",
                    cli_flags=("--source",),
                    group="page",
                ),
                ParamSpec(
                    name="page",
                    param_type=ParamType.INTEGER,
                    required=True,
                    cli_flags=("--page",),
                    group="page",
                ),
                ParamSpec(
                    name="box",
                    param_type=ParamType.INTEGER_LIST,
                    required=True,
                    description="x0 y0 x1 y1",
                    cli_flags=("--box",),
                    group="page",
                ),
                ParamSpec(
                    name="scale",
                    param_type=ParamType.NUMBER,
                    default=1.0,
                    cli_flags=("--scale",),
                ),
                ParamSpec(
                    name="overlay",
                    param_type=ParamType.STRING,
                    cli_flags=("--overlay",),
                    advanced=True,
                ),
                P.VERBOSE,
            ],
        )
    )
    catalog.register(
        _pd(
            "auto-overlay",
            "Auto overlay",
            "Overlay from automatic data only",
            [P.SYSTEM_ID, P.DATASET, P.WORK_DIR, P.STEP_C, P.VERBOSE],
        )
    )
    catalog.register(
        _pd(
            "validate",
            "Validate dataset",
            "Validate the current dataset",
            [P.DATASET, P.WORK_DIR, P.VERBOSE],
        )
    )
    catalog.register(
        _pd(
            "promote",
            "Promote candidate",
            "Copy candidate into current dataset (with history + manifest)",
            [P.SYSTEM_ID, P.DATASET, P.WORK_DIR, P.VERBOSE],
        )
    )
    catalog.register(
        _pd(
            "compare",
            "Compare candidate",
            "Compare the candidate with the dataset file",
            [P.SYSTEM_ID, P.DATASET, P.WORK_DIR, P.VERBOSE],
        )
    )
    catalog.register(
        _pd(
            "nbs-index",
            "NBS index",
            "OCR and parse NSRDS-NBS 61 Table I",
            [
                P.DATASET,
                P.WORK_DIR,
                ParamSpec(
                    name="engine",
                    param_type=ParamType.ENUM,
                    description="page OCR engine",
                    default="vlm",
                    choices=("vlm", "tesseract"),
                    group="ink",
                    cli_flags=("--engine",),
                ),
                P.VERBOSE,
            ],
        )
    )
    from source_extract.commands.history_commands import register_history_commands
    from source_extract.commands.model_commands import register_model_commands

    register_history_commands(catalog)
    register_model_commands(catalog)
