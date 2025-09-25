from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from vprism.core.models.base import DataPoint
from vprism.core.models.corporate_actions import (
    CorporateActionSet,
    DividendEvent,
    SplitEvent,
    merge_corporate_action_set,
)
from vprism.core.models.market import MarketType
from vprism.core.models.query import Adjustment
from vprism.core.services import adjustment_engine as adjustment_engine_module
from vprism.core.services.adjustment_engine import AdjustmentEngine

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def _make_point(day: int, close_price: str) -> DataPoint:
    return DataPoint(
        symbol="000001",
        market=MarketType.CN,
        timestamp=datetime(2024, 1, day, 0, 0, 0),
        close_price=Decimal(close_price),
    )


def test_merge_same_day_events() -> None:
    """Same-day dividends and splits collapse into single merged events."""

    dividends = (
        DividendEvent(
            symbol="000001",
            market=MarketType.CN,
            ex_date=date(2024, 1, 2),
            pay_date=date(2024, 1, 10),
            cash_amount=Decimal("1.5"),
            currency="CNY",
            source="alpha",
            metadata={"note": "first"},
        ),
        DividendEvent(
            symbol="000001",
            market=MarketType.CN,
            ex_date=date(2024, 1, 2),
            pay_date=date(2024, 1, 12),
            cash_amount=Decimal("1.0"),
            currency="CNY",
            source="beta",
            metadata={"second": True},
        ),
    )
    splits = (
        SplitEvent(
            symbol="000001",
            market=MarketType.CN,
            ex_date=date(2024, 1, 3),
            numerator=2,
            denominator=1,
            source="alpha",
        ),
        SplitEvent(
            symbol="000001",
            market=MarketType.CN,
            ex_date=date(2024, 1, 3),
            numerator=3,
            denominator=2,
            source="beta",
        ),
    )

    merged = merge_corporate_action_set(CorporateActionSet(dividends=dividends, splits=splits))

    assert len(merged.dividends) == 1
    dividend = merged.dividends[0]
    assert dividend.cash_amount == Decimal("2.5")
    assert dividend.pay_date == date(2024, 1, 10)
    assert dividend.source == "alpha,beta"
    assert dividend.metadata["merged_event_count"] == 2
    assert dividend.metadata["note"] == "first"
    assert dividend.metadata["second"] is True

    assert len(merged.splits) == 1
    split = merged.splits[0]
    assert split.numerator == 6
    assert split.denominator == 2
    assert split.source == "alpha,beta"
    assert split.metadata["merged_event_count"] == 2


def test_adjustment_engine_merges_events_in_compute() -> None:
    """Merged events influence factor computation deterministically."""

    prices = (
        _make_point(1, "100"),
        _make_point(2, "98"),
        _make_point(3, "49"),
    )
    dividends = (
        DividendEvent(
            symbol="000001",
            market=MarketType.CN,
            ex_date=date(2024, 1, 2),
            cash_amount=Decimal("1"),
            currency="CNY",
        ),
        DividendEvent(
            symbol="000001",
            market=MarketType.CN,
            ex_date=date(2024, 1, 2),
            cash_amount=Decimal("2"),
            currency="CNY",
        ),
    )
    splits = (
        SplitEvent(
            symbol="000001",
            market=MarketType.CN,
            ex_date=date(2024, 1, 3),
            numerator=2,
            denominator=1,
        ),
        SplitEvent(
            symbol="000001",
            market=MarketType.CN,
            ex_date=date(2024, 1, 3),
            numerator=3,
            denominator=2,
        ),
    )

    engine = AdjustmentEngine(
        price_loader=lambda *_: prices,
        action_loader=lambda *_: CorporateActionSet(dividends=dividends, splits=splits),
    )

    result = engine.compute(
        symbol="000001",
        market=MarketType.CN,
        start=date(2024, 1, 1),
        end=date(2024, 1, 3),
        mode=Adjustment.FORWARD,
    )

    day_two = next(row for row in result.rows if row.date == date(2024, 1, 2))
    expected_dividend_adjustment = Decimal("1") / (Decimal("1") - Decimal("3") / Decimal("100"))
    assert day_two.adj_factor_hfq.quantize(Decimal("0.0000001")) == expected_dividend_adjustment.quantize(
        Decimal("0.0000001")
    )

    day_three = next(row for row in result.rows if row.date == date(2024, 1, 3))
    expected_split_factor = expected_dividend_adjustment * Decimal(2) * (Decimal(3) / Decimal(2))
    assert day_three.adj_factor_hfq.quantize(Decimal("0.0000001")) == expected_split_factor.quantize(
        Decimal("0.0000001")
    )


def test_factor_memoization_reuses_cached_result(monkeypatch: MonkeyPatch) -> None:
    """Repeated computations with identical inputs reuse cached factors."""

    prices = (
        _make_point(1, "100"),
        _make_point(2, "101"),
    )
    action_set = CorporateActionSet(dividends=(), splits=())

    engine = AdjustmentEngine(
        price_loader=lambda *_: prices,
        action_loader=lambda *_: action_set,
    )

    call_count = 0
    original = adjustment_engine_module.compute_corporate_action_factors

    def spy_compute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(adjustment_engine_module, "compute_corporate_action_factors", spy_compute)

    engine.compute(
        symbol="000001",
        market=MarketType.CN,
        start=date(2024, 1, 1),
        end=date(2024, 1, 2),
        mode=Adjustment.FORWARD,
    )
    engine.compute(
        symbol="000001",
        market=MarketType.CN,
        start=date(2024, 1, 1),
        end=date(2024, 1, 2),
        mode=Adjustment.FORWARD,
    )

    assert call_count == 1
