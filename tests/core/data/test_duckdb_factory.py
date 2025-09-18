from __future__ import annotations

import duckdb
import pytest

from vprism.core.data.storage.duckdb_factory import (
    DuckDBFactoryConfig,
    VPrismDuckDBFactory,
)


def test_connection_factory_context_yields_and_closes_connection() -> None:
    factory = VPrismDuckDBFactory()

    with factory.connection() as conn:
        result = conn.execute("SELECT 1").fetchone()[0]
        assert result == 1

    with pytest.raises(duckdb.Error):
        conn.execute("SELECT 1")


def test_connection_factory_applies_pragmas() -> None:
    factory = VPrismDuckDBFactory(
        DuckDBFactoryConfig(pragmas={"threads": 3})
    )

    with factory.connection() as conn:
        threads = conn.execute("SELECT current_setting('threads')").fetchone()[0]

    assert threads == 3


def test_create_connection_returns_active_connection() -> None:
    factory = VPrismDuckDBFactory()

    conn = factory.create_connection()
    try:
        assert conn.execute("SELECT 2").fetchone()[0] == 2
    finally:
        conn.close()
