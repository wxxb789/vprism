"""Tests for the Prometheus metrics collector."""

from prometheus_client import CollectorRegistry

from vprism.core.monitoring.metrics import MetricsCollector


def test_observe_query_updates_metrics() -> None:
    registry = CollectorRegistry()
    collector = MetricsCollector(registry=registry)

    collector.observe_query("alpha", 0.25, success=True)
    collector.observe_query("alpha", 0.40, success=False)

    count = registry.get_sample_value("vprism_query_latency_seconds_count")
    total_latency = registry.get_sample_value("vprism_query_latency_seconds_sum")
    total_requests = registry.get_sample_value(
        "vprism_query_requests_total",
        {"provider": "alpha"},
    )
    total_failures = registry.get_sample_value(
        "vprism_query_failures_total",
        {"provider": "alpha"},
    )
    error_rate = registry.get_sample_value(
        "vprism_provider_error_rate",
        {"provider": "alpha"},
    )

    assert count == 2.0
    assert total_latency == 0.65
    assert total_requests == 2.0
    assert total_failures == 1.0
    assert error_rate == 0.5


def test_increment_failure_without_latency_updates_counters() -> None:
    registry = CollectorRegistry()
    collector = MetricsCollector(registry=registry)

    collector.increment_failure("beta")

    total_requests = registry.get_sample_value(
        "vprism_query_requests_total",
        {"provider": "beta"},
    )
    total_failures = registry.get_sample_value(
        "vprism_query_failures_total",
        {"provider": "beta"},
    )
    error_rate = registry.get_sample_value(
        "vprism_provider_error_rate",
        {"provider": "beta"},
    )

    assert total_requests == 1.0
    assert total_failures == 1.0
    assert error_rate == 1.0
