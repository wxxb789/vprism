import duckdb

from vprism.core.data import schema


def test_reconciliation_tables_structure() -> None:
    conn = duckdb.connect(database=":memory:")

    schema.ensure_reconciliation_tables(conn)

    runs_columns = conn.execute("PRAGMA table_info('reconciliation_runs')").fetchall()
    assert [column[1] for column in runs_columns] == [
        "run_id",
        "market",
        "start",
        "end",
        "source_a",
        "source_b",
        "sample_size",
        "created_at",
        "pass",
        "warn",
        "fail",
        "p95_bp_diff",
    ]
    runs_pk = {column[1] for column in runs_columns if column[5] > 0}
    assert runs_pk == {"run_id"}

    diffs_columns = conn.execute("PRAGMA table_info('reconciliation_diffs')").fetchall()
    assert [column[1] for column in diffs_columns] == [
        "run_id",
        "symbol",
        "date",
        "close_a",
        "close_b",
        "close_bp_diff",
        "volume_a",
        "volume_b",
        "volume_ratio",
        "status",
    ]
    diffs_pk = {column[1] for column in diffs_columns if column[5] > 0}
    assert diffs_pk == {"run_id", "symbol", "date"}


def test_reconciliation_table_ddl_idempotent() -> None:
    conn = duckdb.connect(database=":memory:")

    for ddl in schema.create_reconciliation_ddl():
        conn.execute(ddl)
    for ddl in schema.create_reconciliation_ddl():
        conn.execute(ddl)
