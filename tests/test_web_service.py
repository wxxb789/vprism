"""Test FastAPI web service endpoints."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from vprism.core.models import (
    DataPoint,
    DataResponse,
    ProviderInfo,
    ResponseMetadata,
)
from vprism.web.app import create_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_PROVIDER = ProviderInfo(name="test_provider", endpoint="https://api.test.com")


def _make_response(
    *points: DataPoint,
    query_time_ms: float = 100.0,
) -> DataResponse:
    """Build a DataResponse from one or more DataPoints."""
    data = list(points)
    return DataResponse(
        data=data,
        metadata=ResponseMetadata(
            total_records=len(data),
            query_time_ms=query_time_ms,
            data_source="test_provider",
        ),
        source=_TEST_PROVIDER,
    )


def _stock_point(
    symbol: str = "AAPL",
    market: str = "us",
    close: str = "102.50",
    **overrides,
) -> DataPoint:
    """Create a DataPoint with sensible defaults."""
    defaults = {
        "symbol": symbol,
        "market": market,
        "timestamp": datetime(2024, 1, 1),
        "close_price": Decimal(close),
        "provider": "test_provider",
    }
    defaults.update(overrides)
    return DataPoint(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVPrismWebService:
    """Web service test suite."""

    @pytest.fixture
    def vprism_mock_client(self):
        """Create a mock VPrismClient."""

        class MockQueryBuilder:
            def symbols(self, symbols):
                self._symbols = symbols
                return self

            def market(self, market):
                self._market = market
                return self

            def timeframe(self, timeframe):
                self._timeframe = timeframe
                return self

            def start(self, start_date):
                self._start_date = start_date
                return self

            def end(self, end_date):
                self._end_date = end_date
                return self

            def build(self):
                return "mock_query"

        client = Mock()
        client.query.return_value = MockQueryBuilder()
        client.execute = AsyncMock()
        client.batch_get_async = AsyncMock()
        client.startup = AsyncMock()
        client.shutdown = AsyncMock()
        return client

    @pytest.fixture
    async def client(self, vprism_mock_client):
        """Create an async HTTP client wired to the FastAPI app."""
        app = create_app()
        app.state.vprism_client = vprism_mock_client
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    # -- Health endpoints ---------------------------------------------------

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test /health endpoint."""
        response = await client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "checks" in data["data"]

    @pytest.mark.asyncio
    async def test_readiness_check(self, client):
        """Test /health/ready endpoint."""
        response = await client.get("/api/v1/health/ready")

        assert response.status_code == 200
        assert response.json()["data"]["ready"] is True

    @pytest.mark.asyncio
    async def test_liveness_check(self, client):
        """Test /health/live endpoint."""
        response = await client.get("/api/v1/health/live")

        assert response.status_code == 200
        assert response.json()["data"]["alive"] is True

    @pytest.mark.asyncio
    async def test_provider_health_check(self, client):
        """Test /health/providers endpoint."""
        response = await client.get("/api/v1/health/providers")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_cache_health_check(self, client):
        """Test /health/cache endpoint."""
        response = await client.get("/api/v1/health/cache")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "hit_rate" in data["data"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client):
        """Test /metrics endpoint."""
        response = await client.get("/api/v1/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "uptime" in data["data"]

    # -- Data endpoints -----------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_stock_data(self, client, vprism_mock_client):
        """Test GET /data/stock/{symbol}."""
        point = _stock_point(
            open_price=Decimal("100.0"),
            high_price=Decimal("105.0"),
            low_price=Decimal("99.0"),
            volume=Decimal("1000000"),
        )
        vprism_mock_client.execute.return_value = _make_response(point, query_time_ms=150.5)

        response = await client.get("/api/v1/data/stock/AAPL")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "AAPL" in data["message"]
        vprism_mock_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_stock_data(self, client, vprism_mock_client):
        """Test POST /data/stock."""
        vprism_mock_client.execute.return_value = _make_response(_stock_point())

        response = await client.post(
            "/api/v1/data/stock",
            json={"symbol": "AAPL", "market": "us", "timeframe": "daily", "limit": 5},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_market_data_endpoint(self, client, vprism_mock_client):
        """Test POST /data/market."""
        vprism_mock_client.execute.return_value = _make_response(
            _stock_point(symbol="^GSPC", close="3000.0"),
            query_time_ms=150.0,
        )

        response = await client.post(
            "/api/v1/data/market",
            json={"market": "us", "timeframe": "daily", "symbols": ["AAPL", "GOOGL"]},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_batch_data_endpoint(self, client, vprism_mock_client):
        """Test POST /data/batch with multiple queries."""
        vprism_mock_client.execute.side_effect = [
            _make_response(_stock_point(close="150.0"), query_time_ms=120.0),
            _make_response(_stock_point(symbol="GOOGL", close="2500.0"), query_time_ms=110.0),
        ]

        response = await client.post(
            "/api/v1/data/batch",
            json={
                "queries": [
                    {"symbol": "AAPL", "market": "us", "timeframe": "daily"},
                    {"symbol": "GOOGL", "market": "us", "timeframe": "daily"},
                ],
                "async_processing": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 2

    @pytest.mark.asyncio
    async def test_symbols_endpoint(self, client):
        """Test GET /data/symbols."""
        response = await client.get("/api/v1/data/symbols?market=us")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    # -- Error cases --------------------------------------------------------

    @pytest.mark.asyncio
    async def test_batch_data_limit_exceeded(self, client):
        """Test that batch requests exceeding 100 queries are rejected."""
        response = await client.post(
            "/api/v1/data/batch",
            json={
                "queries": [{"symbol": f"STOCK{i}", "market": "us", "timeframe": "daily"} for i in range(101)],
                "async_processing": False,
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_symbol_error(self, client, vprism_mock_client):
        """Test error handling for invalid stock symbols."""
        vprism_mock_client.execute.side_effect = Exception("Invalid symbol")

        response = await client.get("/api/v1/data/stock/INVALID")

        assert response.status_code == 400
        assert response.json()["success"] is False
