from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from vprism.core.models.base import DataPoint
from vprism.core.models.corporate_actions import CorporateActionFactor
from vprism.core.models.market import MarketType
from vprism.core.models.query import Adjustment
from vprism.core.services.adjustment import adjust_prices


def _dp(d: date, o: float, h: float, low: float, c: float, v: int) -> DataPoint:
    return DataPoint(
        symbol="000001",
        market=MarketType.CN,
        timestamp=datetime(d.year, d.month, d.day),
        open_price=Decimal(str(o)),
        high_price=Decimal(str(h)),
        low_price=Decimal(str(low)),
        close_price=Decimal(str(c)),
        volume=Decimal(str(v)),
        provider="test",
    )


def test_adjust_prices_forward_with_factors():
    factors = [
        CorporateActionFactor(symbol="000001", market=MarketType.CN, date=date(2024, 1, 1), forward_factor=Decimal("1"), backward_factor=Decimal("1")),
        CorporateActionFactor(symbol="000001", market=MarketType.CN, date=date(2024, 1, 2), forward_factor=Decimal("2"), backward_factor=Decimal("0.5")),
    ]
    pts = [_dp(date(2024, 1, 1), 10, 11, 9, 10, 1000), _dp(date(2024, 1, 2), 12, 13, 11, 12, 1500)]
    out = adjust_prices(pts, Adjustment.FORWARD, factors)
    assert out[0].close_price == Decimal("10") and out[0].volume == Decimal("1000")
    assert out[1].close_price == Decimal("24") and out[1].volume == Decimal("750")


def test_adjust_prices_backward_with_factors():
    factors = [
        CorporateActionFactor(symbol="000001", market=MarketType.CN, date=date(2024, 1, 1), forward_factor=Decimal("1"), backward_factor=Decimal("1")),
        CorporateActionFactor(symbol="000001", market=MarketType.CN, date=date(2024, 1, 2), forward_factor=Decimal("2"), backward_factor=Decimal("0.5")),
    ]
    pts = [_dp(date(2024, 1, 1), 10, 11, 9, 10, 1000), _dp(date(2024, 1, 2), 12, 13, 11, 12, 1500)]
    out = adjust_prices(pts, Adjustment.BACKWARD, factors)
    assert out[0].close_price == Decimal("10") and out[0].volume == Decimal("1000")
    assert out[1].close_price == Decimal("6") and out[1].volume == Decimal("3000")


def test_adjust_prices_missing_factor_date_no_change():
    factors = [
        CorporateActionFactor(
            symbol="000001", market=MarketType.CN, date=date(2024, 1, 1), forward_factor=Decimal("1.5"), backward_factor=Decimal("0.6666666667")
        ),
    ]
    pts = [_dp(date(2024, 1, 2), 10, 11, 9, 10, 1000)]
    out = adjust_prices(pts, Adjustment.FORWARD, factors)
    assert out[0].close_price == Decimal("10") and out[0].volume == Decimal("1000")
