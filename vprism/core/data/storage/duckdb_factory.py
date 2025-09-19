"""Utility helpers for creating DuckDB connections in tests and local runs."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import duckdb

try:  # pragma: no cover - type checking compatibility
    from duckdb import DuckDBPyConnection
except Exception:  # pragma: no cover
    DuckDBPyConnection = "DuckDBPyConnection"  # type: ignore[misc,assignment]


if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path


@dataclass(frozen=True)
class DuckDBFactoryConfig:
    """Configuration applied to DuckDB connections produced by the factory."""

    database: str | Path = ":memory:"
    read_only: bool = False
    pragmas: Mapping[str, object] = field(
        default_factory=lambda: {"threads": 1}
    )


class VPrismDuckDBFactory:
    """Factory that yields configured DuckDB connections."""

    def __init__(self, config: DuckDBFactoryConfig | None = None) -> None:
        self._config = config or DuckDBFactoryConfig()

    def create_connection(self) -> DuckDBPyConnection:
        """Create and return a configured DuckDB connection."""

        conn = duckdb.connect(
            database=str(self._config.database), read_only=self._config.read_only
        )
        self._apply_pragmas(conn)
        return conn

    @contextmanager
    def connection(self) -> Iterator[DuckDBPyConnection]:
        """Context manager that yields a configured DuckDB connection."""

        conn = self.create_connection()
        try:
            yield conn
        finally:
            conn.close()

    def _apply_pragmas(self, conn: DuckDBPyConnection) -> None:
        for setting, value in self._config.pragmas.items():
            conn.execute(f"SET {setting}=?", [value])


__all__ = ["VPrismDuckDBFactory", "DuckDBFactoryConfig"]
