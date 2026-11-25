"""CLI/API commands for OCR region and model profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from source_extract.commands.command_catalog import CommandCatalog
from source_extract.commands.command_spec import CommandSpec
from source_extract.models.llm.llm_call_recorder import LlmCallRecorder
from source_extract.models.llm.llm_profiles import LLM_PROFILES
from source_extract.models.ocr.ocr_region_runner import OcrRegionRunner
from source_extract.params.param_spec import ParamSpec
from source_extract.params.param_type import ParamType


def _ocr_region(params: dict[str, Any]) -> int:
    image_path = Path(params["image"])
    box = tuple(int(x) for x in params["box"])  # type: ignore[assignment]
    if len(box) != 4:
        print("box must be x0 y0 x1 y1", flush=True)
        return 2
    runner = OcrRegionRunner()
    candidates = runner.ocr_region(
        image_path,
        (box[0], box[1], box[2], box[3]),
        engine=params.get("engine") or "page-ocr",
        language=params.get("language") or "eng",
        whitelist=params.get("whitelist"),
        psm=params.get("psm"),
        scale=float(params.get("scale") or 1.0),
        rotate=float(params.get("rotate") or 0.0),
        prompt=params.get("prompt"),
    )
    for c in candidates:
        print(c.to_dict())
    return 0 if candidates else 1


def _list_profiles(params: dict[str, Any]) -> int:
    for profile in LLM_PROFILES.values():
        print(f"{profile.profile_id}\t{profile.default_provider}\t{profile.description}")
    return 0


def _list_llm_calls(params: dict[str, Any]) -> int:
    limit = int(params.get("limit") or 20)
    for row in LlmCallRecorder().list_recent(limit):
        print(f"{row.get('id')}\t{row.get('provider')}\t{row.get('model')}\t{row.get('latencyMs')}")
    return 0


def register_model_commands(catalog: CommandCatalog) -> None:
    catalog.register(
        CommandSpec(
            command_id="ocr-region",
            title="OCR region",
            description="Re-OCR a pixel box with adjustable settings",
            family="models",
            params=[
                ParamSpec(name="image", param_type=ParamType.PATH, required=True, positional=True),
                ParamSpec(
                    name="box",
                    param_type=ParamType.INTEGER_LIST,
                    required=True,
                    description="x0 y0 x1 y1",
                    cli_flags=("--box",),
                ),
                ParamSpec(
                    name="engine",
                    param_type=ParamType.STRING,
                    default="page-ocr",
                    cli_flags=("--engine",),
                    group="ink",
                ),
                ParamSpec(name="language", param_type=ParamType.STRING, default="eng", cli_flags=("--language",)),
                ParamSpec(name="whitelist", param_type=ParamType.STRING, cli_flags=("--whitelist",), advanced=True),
                ParamSpec(name="psm", param_type=ParamType.INTEGER, cli_flags=("--psm",), advanced=True),
                ParamSpec(name="scale", param_type=ParamType.NUMBER, default=1.0, cli_flags=("--scale",)),
                ParamSpec(name="rotate", param_type=ParamType.NUMBER, default=0.0, cli_flags=("--rotate",), advanced=True),
                ParamSpec(name="prompt", param_type=ParamType.STRING, cli_flags=("--prompt",), advanced=True),
            ],
            run=_ocr_region,
        )
    )
    catalog.register(
        CommandSpec(
            command_id="models-profiles",
            title="Model profiles",
            description="List named LLM profiles",
            family="models",
            params=[],
            run=_list_profiles,
        )
    )
    catalog.register(
        CommandSpec(
            command_id="models-calls",
            title="Recorded LLM calls",
            description="List recent recorded LLM calls",
            family="models",
            params=[
                ParamSpec(name="limit", param_type=ParamType.INTEGER, default=20, cli_flags=("--limit",)),
            ],
            run=_list_llm_calls,
        )
    )
