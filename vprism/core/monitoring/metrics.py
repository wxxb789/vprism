"""Prometheus metrics helpers for VPrism services."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest


@dataclass
class _ProviderStats:
    """Internal container tracking provider level success and failure counts."""

    total: int = 0
    failures: int = 0


class MetricsCollector:
    """Collects and exposes core Prometheus metrics for service operations."""

    def __init__(self, *, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        self.query_latency_seconds = Histogram(
            "vprism_query_latency_seconds",
            "Latency distribution for upstream data provider queries.",
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
            registry=self.registry,
        )
        self.query_requests_total = Counter(
            "vprism_query_requests_total",
            "Total count of upstream data provider queries.",
            ("provider",),
            registry=self.registry,
        )
        self.query_failures_total = Counter(
            "vprism_query_failures_total",
            "Total count of failed upstream data provider queries.",
            ("provider",),
            registry=self.registry,
        )
        self.provider_error_rate = Gauge(
            "vprism_provider_error_rate",
            "Rolling error rate for upstream data providers (0-1 range).",
            ("provider",),
            registry=self.registry,
        )
        self.symbol_normalization_total = Counter(
            "vprism_symbol_normalization_total",
            "Symbol normalization outcomes grouped by cache and resolution status.",
            ("status",),
            registry=self.registry,
        )
        self._provider_stats: DefaultDict[str, _ProviderStats] = defaultdict(_ProviderStats)

    def record_symbol_normalization(self, status: str) -> None:
        """Track symbol normalization activity with constrained status labels."""

        label = status if status in _ALLOWED_SYMBOL_STATUSES else "__other__"
        self.symbol_normalization_total.labels(status=label).inc()

    def observe_query(self, provider: str, latency_seconds: float, *, success: bool = True) -> None:
        """Record a provider query execution."""

        self.query_latency_seconds.observe(latency_seconds)
        self._record_outcome(provider=provider, success=success)

    def increment_failure(self, provider: str) -> None:
        """Increment failure counters when a query fails before latency is captured."""

        self._record_outcome(provider=provider, success=False)

    def render(self) -> bytes:
        """Render metrics in Prometheus exposition format."""

        return generate_latest(self.registry)

    def _record_outcome(self, *, provider: str, success: bool) -> None:
        stats = self._provider_stats[provider]
        stats.total += 1
        self.query_requests_total.labels(provider=provider).inc()
        if not success:
            stats.failures += 1
            self.query_failures_total.labels(provider=provider).inc()
        error_rate = stats.failures / stats.total if stats.total else 0.0
        self.provider_error_rate.labels(provider=provider).set(error_rate)


_DEFAULT_COLLECTOR: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Return the global metrics collector instance."""

    global _DEFAULT_COLLECTOR
    if _DEFAULT_COLLECTOR is None:
        _DEFAULT_COLLECTOR = MetricsCollector()
    return _DEFAULT_COLLECTOR


def configure_metrics_collector(collector: MetricsCollector | None) -> None:
    """Override the global metrics collector for application wiring or tests."""

    global _DEFAULT_COLLECTOR
    _DEFAULT_COLLECTOR = collector


_ALLOWED_SYMBOL_STATUSES = {
    "total",
    "cache_hit",
    "cache_miss",
    "resolved",
    "unresolved",
}
