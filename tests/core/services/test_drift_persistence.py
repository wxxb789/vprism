from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from vprism.core.data.storage.duckdb_factory import VPrismDuckDBFactory
from vprism.core.models.base import DataPoint
from vprism.core.models.market import MarketType
from vprism.core.services.drift import DuckDBDriftMetricWriter, DriftService


@pytest.fixture()
def duckdb_conn():
    factory = VPrismDuckDBFactory()
    with factory.connection() as conn:
        yield conn


def _build_history(start: datetime) -> list[DataPoint]:
    history: list[DataPoint] = []
    for offset, (close_value, volume_value) in enumerate(
        [
            ("10", "100"),
            ("11", "110"),
            ("12", "115"),
            ("13", "120"),
        ]
    ):
        history.append(
            DataPoint(
                symbol="000001",
                market=MarketType.CN,
                timestamp=start + timedelta(days=offset),
                close_price=Decimal(close_value),
                volume=Decimal(volume_value),
            )
        )
    return history


def test_persists_rows_for_each_metric(duckdb_conn) -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    history = _build_history(start)

    def loader(*_: object) -> list[DataPoint]:
        return list(history)

    writer = DuckDBDriftMetricWriter(duckdb_conn)
    fixed_now = datetime(2024, 2, 1, 12, 0, tzinfo=UTC)
    service = DriftService(loader, metric_writer=writer, clock=lambda: fixed_now)

    result = service.compute("000001", MarketType.CN, window=3)

    rows = duckdb_conn.execute(
        """
        SELECT date, market, symbol, metric, value, status, "window", run_id, created_at
        FROM drift_metrics
        ORDER BY metric
        """
    ).fetchall()

    assert len(rows) == 6
    observed_run_ids = {row[7] for row in rows}
    assert observed_run_ids == {result.run_id}
    assert all(row[1] == MarketType.CN.value for row in rows)
    assert all(row[2] == "000001" for row in rows)
    assert rows[-1][0].isoformat() == "2024-01-04"
    metric_names = [row[3] for row in rows]
    assert "zscore_latest_close" in metric_names
    assert "zscore_latest_volume" in metric_names
    assert all(row[6] == 3 for row in rows)
    expected_created_at = fixed_now.replace(tzinfo=None)
    assert all(row[8] == expected_created_at for row in rows)


def test_generates_unique_run_ids_per_execution(duckdb_conn) -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    history = _build_history(start)

    def loader(*_: object) -> list[DataPoint]:
        return list(history)

    writer = DuckDBDriftMetricWriter(duckdb_conn)
    clock_values = [datetime(2024, 3, 1, tzinfo=UTC), datetime(2024, 3, 2, tzinfo=UTC)]

    def clock() -> datetime:
        return clock_values.pop(0)

    service = DriftService(loader, metric_writer=writer, clock=clock)

    first = service.compute("000001", MarketType.CN, window=3)
    second = service.compute("000001", MarketType.CN, window=3)

    assert first.run_id != second.run_id

    run_rows = duckdb_conn.execute(
        "SELECT run_id FROM drift_metrics ORDER BY created_at"
    ).fetchall()
    assert len(run_rows) == 12
    assert {value for (value,) in run_rows} == {first.run_id, second.run_id}
