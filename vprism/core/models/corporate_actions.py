from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence  # noqa: TC003
from dataclasses import dataclass
from datetime import date  # noqa: TC003
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from vprism.core.models.market import MarketType  # noqa: TC001

if TYPE_CHECKING:
    from vprism.core.models.base import DataPoint
    from vprism.core.models.query import Adjustment


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


@dataclass(slots=True, frozen=True)
class CorporateActionSet:
    """Container for dividend and split events for a symbol."""

    dividends: Sequence[DividendEvent]
    splits: Sequence[SplitEvent]


@dataclass(slots=True, frozen=True)
class FactorComputation:
    """Result of computing corporate action adjustment factors."""

    factors: list[CorporateActionFactor]
    gap_dates: tuple[date, ...]


@dataclass(slots=True, frozen=True)
class AdjustmentRow:
    """Single-day adjustment output containing raw and adjusted prices."""

    date: date
    close_raw: Decimal | None
    close_qfq: Decimal | None
    close_hfq: Decimal | None
    adj_factor_qfq: Decimal
    adj_factor_hfq: Decimal


@dataclass(slots=True, frozen=True)
class AdjustmentResult:
    """Adjustment computation output along with factor metadata."""

    symbol: str
    market: MarketType
    mode: Adjustment
    rows: tuple[AdjustmentRow, ...]
    factors: tuple[CorporateActionFactor, ...]
    source_events_hash: str
    version: str
    action_gap_flag: bool


def _decimal_ratio(value: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return value / denominator


def compute_corporate_action_factors(
    symbol: str,
    market: MarketType,
    prices: Sequence[DataPoint],
    dividends: Sequence[DividendEvent],
    splits: Sequence[SplitEvent],
) -> FactorComputation:
    if not prices:
        return FactorComputation(factors=[], gap_dates=())

    sorted_points = sorted(prices, key=lambda point: point.timestamp)
    dividend_map: dict[date, list[DividendEvent]] = defaultdict(list)
    for event in dividends:
        dividend_map[event.ex_date].append(event)

    split_map: dict[date, list[SplitEvent]] = defaultdict(list)
    for event in splits:
        split_map[event.ex_date].append(event)

    hfq_factor = Decimal("1")
    hfq_series: list[Decimal] = []
    dates: list[date] = []
    gap_dates: set[date] = set()
    previous_close: Decimal | None = None

    for point in sorted_points:
        current_date = point.timestamp.date()
        for event in dividend_map.get(current_date, []):
            if previous_close is None:
                gap_dates.add(current_date)
                continue
            ratio_base = _decimal_ratio(event.cash_amount, previous_close)
            if ratio_base is None:
                gap_dates.add(current_date)
                continue
            adjustment = Decimal("1") - ratio_base
            if adjustment <= 0:
                gap_dates.add(current_date)
                continue
            hfq_factor = hfq_factor / adjustment

        for event in split_map.get(current_date, []):
            denominator = Decimal(event.denominator)
            ratio = _decimal_ratio(Decimal(event.numerator), denominator)
            if ratio is None or ratio <= 0:
                gap_dates.add(current_date)
                continue
            hfq_factor = hfq_factor * ratio

        hfq_series.append(hfq_factor)
        dates.append(current_date)
        if point.close_price is not None:
            previous_close = point.close_price

    event_dates = {event.ex_date for event in dividends} | {event.ex_date for event in splits}
    missing_dates = event_dates.difference(dates)
    gap_dates.update(missing_dates)

    if not hfq_series:
        return FactorComputation(factors=[], gap_dates=tuple(sorted(gap_dates)))

    latest_hfq = hfq_series[-1]
    if latest_hfq == 0:
        # Avoid division by zero when normalizing for qfq factors.
        latest_hfq = Decimal("1")

    factors: list[CorporateActionFactor] = []
    for current_date, hfq_value in zip(dates, hfq_series, strict=False):
        qfq_factor = hfq_value / latest_hfq if latest_hfq != 0 else Decimal("0")
        factors.append(
            CorporateActionFactor(
                symbol=symbol,
                market=market,
                date=current_date,
                forward_factor=qfq_factor,
                backward_factor=hfq_value,
            )
        )

    return FactorComputation(factors=factors, gap_dates=tuple(sorted(gap_dates)))


__all__ = [
    "DividendEvent",
    "SplitEvent",
    "CorporateActionFactor",
    "CorporateActionSet",
    "FactorComputation",
    "AdjustmentRow",
    "AdjustmentResult",
    "compute_corporate_action_factors",
]
