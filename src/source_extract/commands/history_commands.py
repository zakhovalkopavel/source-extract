"""history list / diff / prune commands."""

from __future__ import annotations

from typing import Any

from source_extract.adapters.adapter_registry import get_registry
from source_extract.commands.command_catalog import CommandCatalog
from source_extract.commands.command_spec import CommandSpec
from source_extract.params.param_spec import ParamSpec
from source_extract.params.param_type import ParamType
from source_extract.versioning.dataset_store import DatasetStore


def _store_for(adapter_id: str) -> DatasetStore:
    roots = get_registry().get(adapter_id).roots()
    return DatasetStore(roots.current, roots.history)


def _history_list(params: dict[str, Any]) -> int:
    adapter_id = params.get("adapter_id") or "phase-diagrams"
    dataset_id = params["dataset_id"]
    rows = _store_for(adapter_id).list_history(dataset_id)
    for row in rows:
        print(f"{row['version']}\t{row['path']}")
    if not rows:
        print("(no history)")
    return 0


def _history_diff(params: dict[str, Any]) -> int:
    adapter_id = params.get("adapter_id") or "phase-diagrams"
    diff = _store_for(adapter_id).diff(params["dataset_id"], params["version_a"], params["version_b"])
    print(diff)
    return 0


def _history_prune(params: dict[str, Any]) -> int:
    if not params.get("accepted"):
        print("Refusing prune without --accepted", flush=True)
        return 2
    adapter_id = params.get("adapter_id") or "phase-diagrams"
    n = _store_for(adapter_id).prune_accepted(params["dataset_id"])
    print(f"Pruned {n} history entries for {params['dataset_id']}")
    return 0


def register_history_commands(catalog: CommandCatalog) -> None:
    adapter = ParamSpec(
        name="adapter_id",
        param_type=ParamType.STRING,
        default="phase-diagrams",
        cli_flags=("--adapter",),
        group="output",
    )
    dataset = ParamSpec(
        name="dataset_id",
        param_type=ParamType.STRING,
        required=True,
        positional=True,
        description="Dataset / system id",
    )
    catalog.register(
        CommandSpec(
            command_id="history-list",
            title="History list",
            description="List history versions for a dataset",
            family="history",
            params=[adapter, dataset],
            run=_history_list,
        )
    )
    catalog.register(
        CommandSpec(
            command_id="history-diff",
            title="History diff",
            description="Diff two history versions",
            family="history",
            params=[
                adapter,
                dataset,
                ParamSpec(name="version_a", param_type=ParamType.STRING, required=True, positional=True),
                ParamSpec(name="version_b", param_type=ParamType.STRING, required=True, positional=True),
            ],
            run=_history_diff,
        )
    )
    catalog.register(
        CommandSpec(
            command_id="history-prune",
            title="History prune",
            description="Remove history once quality is accepted",
            family="history",
            params=[
                adapter,
                dataset,
                ParamSpec(
                    name="accepted",
                    param_type=ParamType.BOOLEAN,
                    default=False,
                    cli_flags=("--accepted",),
                ),
            ],
            run=_history_prune,
        )
    )
