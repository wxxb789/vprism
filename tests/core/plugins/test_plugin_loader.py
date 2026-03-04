from __future__ import annotations

import typer

from tests.core.plugins.conftest import DummyEntryPoint, DummyEntryPoints
from vprism.core.plugins import PluginLoader


def sample_plugin(cli_app: typer.Typer, services_registry):
    @cli_app.command("greet")
    def greet():  # pragma: no cover - defined for Typer
        """Dummy command."""

    services_registry.setdefault("loaded", []).append("greet")


def test_plugin_loader_registers_commands(monkeypatch):
    app = typer.Typer()
    loader = PluginLoader()
    registry = {}
    entry_points = DummyEntryPoints([DummyEntryPoint("sample", sample_plugin)])
    monkeypatch.setattr("vprism.core.plugins.loader.metadata.entry_points", lambda: entry_points)

    results = loader.load_plugins(app, registry)

    assert registry == {"loaded": ["greet"]}
    assert [cmd.name for cmd in app.registered_commands] == ["greet"]
    assert len(results) == 1
    assert results[0].commands == ("greet",)
