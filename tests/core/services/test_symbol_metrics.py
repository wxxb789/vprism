from __future__ import annotations

import re

import pytest

from vprism.core.exceptions.base import UnresolvedSymbolError
from vprism.core.models.market import AssetType, MarketType
from vprism.core.models.symbols import SymbolRule
from vprism.core.services.symbols import SymbolService


@pytest.fixture()
def metrics_service() -> SymbolService:
    numeric_rule = SymbolRule(
        id="cn_numeric",
        priority=10,
        pattern=re.compile(r"^(?P<code>\d{6})$"),
        transform=lambda raw, match: match.group("code"),
        market_scope=frozenset({MarketType.CN}),
        asset_scope=frozenset({AssetType.STOCK}),
    )
    return SymbolService(rules=[numeric_rule])


def test_metrics_capture_cache_behavior(metrics_service: SymbolService) -> None:
    service = metrics_service

    service.normalize("600010", MarketType.CN, AssetType.STOCK)
    first_metrics = service.get_metrics()
    assert first_metrics["total_requests"] == 1
    assert first_metrics["cache_hits"] == 0
    assert first_metrics["cache_misses"] == 1
    assert first_metrics["hit_rate"] == 0.0

    service.normalize("600010", MarketType.CN, AssetType.STOCK)
    second_metrics = service.get_metrics()
    assert second_metrics["total_requests"] == 2
    assert second_metrics["cache_hits"] == 1
    assert second_metrics["hit_rate"] == 0.5
    assert second_metrics["rule_usage"]["cn_numeric"] == 1


def test_metrics_track_unresolved(metrics_service: SymbolService) -> None:
    service = metrics_service

    with pytest.raises(UnresolvedSymbolError):
        service.normalize("BAD", MarketType.CN, AssetType.STOCK)

    metrics = service.get_metrics()
    assert metrics["unresolved_count"] == 1
    assert metrics["total_requests"] == 1
