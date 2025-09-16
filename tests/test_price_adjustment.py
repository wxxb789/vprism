from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from vprism.core.models.base import DataPoint
from vprism.core.models.market import MarketType
from vprism.core.models.query import Adjustment
from vprism.core.services.adjustment import adjust_prices


def _dp(close: float) -> DataPoint:
    return DataPoint(
        symbol="000001",
        market=MarketType.CN,
        timestamp=datetime(2024,1,1),
        close_price=Decimal(str(close)),
        provider="test",
    )


def test_adjust_prices_none_passthrough():
    points = [_dp(10.0), _dp(11.0)]
    out = adjust_prices(points, Adjustment.NONE)
    assert out == points


def test_adjust_prices_none_mode_is_none():
    points = [_dp(10.0)]
    out = adjust_prices(points, None)
    assert out == points


def test_adjust_prices_forward_passthrough_current_placeholder():
    points = [_dp(10.0), _dp(9.5)]
    out = adjust_prices(points, Adjustment.FORWARD)
    assert [p.close_price for p in out] == [Decimal('10.0'), Decimal('9.5')]


def test_adjust_prices_backward_passthrough_current_placeholder():
    points = [_dp(8.0), _dp(7.5)]
    out = adjust_prices(points, Adjustment.BACKWARD)
    assert [p.close_price for p in out] == [Decimal('8.0'), Decimal('7.5')]
