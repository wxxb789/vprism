from __future__ import annotations

import re

import pytest
from prometheus_client import CollectorRegistry

from vprism.core.exceptions.base import UnresolvedSymbolError
from vprism.core.models.market import AssetType, MarketType
from vprism.core.models.symbols import SymbolRule
from vprism.core.monitoring.metrics import (
    MetricsCollector,
    configure_metrics_collector,
)
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


@pytest.fixture()
def collector_service(metrics_service: SymbolService) -> tuple[SymbolService, CollectorRegistry]:
    registry = CollectorRegistry()
    collector = MetricsCollector(registry=registry)
    service = SymbolService(rules=metrics_service.rules, metrics_collector=collector)
    return service, registry


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


def test_metrics_collector_tracks_symbol_statuses(
    collector_service: tuple[SymbolService, CollectorRegistry],
) -> None:
    service, registry = collector_service

    service.normalize("600010", MarketType.CN, AssetType.STOCK)
    service.normalize("600010", MarketType.CN, AssetType.STOCK)
    with pytest.raises(UnresolvedSymbolError):
        service.normalize("BAD000", MarketType.CN, AssetType.STOCK)

    total = registry.get_sample_value(
        "vprism_symbol_normalization_total",
        {"status": "total"},
    )
    cache_hit = registry.get_sample_value(
        "vprism_symbol_normalization_total",
        {"status": "cache_hit"},
    )
    cache_miss = registry.get_sample_value(
        "vprism_symbol_normalization_total",
        {"status": "cache_miss"},
    )
    unresolved = registry.get_sample_value(
        "vprism_symbol_normalization_total",
        {"status": "unresolved"},
    )
    resolved = registry.get_sample_value(
        "vprism_symbol_normalization_total",
        {"status": "resolved"},
    )

    assert total == 3.0
    assert cache_hit == 1.0
    assert cache_miss == 2.0
    assert unresolved == 1.0
    assert resolved == 2.0


def test_service_uses_global_metrics_collector() -> None:
    registry = CollectorRegistry()
    collector = MetricsCollector(registry=registry)
    configure_metrics_collector(collector)

    try:
        numeric_rule = SymbolRule(
            id="cn_numeric",
            priority=10,
            pattern=re.compile(r"^(?P<code>\d{6})$"),
            transform=lambda raw, match: match.group("code"),
            market_scope=frozenset({MarketType.CN}),
            asset_scope=frozenset({AssetType.STOCK}),
        )
        service = SymbolService(rules=[numeric_rule])

        service.normalize("600010", MarketType.CN, AssetType.STOCK)

        total = registry.get_sample_value(
            "vprism_symbol_normalization_total",
            {"status": "total"},
        )
        resolved = registry.get_sample_value(
            "vprism_symbol_normalization_total",
            {"status": "resolved"},
        )

        assert total == 1.0
        assert resolved == 1.0
    finally:
        configure_metrics_collector(None)
