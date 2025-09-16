from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from vprism.core.models.market import MarketType


@dataclass(slots=True)
class NormalizedSymbol:
    raw: str
    c_symbol: str
    market: MarketType
    confidence: float
    rule: str
    unresolved: bool = False


class SymbolNormalizer:
    def __init__(self, add_market_suffix: bool = False):
        self.add_market_suffix = add_market_suffix

    async def normalize(
        self,
        symbols: list[str],
        market: MarketType | None = None,
        provider: str | None = None,
        upstream: str | None = None,
    ) -> list[NormalizedSymbol]:
        results: list[NormalizedSymbol] = []
        for s in symbols:
            ns = self._normalize_single(s, market, provider, upstream)
            results.append(ns)
        return results

    def _normalize_single(self, symbol: str, market: MarketType | None, provider: str | None, upstream: str | None) -> NormalizedSymbol:
        # Rule 1: already canonical placeholder (contains ':' marker) - none currently used
        # Rule 2: six digit CN code
        if market in {MarketType.CN, None} and symbol.isdigit() and len(symbol) == 6:
            # conservative: keep raw as canonical (phase 1)
            return NormalizedSymbol(
                raw=symbol,
                c_symbol=symbol if not self.add_market_suffix else f"{symbol}.CN",
                market=market or MarketType.CN,
                confidence=0.9,
                rule="cn_six_digit",
            )
        # Rule 3: US style assumed if alphabetic and length<=5
        if symbol.isalpha() and 1 <= len(symbol) <= 5:
            return NormalizedSymbol(raw=symbol, c_symbol=symbol.upper(), market=market or MarketType.US, confidence=0.8, rule="us_symbol")
        # Fallback unresolved
        return NormalizedSymbol(raw=symbol, c_symbol=symbol, market=market or MarketType.CN, confidence=0.1, rule="fallback", unresolved=True)


@lru_cache(maxsize=1)
def get_symbol_normalizer() -> SymbolNormalizer:
    return SymbolNormalizer(add_market_suffix=False)
