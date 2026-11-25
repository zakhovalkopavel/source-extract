"""Console entry: ``source-extract <command> …``."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from source_extract import __version__
from source_extract.cli.arg_builder import ArgBuilder
from source_extract.commands.command_catalog import get_catalog


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="source-extract",
        description="Single entry point for source extract (adapters, commands, models).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for spec in get_catalog().list():
        ArgBuilder.add_command(sub, spec)
    return parser


def _params_from_args(args: argparse.Namespace) -> dict[str, Any]:
    data = dict(vars(args))
    data.pop("command", None)
    return {k: v for k, v in data.items() if v is not None}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    spec = get_catalog().get(args.command)
    try:
        return spec.execute(_params_from_args(args))
    except Exception as exc:  # noqa: BLE001
        print(f"[{args.command}] error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
