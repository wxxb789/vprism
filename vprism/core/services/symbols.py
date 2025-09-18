"""Core symbol normalization service with in-memory caching, diagnostics, and persistence."""

from __future__ import annotations

import re
from collections import OrderedDict, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from functools import lru_cache
from typing import TYPE_CHECKING

from vprism.core.data.schema import SYMBOL_MAP_TABLE
from vprism.core.exceptions.base import UnresolvedSymbolError
from vprism.core.models.market import AssetType, MarketType
from vprism.core.models.symbols import (
    BatchNormalizationItem,
    BatchNormalizationResult,
    CanonicalSymbol,
    RuleTransform,
    SymbolRule,
)

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

CacheKey = tuple[str, MarketType, AssetType]


_CN_SUFFIX_EXCHANGE_MAP: Mapping[str, str] = {"SS": "SH", "SH": "SH", "SZ": "SZ"}
_CN_PREFIX_EXCHANGE_MAP: Mapping[str, str] = {"SH": "SH", "SZ": "SZ"}
_FUND_SUFFIX_EXCHANGE_MAP: Mapping[str, str] = {
    "OF": "OF",
    "SZ": "SZ",
    "SH": "SH",
}
_FUND_PREFIX_EXCHANGE_MAP: Mapping[str, str] = {
    "OF": "OF",
    "SZ": "SZ",
    "SH": "SH",
}


def _exchange_from_mapping(token: str, mapping: Mapping[str, str]) -> str:
    normalized = token.upper()
    return mapping.get(normalized, normalized)


def _suffix_rule(mapping: Mapping[str, str]) -> RuleTransform:
    def _transform(raw: str, match: re.Match[str]) -> str:
        code = match.group("code")
        suffix = match.group("suffix")
        exchange = _exchange_from_mapping(suffix, mapping)
        return f"{exchange}{code}"

    return _transform


def _prefix_rule(mapping: Mapping[str, str]) -> RuleTransform:
    def _transform(raw: str, match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        code = match.group("code")
        exchange = _exchange_from_mapping(prefix, mapping)
        return f"{exchange}{code}"

    return _transform


def _numeric_rule() -> RuleTransform:
    def _transform(raw: str, match: re.Match[str]) -> str:
        return match.group("code")

    return _transform


def _uppercase_token_rule() -> RuleTransform:
    def _transform(raw: str, match: re.Match[str]) -> str:
        return match.group("token").upper()

    return _transform


def _build_cn_stock_rules() -> list[SymbolRule]:
    return [
        SymbolRule(
            id="cn_stock_yfinance",
            priority=10,
            pattern=re.compile(r"^(?P<code>\d{6})\.(?P<suffix>SS|SH|SZ)$", re.IGNORECASE),
            transform=_suffix_rule(_CN_SUFFIX_EXCHANGE_MAP),
            market_scope=frozenset({MarketType.CN}),
            asset_scope=frozenset({AssetType.STOCK}),
        ),
        SymbolRule(
            id="cn_stock_akshare",
            priority=15,
            pattern=re.compile(r"^(?P<prefix>sh|sz)(?P<code>\d{6})$", re.IGNORECASE),
            transform=_prefix_rule(_CN_PREFIX_EXCHANGE_MAP),
            market_scope=frozenset({MarketType.CN}),
            asset_scope=frozenset({AssetType.STOCK}),
        ),
        SymbolRule(
            id="cn_stock_numeric",
            priority=20,
            pattern=re.compile(r"^(?P<code>\d{6})$"),
            transform=_numeric_rule(),
            market_scope=frozenset({MarketType.CN}),
            asset_scope=frozenset({AssetType.STOCK}),
        ),
    ]


def _build_cn_fund_rules() -> list[SymbolRule]:
    return [
        SymbolRule(
            id="cn_fund_yfinance",
            priority=30,
            pattern=re.compile(r"^(?P<code>\d{6})\.(?P<suffix>OF|SZ|SH)$", re.IGNORECASE),
            transform=_suffix_rule(_FUND_SUFFIX_EXCHANGE_MAP),
            market_scope=frozenset({MarketType.CN}),
            asset_scope=frozenset({AssetType.FUND}),
        ),
        SymbolRule(
            id="cn_fund_akshare",
            priority=35,
            pattern=re.compile(r"^(?P<prefix>of|sz|sh)(?P<code>\d{6})$", re.IGNORECASE),
            transform=_prefix_rule(_FUND_PREFIX_EXCHANGE_MAP),
            market_scope=frozenset({MarketType.CN}),
            asset_scope=frozenset({AssetType.FUND}),
        ),
        SymbolRule(
            id="cn_fund_numeric",
            priority=40,
            pattern=re.compile(r"^(?P<code>\d{6})$"),
            transform=_numeric_rule(),
            market_scope=frozenset({MarketType.CN}),
            asset_scope=frozenset({AssetType.FUND}),
        ),
    ]


def _build_cn_index_rules() -> list[SymbolRule]:
    return [
        SymbolRule(
            id="cn_index_yfinance",
            priority=50,
            pattern=re.compile(r"^(?P<code>\d{6})\.(?P<suffix>SH|SZ)$", re.IGNORECASE),
            transform=_suffix_rule(_CN_SUFFIX_EXCHANGE_MAP),
            market_scope=frozenset({MarketType.CN}),
            asset_scope=frozenset({AssetType.INDEX}),
        ),
        SymbolRule(
            id="cn_index_akshare",
            priority=55,
            pattern=re.compile(r"^(?P<prefix>sh|sz)(?P<code>\d{6})$", re.IGNORECASE),
            transform=_prefix_rule(_CN_PREFIX_EXCHANGE_MAP),
            market_scope=frozenset({MarketType.CN}),
            asset_scope=frozenset({AssetType.INDEX}),
        ),
        SymbolRule(
            id="cn_index_numeric",
            priority=60,
            pattern=re.compile(r"^(?P<code>\d{6})$"),
            transform=_numeric_rule(),
            market_scope=frozenset({MarketType.CN}),
            asset_scope=frozenset({AssetType.INDEX}),
        ),
    ]


@lru_cache(maxsize=1)
def default_rules() -> tuple[SymbolRule, ...]:
    rules: list[SymbolRule] = []
    rules.extend(_build_cn_stock_rules())
    rules.extend(_build_cn_fund_rules())
    rules.extend(_build_cn_index_rules())
    rules.append(
        SymbolRule(
            id="generic_uppercase",
            priority=1000,
            pattern=re.compile(r"^(?P<token>[A-Z]{1,10})$", re.IGNORECASE),
            transform=_uppercase_token_rule(),
        )
    )
    return tuple(sorted(rules, key=lambda rule: (rule.priority, rule.id)))


class SymbolService:
    """Provides canonical symbol normalization using priority-ordered rules."""

    def __init__(
        self,
        rules: Sequence[SymbolRule] | None = None,
        cache_size: int = 10_000,
        persistence_conn: DuckDBPyConnection | None = None,
    ) -> None:
        self._cache_size = max(cache_size, 0)
        resolved_rules = rules if rules is not None else default_rules()
        self._rules: tuple[SymbolRule, ...] = tuple(sorted(resolved_rules, key=lambda rule: (rule.priority, rule.id)))
        self._cache: OrderedDict[CacheKey, CanonicalSymbol] = OrderedDict()
        self._metrics: dict[str, object] = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "unresolved_count": 0,
            "rule_usage": defaultdict(int),
        }
        self._persistence_conn = persistence_conn
        if self._persistence_conn is not None:
            SYMBOL_MAP_TABLE.ensure(self._persistence_conn)

    @property
    def rules(self) -> tuple[SymbolRule, ...]:
        """Return the rules currently registered with the service."""

        return self._rules

    def normalize(
        self,
        raw_symbol: str,
        market: MarketType,
        asset_type: AssetType,
        provider_hint: str | None = None,
    ) -> CanonicalSymbol:
        """Normalize a raw symbol into its canonical representation."""

        normalized_raw = raw_symbol.strip()
        cache_key: CacheKey = (normalized_raw, market, asset_type)
        self._metrics["total_requests"] = int(self._metrics["total_requests"]) + 1

        cached = self._cache_get(cache_key)
        if cached is not None:
            self._metrics["cache_hits"] = int(self._metrics["cache_hits"]) + 1
            return cached

        self._metrics["cache_misses"] = int(self._metrics["cache_misses"]) + 1
        canonical = self._evaluate_rules(normalized_raw, market, asset_type)
        self._persist_normalization(canonical, provider_hint)
        self._cache_set(cache_key, canonical)
        return canonical

    def normalize_batch(
        self,
        raw_symbols: Sequence[str],
        market: MarketType,
        asset_type: AssetType,
        provider_hint: str | Mapping[str, str] | None = None,
    ) -> BatchNormalizationResult:
        """Normalize a sequence of raw symbols with partial success reporting."""

        items: list[BatchNormalizationItem] = []
        successes: list[CanonicalSymbol] = []
        failures: list[UnresolvedSymbolError] = []

        for raw_symbol in raw_symbols:
            normalized_input = raw_symbol.strip()
            hint_value: str | None
            if isinstance(provider_hint, Mapping):
                hint_value = provider_hint.get(normalized_input)
                if hint_value is None and normalized_input != raw_symbol:
                    hint_value = provider_hint.get(raw_symbol)
            else:
                hint_value = provider_hint

            try:
                canonical = self.normalize(
                    normalized_input, market, asset_type, provider_hint=hint_value
                )
            except UnresolvedSymbolError as error:
                items.append(
                    BatchNormalizationItem(
                        raw_symbol=normalized_input,
                        status="unresolved",
                        error=error,
                    )
                )
                failures.append(error)
            else:
                items.append(
                    BatchNormalizationItem(
                        raw_symbol=normalized_input,
                        status="resolved",
                        canonical=canonical,
                    )
                )
                successes.append(canonical)

        return BatchNormalizationResult(
            market=market,
            asset_type=asset_type,
            items=tuple(items),
            successes=tuple(successes),
            failures=tuple(failures),
        )

    def get_metrics(self) -> Mapping[str, object]:
        """Return a snapshot of cache and normalization metrics."""

        total_requests = int(self._metrics["total_requests"])
        cache_hits = int(self._metrics["cache_hits"])
        cache_misses = int(self._metrics["cache_misses"])
        unresolved_count = int(self._metrics["unresolved_count"])
        hit_rate = cache_hits / total_requests if total_requests else 0.0
        rule_usage = dict(self._metrics["rule_usage"])
        return {
            "total_requests": total_requests,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "unresolved_count": unresolved_count,
            "hit_rate": hit_rate,
            "rule_usage": rule_usage,
        }

    def reload(self, new_rules: Sequence[SymbolRule]) -> None:
        """Atomically replace the rule set and clear derived caches."""

        if not new_rules:
            raise ValueError("SymbolService requires at least one rule for reload().")
        if not all(isinstance(rule, SymbolRule) for rule in new_rules):
            raise TypeError("All rules supplied to reload() must be SymbolRule instances.")

        self._rules = tuple(sorted(new_rules, key=lambda rule: (rule.priority, rule.id)))
        self._cache.clear()
        self._metrics["rule_usage"] = defaultdict(int)

    def _evaluate_rules(
        self,
        raw_symbol: str,
        market: MarketType,
        asset_type: AssetType,
    ) -> CanonicalSymbol:
        for rule in self._rules:
            if not rule.applies_to(market, asset_type):
                continue
            match = rule.pattern.match(raw_symbol)
            if not match:
                continue
            core_value = rule.transform(raw_symbol, match)
            if rule.prefix:
                core_value = f"{rule.prefix}{core_value}"
            if rule.suffix:
                core_value = f"{core_value}{rule.suffix}"
            canonical_value = self._compose_canonical(market, asset_type, core_value)
            canonical = CanonicalSymbol(
                raw_symbol=raw_symbol,
                canonical=canonical_value,
                market=market,
                asset_type=asset_type,
                rule_id=rule.id,
            )
            self._metrics["rule_usage"][rule.id] += 1
            return canonical

        self._metrics["unresolved_count"] = int(self._metrics["unresolved_count"]) + 1
        raise UnresolvedSymbolError(
            message=(f"Unable to normalize symbol '{raw_symbol}' for market '{market.value}' and asset '{asset_type.value}'."),
            raw_symbol=raw_symbol,
            market=market.value,
            asset_type=asset_type.value,
            details={"rules_evaluated": [rule.id for rule in self._rules]},
        )

    def _compose_canonical(self, market: MarketType, asset_type: AssetType, core_value: str) -> str:
        market_prefix = market.value.upper()
        asset_segment = asset_type.value.upper()
        return f"{market_prefix}:{asset_segment}:{core_value}"

    def _cache_get(self, key: CacheKey) -> CanonicalSymbol | None:
        try:
            cached = self._cache[key]
        except KeyError:
            return None
        self._cache.move_to_end(key)
        return cached

    def _cache_set(self, key: CacheKey, value: CanonicalSymbol) -> None:
        if self._cache_size == 0:
            return
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    def _persist_normalization(self, canonical: CanonicalSymbol, provider_hint: str | None) -> None:
        if self._persistence_conn is None:
            return

        self._persistence_conn.execute(
            """
            INSERT OR IGNORE INTO symbol_map (
                c_symbol,
                raw_symbol,
                market,
                asset_type,
                provider_hint,
                rule_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                canonical.canonical,
                canonical.raw_symbol,
                canonical.market.value,
                canonical.asset_type.value,
                provider_hint,
                canonical.rule_id,
                datetime.now(datetime.UTC),
            ],
        )


__all__ = ["SymbolService", "default_rules"]
