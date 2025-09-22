"""Adjustment engine for computing forward/backward adjusted price series."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal

from vprism.core.exceptions.base import AdjustmentInputError
from vprism.core.models.base import DataPoint
from vprism.core.models.corporate_actions import (
    AdjustmentResult,
    AdjustmentRow,
    CorporateActionFactor,
    CorporateActionSet,
    FactorComputation,
    compute_corporate_action_factors,
    merge_corporate_action_set,
)
from vprism.core.models.market import MarketType
from vprism.core.models.query import Adjustment

PriceLoader = Callable[[str, MarketType, date, date], Sequence[DataPoint]]
CorporateActionLoader = Callable[[str, MarketType, date, date], CorporateActionSet]


def _format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _hash_events(action_set: CorporateActionSet) -> str:
    parts: list[str] = []
    for event in sorted(
        action_set.dividends,
        key=lambda item: (item.ex_date, _format_decimal(item.cash_amount), item.currency or "", item.source or ""),
    ):
        parts.append(
            "|".join(
                (
                    "dividend",
                    event.ex_date.isoformat(),
                    _format_decimal(event.cash_amount),
                    event.currency or "",
                    event.source or "",
                )
            )
        )
    for event in sorted(
        action_set.splits,
        key=lambda item: (item.ex_date, item.numerator, item.denominator, item.source or ""),
    ):
        parts.append(
            "|".join(
                (
                    "split",
                    event.ex_date.isoformat(),
                    str(event.numerator),
                    str(event.denominator),
                    event.source or "",
                )
            )
        )
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class AdjustmentEngine:
    """Compute adjustment factors and adjusted prices for a symbol."""

    def __init__(
        self,
        price_loader: PriceLoader,
        action_loader: CorporateActionLoader,
        algorithm_version: int = 1,
    ) -> None:
        self._price_loader = price_loader
        self._action_loader = action_loader
        self._algorithm_version = algorithm_version
        self._factor_cache: dict[str, FactorComputation] = {}

    def _fingerprint_prices(self, prices: Sequence[DataPoint]) -> str:
        hasher = hashlib.sha256()
        for point in prices:
            hasher.update(point.timestamp.isoformat().encode("utf-8"))
            close_text = (
                _format_decimal(point.close_price) if point.close_price is not None else "None"
            )
            hasher.update(close_text.encode("utf-8"))
        return hasher.hexdigest()

    def _cache_key(
        self,
        symbol: str,
        market: MarketType,
        start: date,
        end: date,
        mode: Adjustment,
        price_fingerprint: str,
        events_hash: str,
        price_count: int,
    ) -> str:
        return "|".join(
            (
                symbol,
                market.value,
                start.isoformat(),
                end.isoformat(),
                mode.value,
                str(self._algorithm_version),
                str(price_count),
                price_fingerprint,
                events_hash,
            )
        )

    def compute(
        self,
        symbol: str,
        market: MarketType,
        start: date,
        end: date,
        mode: Adjustment = Adjustment.NONE,
    ) -> AdjustmentResult:
        prices = list(self._price_loader(symbol, market, start, end))
        if not prices:
            raise AdjustmentInputError(
                "No price data available for adjustment computation.",
                symbol=symbol,
                market=market.value,
            )

        prices.sort(key=lambda point: point.timestamp)
        action_set = merge_corporate_action_set(
            self._action_loader(symbol, market, start, end)
        )

        price_fingerprint = self._fingerprint_prices(prices)
        events_hash = _hash_events(action_set)
        cache_key = self._cache_key(
            symbol,
            market,
            start,
            end,
            mode,
            price_fingerprint,
            events_hash,
            len(prices),
        )

        cached = self._factor_cache.get(cache_key)
        if cached is None:
            computed = compute_corporate_action_factors(
                symbol,
                market,
                prices,
                action_set.dividends,
                action_set.splits,
            )
            factor_result = FactorComputation(
                factors=list(computed.factors),
                gap_dates=computed.gap_dates,
            )
            self._factor_cache[cache_key] = FactorComputation(
                factors=list(factor_result.factors),
                gap_dates=factor_result.gap_dates,
            )
        else:
            factor_result = FactorComputation(
                factors=list(cached.factors),
                gap_dates=cached.gap_dates,
            )
        factor_map: dict[date, CorporateActionFactor] = {
            factor.date: factor for factor in factor_result.factors
        }

        rows: list[AdjustmentRow] = []
        for point in prices:
            price_date = point.timestamp.date()
            factor = factor_map.get(price_date)
            adj_qfq = factor.forward_factor if factor else Decimal("1")
            adj_hfq = factor.backward_factor if factor else Decimal("1")
            close_raw = point.close_price
            close_qfq = close_raw * adj_qfq if close_raw is not None else None
            close_hfq = close_raw * adj_hfq if close_raw is not None else None
            rows.append(
                AdjustmentRow(
                    date=price_date,
                    close_raw=close_raw,
                    close_qfq=close_qfq,
                    close_hfq=close_hfq,
                    adj_factor_qfq=adj_qfq,
                    adj_factor_hfq=adj_hfq,
                )
            )

        version = f"{self._algorithm_version}:{events_hash[:12]}"

        return AdjustmentResult(
            symbol=symbol,
            market=market,
            mode=mode,
            rows=tuple(rows),
            factors=tuple(factor_result.factors),
            source_events_hash=events_hash,
            version=version,
            action_gap_flag=bool(factor_result.gap_dates),
        )


__all__ = ["AdjustmentEngine"]
