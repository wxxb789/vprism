from datetime import UTC, datetime
from decimal import Decimal
from typing import Sequence

import pytest

from vprism.core.data.storage.duckdb_factory import VPrismDuckDBFactory
from vprism.core.models.base import DataPoint
from vprism.core.models.market import MarketType
from vprism.core.services.reconciliation import (
    DuckDBReconciliationWriter,
    PriceSeriesLoader,
    ReconciliationService,
)


@pytest.fixture()
def duckdb_conn():
    factory = VPrismDuckDBFactory()
    with factory.connection() as conn:
        yield conn


def _make_point(symbol: str, day: datetime, close: str, volume: str, provider: str) -> DataPoint:
    return DataPoint(
        symbol=symbol,
        market=MarketType.CN,
        timestamp=day,
        close_price=Decimal(close),
        volume=Decimal(volume),
        provider=provider,
    )


def _loader_factory(data: dict[str, Sequence[DataPoint]]) -> PriceSeriesLoader:
    def _loader(symbol: str, market: MarketType, start, end) -> Sequence[DataPoint]:
        return data.get(symbol, [])

    return _loader


def test_persists_run_and_diff_rows(duckdb_conn) -> None:
    symbol = "BBB"
    start = datetime(2024, 1, 1, tzinfo=UTC)
    provider_a = {
        symbol: [
            _make_point(symbol, start, "100", "1000", "A"),
            _make_point(symbol, start.replace(day=2), "100.06", "1000", "A"),
            _make_point(symbol, start.replace(day=3), "100.12", "1800", "A"),
        ]
    }
    provider_b = {
        symbol: [
            _make_point(symbol, start, "100", "1000", "B"),
            _make_point(symbol, start.replace(day=2), "100", "1000", "B"),
            _make_point(symbol, start.replace(day=3), "100", "900", "B"),
        ]
    }

    writer = DuckDBReconciliationWriter(duckdb_conn)
    fixed_now = datetime(2024, 2, 1, 12, 0, tzinfo=UTC)
    service = ReconciliationService(
        _loader_factory(provider_a),
        _loader_factory(provider_b),
        source_a="akshare",
        source_b="yfinance",
        run_writer=writer.write_run,
        diff_writer=writer.write_diff,
        clock=lambda: fixed_now,
        run_id_factory=lambda: "run-001",
    )

    result = service.reconcile([symbol], MarketType.CN, (start.date(), start.replace(day=3).date()))

    run_row = duckdb_conn.execute(
        """
        SELECT run_id, market, "start", "end", source_a, source_b, sample_size, created_at,
               "pass", "warn", "fail", p95_bp_diff
        FROM reconciliation_runs
        """
    ).fetchone()

    assert run_row is not None
    assert run_row[0] == "run-001"
    assert run_row[1] == MarketType.CN.value
    assert run_row[2].isoformat() == "2024-01-01"
    assert run_row[3].isoformat() == "2024-01-03"
    assert run_row[4] == "akshare"
    assert run_row[5] == "yfinance"
    assert run_row[6] == 1
    assert run_row[7] == fixed_now.replace(tzinfo=None)
    assert run_row[8] == 1
    assert run_row[9] == 1
    assert run_row[10] == 1
    assert pytest.approx(run_row[11], rel=1e-6) == 11.4

    diff_rows = duckdb_conn.execute(
        """
        SELECT run_id, symbol, date, close_bp_diff, status
        FROM reconciliation_diffs
        ORDER BY date
        """
    ).fetchall()

    assert len(diff_rows) == 3
    assert all(row[0] == "run-001" for row in diff_rows)
    statuses = [row[4] for row in diff_rows]
    assert statuses.count("PASS") == 1
    assert statuses.count("WARN") == 1
    assert statuses.count("FAIL") == 1
    assert result.run_id == "run-001"


def test_generates_distinct_run_ids(duckdb_conn) -> None:
    symbol = "ZZZ"
    day = datetime(2024, 3, 1, tzinfo=UTC)
    provider_a = {symbol: [_make_point(symbol, day, "10", "100", "A")]}
    provider_b = {symbol: [_make_point(symbol, day, "10", "100", "B")]}

    writer = DuckDBReconciliationWriter(duckdb_conn)
    run_ids = ["run-a", "run-b"]
    clock_values = [datetime(2024, 3, 10, tzinfo=UTC), datetime(2024, 3, 11, tzinfo=UTC)]

    def factory() -> str:
        return run_ids.pop(0)

    def clock() -> datetime:
        return clock_values.pop(0)

    service = ReconciliationService(
        _loader_factory(provider_a),
        _loader_factory(provider_b),
        source_a="akshare",
        source_b="yfinance",
        run_writer=writer.write_run,
        diff_writer=writer.write_diff,
        clock=clock,
        run_id_factory=factory,
    )

    first = service.reconcile([symbol], MarketType.CN, (day.date(), day.date()))
    second = service.reconcile([symbol], MarketType.CN, (day.date(), day.date()))

    assert first.run_id == "run-a"
    assert second.run_id == "run-b"

    rows = duckdb_conn.execute("SELECT run_id FROM reconciliation_runs ORDER BY created_at").fetchall()
    assert [value for (value,) in rows] == ["run-a", "run-b"]

    diff_count = duckdb_conn.execute("SELECT COUNT(*) FROM reconciliation_diffs").fetchone()
    assert diff_count == (2,)
