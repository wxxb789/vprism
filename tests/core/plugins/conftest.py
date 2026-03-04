"""Shared fixtures for plugin tests."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


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
