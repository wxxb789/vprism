from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal

import pytest

from vprism.core.exceptions.base import AdjustmentInputError
from vprism.core.models.base import DataPoint
from vprism.core.models.corporate_actions import (
    CorporateActionSet,
    DividendEvent,
    SplitEvent,
)
from vprism.core.models.market import MarketType
from vprism.core.models.query import Adjustment
from vprism.core.services.adjustment_engine import AdjustmentEngine


def _point(day: date, close: str) -> DataPoint:
    return DataPoint(
        symbol="000001",
        market=MarketType.CN,
        timestamp=datetime.combine(day, datetime.min.time()),
        close_price=Decimal(close),
        provider="test",
    )


def _loader(points: list[DataPoint]):
    def _inner(symbol: str, market: MarketType, start: date, end: date) -> list[DataPoint]:
        return list(points)

    return _inner


def _actions(dividends: list[DividendEvent], splits: list[SplitEvent]):
    action_set = CorporateActionSet(dividends=tuple(dividends), splits=tuple(splits))

    def _inner(symbol: str, market: MarketType, start: date, end: date) -> CorporateActionSet:
        return action_set

    return _inner


def test_compute_without_events_returns_identity() -> None:
    points = [_point(date(2024, 1, 1), "10"), _point(date(2024, 1, 2), "11"), _point(date(2024, 1, 3), "12")]
    engine = AdjustmentEngine(_loader(points), _actions([], []))

    result = engine.compute("000001", MarketType.CN, date(2024, 1, 1), date(2024, 1, 3), Adjustment.NONE)

    assert [row.close_qfq for row in result.rows] == [Decimal("10"), Decimal("11"), Decimal("12")]
    assert [row.close_hfq for row in result.rows] == [Decimal("10"), Decimal("11"), Decimal("12")]
    assert result.source_events_hash == hashlib.sha256(b"").hexdigest()
    assert result.version == f"1:{result.source_events_hash[:12]}"
    assert result.action_gap_flag is False


def test_compute_handles_dividend_and_split_sequence() -> None:
    points = [
        _point(date(2024, 1, 1), "100"),
        _point(date(2024, 1, 2), "98"),
        _point(date(2024, 1, 3), "49"),
    ]
    dividends = [
        DividendEvent(
            symbol="000001",
            market=MarketType.CN,
            ex_date=date(2024, 1, 2),
            pay_date=None,
            cash_amount=Decimal("2"),
        )
    ]
    splits = [
        SplitEvent(
            symbol="000001",
            market=MarketType.CN,
            ex_date=date(2024, 1, 3),
            numerator=2,
            denominator=1,
        )
    ]
    engine = AdjustmentEngine(_loader(points), _actions(dividends, splits))

    result = engine.compute("000001", MarketType.CN, date(2024, 1, 1), date(2024, 1, 3), Adjustment.FORWARD)

    factors = [row.adj_factor_hfq.quantize(Decimal("0.0001")) for row in result.rows]
    assert factors == [Decimal("1.0000"), Decimal("1.0204"), Decimal("2.0408")]

    q_factors = [row.adj_factor_qfq.quantize(Decimal("0.0001")) for row in result.rows]
    assert q_factors == [Decimal("0.4900"), Decimal("0.5000"), Decimal("1.0000")]

    close_hfq = [row.close_hfq.quantize(Decimal("0.0001")) for row in result.rows if row.close_hfq is not None]
    close_qfq = [row.close_qfq.quantize(Decimal("0.0001")) for row in result.rows if row.close_qfq is not None]

    assert close_hfq == [Decimal("100.0000"), Decimal("100.0000"), Decimal("100.0000")]
    assert close_qfq == [Decimal("49.0000"), Decimal("49.0000"), Decimal("49.0000")]
    assert result.action_gap_flag is False


def test_compute_raises_without_prices() -> None:
    engine = AdjustmentEngine(_loader([]), _actions([], []))

    with pytest.raises(AdjustmentInputError):
        engine.compute("000001", MarketType.CN, date(2024, 1, 1), date(2024, 1, 2), Adjustment.NONE)


def test_gap_flag_set_when_missing_previous_close() -> None:
    points = [_point(date(2024, 1, 2), "10")]
    dividends = [
        DividendEvent(
            symbol="000001",
            market=MarketType.CN,
            ex_date=date(2024, 1, 2),
            cash_amount=Decimal("1"),
        )
    ]
    engine = AdjustmentEngine(_loader(points), _actions(dividends, []))

    result = engine.compute("000001", MarketType.CN, date(2024, 1, 2), date(2024, 1, 2), Adjustment.NONE)

    assert result.action_gap_flag is True
    assert result.rows[0].adj_factor_hfq == Decimal("1")


def test_version_hash_stable_for_identical_inputs() -> None:
    points = [_point(date(2024, 1, 1), "10"), _point(date(2024, 1, 2), "11")]
    dividends = [
        DividendEvent(
            symbol="000001",
            market=MarketType.CN,
            ex_date=date(2024, 1, 2),
            cash_amount=Decimal("0.5"),
        )
    ]
    engine = AdjustmentEngine(_loader(points), _actions(dividends, []))

    first = engine.compute("000001", MarketType.CN, date(2024, 1, 1), date(2024, 1, 2), Adjustment.BACKWARD)
    second = engine.compute("000001", MarketType.CN, date(2024, 1, 1), date(2024, 1, 2), Adjustment.BACKWARD)

    assert first.source_events_hash == second.source_events_hash
    assert first.version == second.version
    assert first.mode == Adjustment.BACKWARD
