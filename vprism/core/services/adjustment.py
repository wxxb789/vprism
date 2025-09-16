from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from vprism.core.models.corporate_actions import CorporateActionFactor  # noqa: TCH001
from vprism.core.models.query import Adjustment

if TYPE_CHECKING:
    from collections.abc import Iterable
    from vprism.core.models.base import DataPoint  # noqa: TCH001


@dataclass(slots=True)
class AdjustmentContext:
    mode: Adjustment
    factors: dict[str, CorporateActionFactor] | None = None


class PriceAdjuster:
    def apply(self, points: Iterable[DataPoint], context: AdjustmentContext) -> list[DataPoint]:
        if context.mode == Adjustment.NONE:
            return list(points)
        out: list[DataPoint] = []
        factors = context.factors or {}
        for p in points:
            key = p.timestamp.date().isoformat()
            f = factors.get(key)
            if not f:
                out.append(p)
                continue
            factor = f.forward_factor if context.mode == Adjustment.FORWARD else f.backward_factor
            if p.close_price is not None:
                p = p.model_copy(update={"close_price": p.close_price * factor})
            if p.open_price is not None:
                p = p.model_copy(update={"open_price": p.open_price * factor})
            if p.high_price is not None:
                p = p.model_copy(update={"high_price": p.high_price * factor})
            if p.low_price is not None:
                p = p.model_copy(update={"low_price": p.low_price * factor})
            if p.volume is not None and factor != 0:
                p = p.model_copy(update={"volume": p.volume / factor})
            out.append(p)
        return out


def adjust_prices(points: list[DataPoint], mode: Adjustment | None, factors: list[CorporateActionFactor] | None = None) -> list[DataPoint]:
    if mode is None or mode == Adjustment.NONE:
        return points
    factor_map: dict[str, CorporateActionFactor] | None = None
    if factors:
        factor_map = {f.date.isoformat(): f for f in factors}
    adjuster = PriceAdjuster()
    return adjuster.apply(points, AdjustmentContext(mode=mode, factors=factor_map))
