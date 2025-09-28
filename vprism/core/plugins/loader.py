"""Utilities for discovering and loading VPrism CLI plugins."""

from __future__ import annotations

import logging
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass, field
from importlib import metadata
from typing import Any, Protocol

LOGGER = logging.getLogger(__name__)


@dataclass
class PluginLoadResult:
    """Represents the outcome of loading a single plugin."""

    plugin_id: str
    commands: tuple[str, ...] = field(default_factory=tuple)


class TyperLike(Protocol):
    registered_commands: list[Any]

    def command(self, *args: Any, **kwargs: Any): ...


class PluginLoader:
    """Discover and register VPrism CLI plugins."""

    def __init__(self, group: str = "vprism.plugins", logger: logging.Logger | None = None) -> None:
        self.group = group
        self.logger = logger or LOGGER

    def load_plugins(
        self,
        cli_app: TyperLike,
        services_registry: MutableMapping[str, object],
    ) -> list[PluginLoadResult]:
        """Load plugins and register their commands against the provided CLI app."""

        if not isinstance(services_registry, MutableMapping):
            msg = "services_registry must be a mutable mapping"
            raise TypeError(msg)

        results: list[PluginLoadResult] = []
        for entry_point in self._iter_entry_points():
            plugin_id = self._plugin_identifier(entry_point)
            self.logger.info("Loading plugin %s", plugin_id)
            try:
                plugin = entry_point.load()
            except Exception as exc:  # pragma: no cover - safety net
                self.logger.exception("Failed to load plugin %s: %s", plugin_id, exc)
                continue

            register = self._resolve_register_callable(plugin, plugin_id)
            if register is None:
                continue

            pre_commands = list(cli_app.registered_commands)
            pre_names = {cmd.name for cmd in pre_commands}

            try:
                register(cli_app, services_registry)
            except Exception as exc:
                cli_app.registered_commands = pre_commands
                self.logger.exception("Plugin %s raised during register: %s", plugin_id, exc)
                continue

            new_commands = [cmd for cmd in cli_app.registered_commands if cmd not in pre_commands]
            conflicting = [cmd for cmd in new_commands if cmd.name in pre_names]
            if conflicting:
                cli_app.registered_commands = pre_commands
                conflict_names = ", ".join(sorted({cmd.name for cmd in conflicting}))
                self.logger.warning(
                    "Plugin %s defines commands already registered (%s); skipping plugin.",
                    plugin_id,
                    conflict_names,
                )
                continue

            for cmd in new_commands:
                pre_names.add(cmd.name)

            command_names = tuple(cmd.name for cmd in new_commands)
            results.append(PluginLoadResult(plugin_id=plugin_id, commands=command_names))
            joined = ", ".join(command_names) if command_names else "no commands"
            self.logger.info("Plugin %s loaded with %s", plugin_id, joined)

        return results

    def _iter_entry_points(self) -> list[metadata.EntryPoint]:
        eps = metadata.entry_points()
        selected = (
            eps.select(group=self.group)
            if hasattr(eps, "select")
            else eps.get(self.group, [])  # type: ignore[assignment]
        )
        return list(selected)

    def _plugin_identifier(self, entry_point: metadata.EntryPoint) -> str:
        module = getattr(entry_point, "module", "<unknown>")
        attr = getattr(entry_point, "attr", None)
        if attr:
            return f"{module}:{attr}"
        return module

    def _resolve_register_callable(
        self, plugin: object, plugin_id: str
    ) -> Callable[[TyperLike, MutableMapping[str, object]], None] | None:
        if isinstance(plugin, Callable):
            return plugin
        register = getattr(plugin, "register", None)
        if callable(register):
            return register
        self.logger.warning("Plugin %s does not expose a register callable; skipping.", plugin_id)
        return None
