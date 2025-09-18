from __future__ import annotations

import duckdb

from vprism.core.data import schema


def test_ensure_corporate_action_tables_creates_expected_columns() -> None:
    conn = duckdb.connect(database=":memory:")

    schema.ensure_corporate_action_tables(conn)

    corp_columns = [row[1] for row in conn.execute("PRAGMA table_info('corporate_actions')").fetchall()]
    adj_columns = [row[1] for row in conn.execute("PRAGMA table_info('adjustments')").fetchall()]
    corp_pk = [row[1] for row in conn.execute("PRAGMA table_info('corporate_actions')").fetchall() if row[5] > 0]
    adj_pk = [row[1] for row in conn.execute("PRAGMA table_info('adjustments')").fetchall() if row[5] > 0]

    assert corp_columns == [
        "market",
        "supplier_symbol",
        "event_type",
        "effective_date",
        "dividend_cash",
        "split_ratio",
        "raw_payload",
        "source",
        "batch_id",
        "ingest_time",
    ]
    assert adj_columns == [
        "market",
        "supplier_symbol",
        "date",
        "adj_factor_qfq",
        "adj_factor_hfq",
        "version",
        "build_time",
        "source_events_hash",
    ]
    assert corp_pk == [
        "market",
        "supplier_symbol",
        "event_type",
        "effective_date",
        "batch_id",
    ]
    assert adj_pk == ["market", "supplier_symbol", "date", "version"]


def test_create_corporate_action_ddl_exposes_statements() -> None:
    ddls = list(schema.create_corporate_action_ddl())

    assert any("CREATE TABLE IF NOT EXISTS corporate_actions" in ddl for ddl in ddls)
    assert any("CREATE TABLE IF NOT EXISTS adjustments" in ddl for ddl in ddls)
