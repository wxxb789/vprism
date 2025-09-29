"""Main entry point for the VPrism command line interface."""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from pathlib import Path

import typer

from vprism.core.plugins import PluginLoader

from .data import register as register_data_commands
from .drift import register as register_drift_commands
from .formatters import create_formatter
from .symbol import register as register_symbol_commands


def create_app() -> typer.Typer:
    """Create a Typer application instance for VPrism."""

    app = typer.Typer(add_completion=False, help="VPrism command line interface")

    @app.callback()
    def main(
        ctx: typer.Context,
        format: str = typer.Option(
            "table",
            "--format",
            "-f",
            help="Output format (table or jsonl).",
            show_default=True,
        ),
        output: Path | None = typer.Option(
            None,
            "--output",
            "-o",
            help="Write output to a file instead of stdout.",
        ),
        log_level: str = typer.Option(
            "INFO",
            "--log-level",
            help="Root logging level.",
            show_default=True,
        ),
        no_color: bool = typer.Option(
            False,
            "--no-color",
            help="Disable colorized output for table format.",
        ),
    ) -> None:
        ctx.ensure_object(dict)
        normalized_format = format.strip().lower()
        try:
            # Validate formatter eagerly for immediate feedback on invalid options
            create_formatter(normalized_format, no_color=no_color)
        except ValueError as exc:
            raise typer.BadParameter(str(exc), param_hint="--format") from exc

        ctx.obj.update(
            {
                "format": normalized_format,
                "output_path": output,
                "log_level": log_level.upper(),
                "no_color": no_color,
            }
        )
        _configure_logging(log_level)

    register_data_commands(app)
    register_drift_commands(app)
    register_symbol_commands(app)
    return app


def bootstrap_plugins(
    cli_app: typer.Typer,
    *,
    services_registry: MutableMapping[str, object] | None = None,
    loader: PluginLoader | None = None,
) -> MutableMapping[str, object]:
    """Load CLI plugins using the provided loader."""

    if services_registry is not None and not isinstance(services_registry, MutableMapping):
        msg = "services_registry must be a mutable mapping"
        raise TypeError(msg)

    registry = services_registry or {}
    plugin_loader = loader or PluginLoader()
    plugin_loader.load_plugins(cli_app, registry)
    return registry


def _configure_logging(level_name: str) -> None:
    resolved = getattr(logging, level_name.upper(), None)
    if not isinstance(resolved, int):
        resolved = logging.INFO
    logging.basicConfig(level=resolved, force=True)


app = create_app()
bootstrap_plugins(app)
