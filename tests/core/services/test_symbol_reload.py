from __future__ import annotations

import re

import pytest

from vprism.core.models.market import AssetType, MarketType
from vprism.core.models.symbols import SymbolRule
from vprism.core.services.symbols import SymbolService


def _rule_with_prefix(prefix: str, priority: int) -> SymbolRule:
    return SymbolRule(
        id=f"rule_{prefix.lower()}",
        priority=priority,
        pattern=re.compile(r"^(?P<code>\d{6})$"),
        transform=lambda raw, match, p=prefix: f"{p}{match.group('code')}",
        market_scope=frozenset({MarketType.CN}),
        asset_scope=frozenset({AssetType.STOCK}),
    )


def test_reload_replaces_rules_and_clears_cache() -> None:
    original_rule = _rule_with_prefix("OLD", 10)
    service = SymbolService(rules=[original_rule])

    first = service.normalize("600500", MarketType.CN, AssetType.STOCK)
    assert first.canonical == "CN:STOCK:OLD600500"

    metrics_before = service.get_metrics()
    assert metrics_before["cache_misses"] == 1

    new_rule = _rule_with_prefix("NEW", 5)
    service.reload([new_rule])

    second = service.normalize("600500", MarketType.CN, AssetType.STOCK)
    assert second.canonical == "CN:STOCK:NEW600500"

    metrics_after = service.get_metrics()
    assert metrics_after["cache_hits"] == 0
    assert metrics_after["cache_misses"] == 2
    assert metrics_after["rule_usage"]["rule_new"] == 1
    assert "rule_old" not in metrics_after["rule_usage"]


def test_reload_rejects_empty_rule_set() -> None:
    service = SymbolService(rules=[_rule_with_prefix("A", 1)])

    with pytest.raises(ValueError):
        service.reload([])

    with pytest.raises(TypeError):
        service.reload(["not-a-rule"])  # type: ignore[arg-type]
