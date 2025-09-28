"""Utility helpers shared across CLI commands."""

from __future__ import annotations

import json
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, TextIO

import typer

from .constants import VALIDATION_EXIT_CODE
from .formatters import OutputFormatter, create_formatter


@dataclass(slots=True)
class CLIOptions:
    """Resolved options derived from the Typer context."""

    format: str = "table"
    output_path: Path | None = None
    no_color: bool = False


def get_cli_options(ctx: typer.Context) -> CLIOptions:
    """Extract :class:`CLIOptions` from the Typer context object."""

    ctx.ensure_object(dict)
    data = ctx.obj or {}
    return CLIOptions(
        format=str(data.get("format", "table")),
        output_path=data.get("output_path"),
        no_color=bool(data.get("no_color", False)),
    )


def prepare_output(ctx: typer.Context) -> tuple[OutputFormatter, TextIO, ExitStack, CLIOptions]:
    """Resolve formatter and writable stream for the current command."""

    options = get_cli_options(ctx)
    try:
        formatter = create_formatter(options.format, no_color=options.no_color)
    except ValueError as exc:  # pragma: no cover - validated at callback, safeguard for manual use
        _emit_error("INVALID_FORMAT", str(exc))
        raise typer.Exit(code=VALIDATION_EXIT_CODE) from exc

    stack = ExitStack()
    stream: TextIO
    if options.output_path is not None:
        try:
            stream = stack.enter_context(open(options.output_path, "w", encoding="utf-8"))
        except OSError as exc:
            stack.close()
            _emit_error("OUTPUT_WRITE_ERROR", f"Unable to open '{options.output_path}': {exc}")
            raise typer.Exit(code=VALIDATION_EXIT_CODE) from exc
    else:
        stream = sys.stdout

    return formatter, stream, stack, options


def emit_error(message: str, code: str, *, details: Mapping[str, object] | None = None) -> None:
    """Print a structured error payload to stderr."""

    payload: dict[str, object] = {"code": code, "message": message}
    if details:
        payload["details"] = _sanitize_details(details)
    typer.echo(json.dumps(payload, ensure_ascii=False, default=str), err=True)


def _emit_error(code: str, message: str, details: Mapping[str, object] | None = None) -> None:
    payload: dict[str, object] = {"code": code, "message": message}
    if details:
        payload["details"] = _sanitize_details(details)
    typer.echo(json.dumps(payload, ensure_ascii=False, default=str), err=True)


def _sanitize_details(details: Mapping[str, object]) -> Mapping[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in details.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = value
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            sanitized[key] = [str(item) for item in value]
        else:
            sanitized[key] = str(value)
    return sanitized


__all__ = ["CLIOptions", "get_cli_options", "prepare_output", "emit_error"]
