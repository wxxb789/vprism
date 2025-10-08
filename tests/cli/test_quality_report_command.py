from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime

import duckdb
import pytest
from typer.testing import CliRunner

from vprism.cli import quality as quality_module
from vprism.cli.main import create_app
from vprism.core.data.schema import vprism_quality_metrics_table


class StubDuckDBFactory:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self._connection = connection

    @contextmanager
    def connection(self) -> duckdb.DuckDBPyConnection:
        yield self._connection


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def duckdb_connection(monkeypatch: pytest.MonkeyPatch) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(database=":memory:")
    vprism_quality_metrics_table.ensure(connection)
    monkeypatch.setattr(quality_module, "get_duckdb_factory", lambda: StubDuckDBFactory(connection))
    yield connection
    connection.close()


def _insert_sample_metrics(connection: duckdb.DuckDBPyConnection) -> None:
    connection.executemany(
        """
        INSERT INTO quality_metrics (date, market, supplier_symbol, metric, value, status, run_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                date(2024, 1, 5),
                "cn",
                "000001",
                "gap_ratio",
                0.0,
                "OK",
                "run-gap",
                datetime(2024, 1, 6, 12, 0, 0),
            ),
            (
                date(2024, 1, 5),
                "cn",
                "000002",
                "duplicate_count",
                2.0,
                "WARN",
                "run-dup",
                datetime(2024, 1, 6, 12, 5, 0),
            ),
        ],
    )


def test_report_renders_table_output(runner: CliRunner, duckdb_connection: duckdb.DuckDBPyConnection) -> None:
    _insert_sample_metrics(duckdb_connection)

    app = create_app()
    result = runner.invoke(app, ["quality", "report"])

    assert result.exit_code == 0, result.output
    assert "gap_ratio" in result.output
    assert "duplicate_count" in result.output
    assert "000001" in result.output
    assert "run-gap" in result.output


def test_report_renders_jsonl_output(runner: CliRunner, duckdb_connection: duckdb.DuckDBPyConnection) -> None:
    _insert_sample_metrics(duckdb_connection)

    app = create_app()
    result = runner.invoke(app, ["--format", "jsonl", "quality", "report"])

    assert result.exit_code == 0, result.output
    payloads = [json.loads(line) for line in result.output.strip().splitlines()]
    assert len(payloads) == 2
    for payload in payloads:
        assert {"metric", "value", "status", "run_id", "symbol"}.issubset(payload)
    metrics = {payload["metric"] for payload in payloads}
    assert metrics == {"gap_ratio", "duplicate_count"}


def test_report_emits_error_when_no_rows(runner: CliRunner, duckdb_connection: duckdb.DuckDBPyConnection) -> None:
    app = create_app()
    result = runner.invoke(app, ["quality", "report"])

    assert result.exit_code == 10
    assert "QUALITY_METRICS_NOT_FOUND" in result.stderr
