from __future__ import annotations

import re

import pytest

from vprism.core.exceptions.base import UnresolvedSymbolError
from vprism.core.models.market import AssetType, MarketType
from vprism.core.models.symbols import SymbolRule
from vprism.core.services.symbols import SymbolService


@pytest.fixture()
def sample_rules() -> list[SymbolRule]:
    return [
        SymbolRule(
            id="cn_stock_numeric",
            priority=10,
            pattern=re.compile(r"^(?P<code>\d{6})$"),
            transform=lambda raw, match: match.group("code"),
            market_scope=frozenset({MarketType.CN}),
            asset_scope=frozenset({AssetType.STOCK}),
        ),
        SymbolRule(
            id="fallback_upper",
            priority=20,
            pattern=re.compile(r"^(?P<token>[A-Z]{1,5})$", re.IGNORECASE),
            transform=lambda raw, match: match.group("token").upper(),
            market_scope=frozenset(),
            asset_scope=frozenset(),
        ),
    ]


def test_normalize_returns_canonical_symbol(sample_rules: list[SymbolRule]) -> None:
    service = SymbolService(rules=sample_rules)

    result = service.normalize("600000", MarketType.CN, AssetType.STOCK)

    assert result.canonical == "CN:STOCK:600000"
    assert result.rule_id == "cn_stock_numeric"


def test_normalize_uses_cache_metrics(sample_rules: list[SymbolRule]) -> None:
    service = SymbolService(rules=sample_rules)

    first = service.normalize("600000", MarketType.CN, AssetType.STOCK)
    metrics_after_first = service.get_metrics()
    assert metrics_after_first["cache_hits"] == 0
    assert metrics_after_first["cache_misses"] == 1

    second = service.normalize("600000", MarketType.CN, AssetType.STOCK)
    metrics_after_second = service.get_metrics()
    assert second is first
    assert metrics_after_second["cache_hits"] == 1
    assert metrics_after_second["total_requests"] == 2


def test_normalize_raises_unresolved_with_diagnostics(sample_rules: list[SymbolRule]) -> None:
    service = SymbolService(rules=sample_rules)

    with pytest.raises(UnresolvedSymbolError) as exc_info:
        service.normalize("@@INVALID@@", MarketType.CN, AssetType.STOCK)

    error = exc_info.value
    assert error.error_code == "SYMBOL_UNRESOLVED"
    assert error.details["raw_symbol"] == "@@INVALID@@"
    assert error.details["market"] == MarketType.CN.value
    assert error.details["asset_type"] == AssetType.STOCK.value


def test_rule_priority_short_circuits(sample_rules: list[SymbolRule]) -> None:
    high_priority = SymbolRule(
        id="high_priority",
        priority=0,
        pattern=re.compile(r"^(?P<code>\d{6})$"),
        transform=lambda raw, match: f"A{match.group('code')}",
        market_scope=frozenset({MarketType.CN}),
        asset_scope=frozenset({AssetType.STOCK}),
    )
    rules = [sample_rules[1], sample_rules[0], high_priority]
    service = SymbolService(rules=rules)

    result = service.normalize("600001", MarketType.CN, AssetType.STOCK)

    assert result.canonical == "CN:STOCK:A600001"
    assert result.rule_id == "high_priority"
    metrics = service.get_metrics()
    assert metrics["rule_usage"]["high_priority"] == 1
