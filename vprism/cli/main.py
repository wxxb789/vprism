"""Main entry point for the VPrism command line interface."""

from __future__ import annotations

from collections.abc import MutableMapping

import typer

from vprism.core.plugins import PluginLoader


def create_app() -> typer.Typer:
    """Create a Typer application instance for VPrism."""

    return typer.Typer(add_completion=False, help="VPrism command line interface")


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


app = create_app()
bootstrap_plugins(app)
