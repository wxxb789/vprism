"""FastAPI utilities for Prometheus metrics exposure."""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST

from vprism.core.monitoring.metrics import get_metrics_collector


router = APIRouter()


@router.get("/metrics", include_in_schema=False, summary="Prometheus metrics endpoint")
def metrics_endpoint() -> Response:
    """Expose collected metrics in Prometheus text format."""

    collector = get_metrics_collector()
    return Response(content=collector.render(), media_type=CONTENT_TYPE_LATEST)
