from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from random import Random
from typing import Sequence

import pytest

from vprism.core.exceptions.base import ReconciliationError
from vprism.core.models.base import DataPoint
from vprism.core.models.market import MarketType
from vprism.core.services.reconciliation import (
    PriceSeriesLoader,
    ReconciliationService,
    ReconciliationStatus,
)


def _make_point(
    symbol: str,
    day: date,
    close: str,
    volume: str,
    provider: str,
    market: MarketType = MarketType.CN,
) -> DataPoint:
    return DataPoint(
        symbol=symbol,
        market=market,
        timestamp=datetime.combine(day, time.min),
        close_price=Decimal(close),
        volume=Decimal(volume),
        provider=provider,
    )


def _loader_factory(data: dict[str, Sequence[DataPoint]]) -> PriceSeriesLoader:
    def _loader(symbol: str, market: MarketType, start: date, end: date) -> Sequence[DataPoint]:
        return data.get(symbol, [])

    return _loader


def test_reconcile_all_pass() -> None:
    symbol = "AAA"
    start = date(2024, 1, 1)
    end = date(2024, 1, 3)
    provider_a_data = {
        symbol: [
            _make_point(symbol, start, "100", "1000", "A"),
            _make_point(symbol, date(2024, 1, 2), "101", "1100", "A"),
            _make_point(symbol, end, "102", "900", "A"),
        ]
    }
    provider_b_data = {
        symbol: [
            _make_point(symbol, start, "100", "1000", "B"),
            _make_point(symbol, date(2024, 1, 2), "101", "1100", "B"),
            _make_point(symbol, end, "102", "900", "B"),
        ]
    }

    service = ReconciliationService(
        _loader_factory(provider_a_data),
        _loader_factory(provider_b_data),
        source_a="akshare",
        source_b="yfinance",
        default_sample_size=5,
        rng=Random(0),
    )

    result = service.reconcile([symbol], MarketType.CN, (start, end))

    assert result.run_id
    assert result.summary.pass_count == 3
    assert result.summary.warn_count == 0
    assert result.summary.fail_count == 0
    assert result.summary.p95_close_bp_diff == Decimal("0")
    assert result.sampled_symbols == (symbol,)
    assert all(sample.status is ReconciliationStatus.PASS for sample in result.samples)


def test_reconcile_warn_and_fail_classification() -> None:
    symbol = "BBB"
    start = date(2024, 1, 1)
    provider_a_data = {
        symbol: [
            _make_point(symbol, start, "100", "1000", "A"),
            _make_point(symbol, date(2024, 1, 2), "100.06", "1000", "A"),
            _make_point(symbol, date(2024, 1, 3), "100.12", "1800", "A"),
        ]
    }
    provider_b_data = {
        symbol: [
            _make_point(symbol, start, "100", "1000", "B"),
            _make_point(symbol, date(2024, 1, 2), "100", "1000", "B"),
            _make_point(symbol, date(2024, 1, 3), "100", "900", "B"),
        ]
    }

    service = ReconciliationService(
        _loader_factory(provider_a_data),
        _loader_factory(provider_b_data),
        source_a="akshare",
        source_b="yfinance",
        rng=Random(0),
    )

    result = service.reconcile([symbol], MarketType.CN, (start, date(2024, 1, 3)))

    statuses = [sample.status for sample in result.samples]
    assert result.run_id
    assert statuses.count(ReconciliationStatus.PASS) == 1
    assert statuses.count(ReconciliationStatus.WARN) == 1
    assert statuses.count(ReconciliationStatus.FAIL) == 1
    assert result.summary.pass_count == 1
    assert result.summary.warn_count == 1
    assert result.summary.fail_count == 1
    assert result.summary.p95_close_bp_diff == Decimal("11.4")


def test_reconcile_missing_provider_data_marks_fail() -> None:
    symbol = "CCC"
    start = date(2024, 1, 1)
    end = date(2024, 1, 2)
    provider_a_data = {
        symbol: [
            _make_point(symbol, start, "100", "1000", "A"),
            _make_point(symbol, end, "101", "1000", "A"),
        ]
    }
    provider_b_data: dict[str, Sequence[DataPoint]] = {symbol: []}

    service = ReconciliationService(
        _loader_factory(provider_a_data),
        _loader_factory(provider_b_data),
        source_a="akshare",
        source_b="yfinance",
    )

    result = service.reconcile([symbol], MarketType.CN, (start, end))

    assert all(sample.status is ReconciliationStatus.FAIL for sample in result.samples)
    assert result.summary.fail_count == 2
    assert result.run_id


def test_reconcile_validates_inputs() -> None:
    service = ReconciliationService(
        _loader_factory({}),
        _loader_factory({}),
        source_a="akshare",
        source_b="yfinance",
    )

    with pytest.raises(ReconciliationError):
        service.reconcile([], MarketType.CN, (date(2024, 1, 1), date(2024, 1, 2)))

    with pytest.raises(ReconciliationError):
        service.reconcile(["AAA"], MarketType.CN, (date(2024, 1, 2), date(2024, 1, 1)))

    with pytest.raises(ReconciliationError):
        service.reconcile(["AAA"], MarketType.CN, (date(2024, 1, 1), date(2024, 1, 2)), sample_size=0)
