from __future__ import annotations

import duckdb

from vprism.core.data import schema


def test_drift_metrics_table_structure() -> None:
    conn = duckdb.connect(database=":memory:")

    schema.vprism_ensure_drift_metric_tables(conn)

    columns = conn.execute("PRAGMA table_info('drift_metrics')").fetchall()
    assert [row[1] for row in columns] == [
        "date",
        "market",
        "symbol",
        "metric",
        "value",
        "status",
        "window",
        "run_id",
        "created_at",
    ]

    pk_columns = {row[1] for row in columns if row[5] > 0}
    assert pk_columns == {"date", "market", "symbol", "metric", "window", "run_id"}


def test_drift_metric_ddl_is_idempotent() -> None:
    conn = duckdb.connect(database=":memory:")

    for ddl in schema.vprism_create_drift_metric_ddl():
        conn.execute(ddl)
    for ddl in schema.vprism_create_drift_metric_ddl():
        conn.execute(ddl)
