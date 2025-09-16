from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from vprism.core.models.market import MarketType


class DividendEvent(BaseModel):
    symbol: str
    market: MarketType
    ex_date: date
    pay_date: date | None = None
    cash_amount: Decimal = Field(gt=Decimal("0"))
    currency: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SplitEvent(BaseModel):
    symbol: str
    market: MarketType
    ex_date: date
    numerator: int = Field(gt=0)
    denominator: int = Field(gt=0)
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def ratio(self) -> Decimal:
        return Decimal(self.numerator) / Decimal(self.denominator)


class CorporateActionFactor(BaseModel):
    symbol: str
    market: MarketType
    date: date
    forward_factor: Decimal
    backward_factor: Decimal
    source: str | None = None


def compute_corporate_action_factors(
    symbol: str,
    market: MarketType,
    price_dates: list[date],
    dividends: list[DividendEvent],
    splits: list[SplitEvent],
) -> list[CorporateActionFactor]:
    factors: list[CorporateActionFactor] = []
    for d in price_dates:
        factors.append(
            CorporateActionFactor(
                symbol=symbol,
                market=market,
                date=d,
                forward_factor=Decimal("1"),
                backward_factor=Decimal("1"),
                source="placeholder",
            )
        )
    return factors


__all__ = [
    "DividendEvent",
    "SplitEvent",
    "CorporateActionFactor",
    "compute_corporate_action_factors",
]
