from __future__ import annotations

import duckdb

from vprism.core.data import schema


def test_quality_metrics_table_structure() -> None:
    vprism_conn = duckdb.connect(database=":memory:")

    schema.vprism_ensure_quality_metric_tables(vprism_conn)

    vprism_columns = vprism_conn.execute("PRAGMA table_info('quality_metrics')").fetchall()
    assert [vprism_row[1] for vprism_row in vprism_columns] == [
        "date",
        "market",
        "supplier_symbol",
        "metric",
        "value",
        "status",
        "run_id",
        "created_at",
    ]

    vprism_pk_columns = {vprism_row[1] for vprism_row in vprism_columns if vprism_row[5] > 0}
    assert vprism_pk_columns == {"date", "market", "metric", "run_id", "supplier_symbol"}


def test_quality_metric_ddl_idempotent() -> None:
    vprism_conn = duckdb.connect(database=":memory:")

    for vprism_ddl in schema.vprism_create_quality_metric_ddl():
        vprism_conn.execute(vprism_ddl)
    for vprism_ddl in schema.vprism_create_quality_metric_ddl():
        vprism_conn.execute(vprism_ddl)


def test_quality_metric_status_values() -> None:
    vprism_statuses = {status.value for status in schema.VPrismQualityMetricStatus}

    assert vprism_statuses == {"OK", "WARN", "FAIL"}
