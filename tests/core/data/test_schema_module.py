from __future__ import annotations

import duckdb

from vprism.core.data import schema


def test_create_baseline_tables_contains_expected_columns() -> None:
    conn = duckdb.connect(database=":memory:")

    schema.ensure_baseline_tables(conn)

    raw_columns = [row[1] for row in conn.execute("PRAGMA table_info('raw_schema')").fetchall()]
    normalization_columns = [row[1] for row in conn.execute("PRAGMA table_info('normalization_schema')").fetchall()]

    assert raw_columns == [
        "supplier_symbol",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "provider",
    ]

    assert normalization_columns == [
        "supplier_symbol",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "provider",
        "market",
        "tz_offset",
        "currency",
        "c_symbol",
    ]


def test_create_baseline_ddl_exposes_statements() -> None:
    ddls = list(schema.create_baseline_ddl())

    assert any("CREATE TABLE IF NOT EXISTS raw_schema" in ddl for ddl in ddls)
    assert any("CREATE TABLE IF NOT EXISTS normalization_schema" in ddl for ddl in ddls)
