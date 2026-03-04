from __future__ import annotations

import typer

from tests.core.plugins.conftest import DummyEntryPoint, DummyEntryPoints
from vprism.core.plugins import PluginLoader


def base_plugin(cli_app: typer.Typer, services_registry):
    @cli_app.command("alpha")
    def alpha():  # pragma: no cover - Typer command body not executed
        """Base command."""

    services_registry.setdefault("commands", []).append("alpha")


def conflicting_plugin(cli_app: typer.Typer, services_registry):
    @cli_app.command("alpha")
    def alpha():  # pragma: no cover - Typer command body not executed
        """Conflicting command."""

    services_registry.setdefault("commands", []).append("alpha-conflict")


def test_conflicting_plugin_is_skipped(monkeypatch, caplog):
    app = typer.Typer()
    loader = PluginLoader()
    registry = {}
    entry_points = DummyEntryPoints(
        [
            DummyEntryPoint("base", base_plugin),
            DummyEntryPoint("conflict", conflicting_plugin),
        ]
    )
    monkeypatch.setattr("vprism.core.plugins.loader.metadata.entry_points", lambda: entry_points)
    caplog.set_level("WARNING")

    results = loader.load_plugins(app, registry)

    assert [cmd.name for cmd in app.registered_commands] == ["alpha"]
    assert results[0].commands == ("alpha",)
    assert len(results) == 1
    assert registry == {"commands": ["alpha", "alpha-conflict"]}
    assert "skipping plugin" in caplog.text.lower()
