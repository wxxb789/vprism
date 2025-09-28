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
