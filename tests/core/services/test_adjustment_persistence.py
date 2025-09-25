import duckdb
import pytest

from datetime import UTC, date, datetime
from decimal import Decimal

from vprism.core.data.schema import ADJUSTMENTS_TABLE
from vprism.core.models.base import DataPoint
from vprism.core.models.corporate_actions import CorporateActionSet
from vprism.core.models.market import MarketType
from vprism.core.models.query import Adjustment
from vprism.core.services.adjustment_engine import (
    AdjustmentEngine,
    VPrismDuckDBAdjustmentWriter,
)


def _point(day: date, close: str) -> DataPoint:
    return DataPoint(
        symbol="000001",
        market=MarketType.CN,
        timestamp=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
        close_price=Decimal(close),
        provider="test",
    )


def _loader(points: list[DataPoint]):
    def _inner(symbol: str, market: MarketType, start: date, end: date) -> list[DataPoint]:
        return list(points)

    return _inner


def _actions() -> CorporateActionSet:
    return CorporateActionSet(dividends=(), splits=())


@pytest.fixture()
def duckdb_connection() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(database=":memory:")
    ADJUSTMENTS_TABLE.ensure(connection)
    return connection


def _fixed_clock() -> datetime:
    return datetime(2024, 2, 1, 12, tzinfo=UTC)


def test_adjustment_engine_persists_rows(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    points = [
        _point(date(2024, 1, 1), "10"),
        _point(date(2024, 1, 2), "10"),
    ]
    engine = AdjustmentEngine(
        _loader(points),
        lambda symbol, market, start, end: _actions(),
        factor_writer=VPrismDuckDBAdjustmentWriter(duckdb_connection),
        clock=_fixed_clock,
    )

    result = engine.compute("000001", MarketType.CN, date(2024, 1, 1), date(2024, 1, 2), Adjustment.FORWARD)

    stored = duckdb_connection.execute(
        """
        SELECT market, supplier_symbol, date, adj_factor_qfq, adj_factor_hfq, version, build_time, source_events_hash
        FROM adjustments
        ORDER BY date
        """
    ).fetchall()

    assert len(stored) == len(result.rows)
    assert {row.date for row in result.rows} == {entry[2] for entry in stored}
    for entry in stored:
        assert entry[0] == "cn"
        assert entry[1] == "000001"
        assert entry[5] == result.version
        assert entry[7] == result.source_events_hash

    stored_time = stored[0][6]
    if stored_time.tzinfo is None:
        stored_time = stored_time.replace(tzinfo=UTC)
    assert stored_time == _fixed_clock()


def test_adjustment_engine_replaces_existing_rows(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    points = [
        _point(date(2024, 1, 1), "10"),
    ]
    engine = AdjustmentEngine(
        _loader(points),
        lambda symbol, market, start, end: _actions(),
        factor_writer=VPrismDuckDBAdjustmentWriter(duckdb_connection),
        clock=_fixed_clock,
    )

    engine.compute("000001", MarketType.CN, date(2024, 1, 1), date(2024, 1, 1), Adjustment.NONE)
    engine.compute("000001", MarketType.CN, date(2024, 1, 1), date(2024, 1, 1), Adjustment.NONE)

    stored = duckdb_connection.execute("SELECT COUNT(*) FROM adjustments").fetchone()[0]
    assert stored == 1
