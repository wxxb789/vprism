"""Data models supporting the symbol normalization service."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from re import Pattern
from typing import TYPE_CHECKING, Literal

RuleTransform = Callable[[str, re.Match[str]], str]


if TYPE_CHECKING:
    from vprism.core.exceptions.base import UnresolvedSymbolError
    from vprism.core.models.market import AssetType, MarketType


@dataclass(frozen=True)
class CanonicalSymbol:
    """Represents a canonical symbol produced by the normalization service."""

    raw_symbol: str
    canonical: str
    market: MarketType
    asset_type: AssetType
    rule_id: str


@dataclass(frozen=True)
class SymbolRule:
    """Normalization rule evaluated by :class:`SymbolService`."""

    id: str
    priority: int
    pattern: Pattern[str]
    transform: RuleTransform
    market_scope: frozenset[MarketType] = frozenset()
    asset_scope: frozenset[AssetType] = frozenset()
    prefix: str | None = None
    suffix: str | None = None

    def applies_to(self, market: MarketType, asset_type: AssetType) -> bool:
        """Return whether the rule is applicable for the provided context."""

        market_allowed = not self.market_scope or market in self.market_scope
        asset_allowed = not self.asset_scope or asset_type in self.asset_scope
        return market_allowed and asset_allowed


@dataclass(frozen=True)
class BatchNormalizationItem:
    """Represents the outcome for a single symbol in a batch request."""

    raw_symbol: str
    status: Literal["resolved", "unresolved"]
    canonical: CanonicalSymbol | None = None
    error: UnresolvedSymbolError | None = None

    def __post_init__(self) -> None:
        if self.status == "resolved" and self.canonical is None:
            raise ValueError("Resolved batch items require a canonical symbol.")
        if self.status == "unresolved" and self.error is None:
            raise ValueError("Unresolved batch items require an associated error.")


@dataclass(frozen=True)
class BatchNormalizationResult:
    """Aggregated result payload for batch normalization operations."""

    market: MarketType
    asset_type: AssetType
    items: tuple[BatchNormalizationItem, ...]
    successes: tuple[CanonicalSymbol, ...]
    failures: tuple[UnresolvedSymbolError, ...]


__all__ = [
    "CanonicalSymbol",
    "SymbolRule",
    "RuleTransform",
    "BatchNormalizationItem",
    "BatchNormalizationResult",
]
