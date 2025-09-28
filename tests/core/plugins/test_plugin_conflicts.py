from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import typer

from vprism.core.plugins import PluginLoader


@dataclass
class DummyEntryPoint:
    name: str
    target: object

    @property
    def group(self) -> str:
        return "vprism.plugins"

    @property
    def module(self) -> str:
        return getattr(self.target, "__module__", "tests")

    @property
    def attr(self) -> str:
        return getattr(self.target, "__name__", "register")

    def load(self) -> object:
        return self.target


class DummyEntryPoints(list[DummyEntryPoint]):
    def __init__(self, items: Iterable[DummyEntryPoint]):
        if not isinstance(items, Iterable):
            raise TypeError("items must be iterable")
        super().__init__(items)

    def select(self, *, group: str) -> DummyEntryPoints:
        return DummyEntryPoints(ep for ep in self if ep.group == group)


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
