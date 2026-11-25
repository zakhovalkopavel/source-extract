"""Build argparse from CommandSpec ParamSpecs."""

from __future__ import annotations

import argparse

from source_extract.commands.command_spec import CommandSpec
from source_extract.params.param_type import ParamType


class ArgBuilder:
    """Derive CLI flags from ParamSpec lists."""

    @staticmethod
    def add_command(sub: argparse._SubParsersAction, spec: CommandSpec) -> None:
        parser = sub.add_parser(spec.command_id, help=spec.description)
        for param in spec.params:
            ArgBuilder._add_param(parser, param)

    @staticmethod
    def _add_param(parser: argparse.ArgumentParser, param) -> None:  # type: ignore[no-untyped-def]
        kwargs: dict = {"help": param.description or param.name}
        if param.param_type == ParamType.BOOLEAN:
            flags = param.cli_flags or (f"--{param.name.replace('_', '-')}",)
            parser.add_argument(*flags, action="store_true", default=bool(param.default), **kwargs)
            return
        if param.positional and param.required:
            parser.add_argument(param.name, **kwargs)
            return
        if param.positional and not param.required:
            parser.add_argument(param.name, nargs="?", default=param.default, **kwargs)
            return
        flags = param.cli_flags or (f"--{param.name.replace('_', '-')}",)
        if param.param_type in {ParamType.INTEGER_LIST, ParamType.STRING_LIST}:
            parser.add_argument(*flags, nargs="+", default=param.default, **kwargs)
            return
        if param.param_type == ParamType.INTEGER:
            kwargs["type"] = int
        elif param.param_type == ParamType.NUMBER:
            kwargs["type"] = float
        if param.choices:
            kwargs["choices"] = list(param.choices)
        if param.default is not None:
            kwargs["default"] = param.default
        elif param.required:
            kwargs["required"] = True
        parser.add_argument(*flags, **kwargs)
