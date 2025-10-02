"""Integration tests for the metrics endpoint."""

from fastapi.testclient import TestClient
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry

from vprism.core.monitoring.metrics import MetricsCollector, configure_metrics_collector
from vprism.web.app import create_app


def test_metrics_endpoint_exposes_prometheus_payload() -> None:
    registry = CollectorRegistry()
    collector = MetricsCollector(registry=registry)
    configure_metrics_collector(collector)

    app = create_app()
    collector.observe_query("alpha", 0.12, success=True)

    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "vprism_query_latency_seconds" in response.text
    assert "vprism_query_requests_total" in response.text
    assert response.headers["content-type"] == CONTENT_TYPE_LATEST

    configure_metrics_collector(None)
