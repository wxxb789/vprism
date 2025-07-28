"""
Web 服务测试套件
测试 FastAPI Web 服务的各个端点和功能
"""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "web"))
from web.app import create_app


class TestWebService:
    """Web 服务测试类"""

    @pytest.fixture
    def app(self):
        """创建 FastAPI 应用实例"""
        return create_app()

    @pytest.fixture
    def mock_client(self):
        """创建模拟的 VPrismClient"""
        from unittest.mock import Mock

        client = Mock()

        # 创建同步的查询构建器
        class MockQueryBuilder:
            def asset(self, symbol):
                self._asset = symbol
                return self

            def market(self, market):
                self._market = market
                return self

            def timeframe(self, timeframe):
                self._timeframe = timeframe
                return self

            def limit(self, limit):
                self._limit = limit
                return self

            def start_date(self, start_date):
                self._start_date = start_date
                return self

            def end_date(self, end_date):
                self._end_date = end_date
                return self

            def build(self):
                return "mock_query"

        query_builder = MockQueryBuilder()
        client.query.return_value = query_builder
        client.execute_async = AsyncMock()
        client.batch_get_async = AsyncMock()
        client.startup = AsyncMock()
        client.shutdown = AsyncMock()

        return client

    @pytest.mark.asyncio
    async def test_health_check(self, app, mock_client):
        """测试健康检查端点"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "checks" in data["data"]

    @pytest.mark.asyncio
    async def test_readiness_check(self, app, mock_client):
        """测试就绪检查端点"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.get("/api/v1/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["ready"] is True

    @pytest.mark.asyncio
    async def test_liveness_check(self, app):
        """测试存活检查端点"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["alive"] is True

    @pytest.mark.asyncio
    async def test_get_stock_data(self, app, mock_client):
        """测试获取股票数据端点"""
        # 设置模拟返回数据
        from decimal import Decimal

        from core.models import (
            DataPoint,
            DataResponse,
            ProviderInfo,
            ResponseMetadata,
        )

        mock_response = DataResponse(
            data=[
                DataPoint(
                    symbol="AAPL",
                    market="us",
                    timestamp=datetime(2024, 1, 1),
                    open_price=Decimal("100.0"),
                    high_price=Decimal("105.0"),
                    low_price=Decimal("99.0"),
                    close_price=Decimal("102.5"),
                    volume=Decimal("1000000"),
                    provider="test_provider",
                )
            ],
            metadata=ResponseMetadata(
                total_records=1, query_time_ms=150.5, data_source="test_provider"
            ),
            source=ProviderInfo(name="test_provider", endpoint="https://api.test.com"),
        )
        mock_client.execute_async.return_value = mock_response

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.get("/api/v1/data/stock/AAPL")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "AAPL" in data["message"]
        mock_client.execute_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_stock_data(self, app, mock_client):
        """测试 POST 方式获取股票数据"""
        from decimal import Decimal

        from core.models import (
            DataPoint,
            DataResponse,
            ProviderInfo,
            ResponseMetadata,
        )

        mock_response = DataResponse(
            data=[
                DataPoint(
                    symbol="AAPL",
                    market="us",
                    timestamp=datetime(2024, 1, 1),
                    close_price=Decimal("102.5"),
                    provider="test_provider",
                )
            ],
            metadata=ResponseMetadata(
                total_records=1, query_time_ms=100.0, data_source="test_provider"
            ),
            source=ProviderInfo(name="test_provider", endpoint="https://api.test.com"),
        )
        mock_client.execute_async.return_value = mock_response

        request_data = {
            "symbol": "AAPL",
            "market": "us",
            "timeframe": "daily",
            "limit": 5,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.post("/api/v1/data/stock", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_market_data_endpoint(self, app, mock_client):
        """测试市场数据端点"""
        from datetime import datetime
        from decimal import Decimal

        from core.models import (
            DataPoint,
            DataResponse,
            ProviderInfo,
            ResponseMetadata,
        )

        mock_response = DataResponse(
            data=[
                DataPoint(
                    symbol="^GSPC",
                    market="us",
                    timestamp=datetime(2024, 1, 1),
                    close_price=Decimal("3000.0"),
                    provider="test_provider",
                )
            ],
            metadata=ResponseMetadata(
                total_records=1, query_time_ms=150.0, data_source="test_provider"
            ),
            source=ProviderInfo(name="test_provider", endpoint="https://api.test.com"),
        )
        mock_client.execute_async.return_value = mock_response

        request_data = {
            "market": "us",
            "timeframe": "daily",
            "symbols": ["AAPL", "GOOGL"],
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.post("/api/v1/data/market", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_batch_data_endpoint(self, app, mock_client):
        """测试批量数据端点"""
        from decimal import Decimal

        from core.models import (
            DataPoint,
            DataResponse,
            ProviderInfo,
            ResponseMetadata,
        )

        mock_response1 = DataResponse(
            data=[
                DataPoint(
                    symbol="AAPL",
                    market="us",
                    timestamp=datetime(2024, 1, 1),
                    close_price=Decimal("150.0"),
                    provider="test_provider",
                )
            ],
            metadata=ResponseMetadata(
                total_records=1, query_time_ms=120.0, data_source="test_provider"
            ),
            source=ProviderInfo(name="test_provider", endpoint="https://api.test.com"),
        )
        mock_response2 = DataResponse(
            data=[
                DataPoint(
                    symbol="GOOGL",
                    market="us",
                    timestamp=datetime(2024, 1, 1),
                    close_price=Decimal("2500.0"),
                    provider="test_provider",
                )
            ],
            metadata=ResponseMetadata(
                total_records=1, query_time_ms=110.0, data_source="test_provider"
            ),
            source=ProviderInfo(name="test_provider", endpoint="https://api.test.com"),
        )
        mock_client.batch_get_async.return_value = [mock_response1, mock_response2]

        request_data = {
            "queries": [
                {"symbol": "AAPL", "market": "us", "timeframe": "daily"},
                {"symbol": "GOOGL", "market": "us", "timeframe": "daily"},
            ],
            "async_processing": False,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.post("/api/v1/data/batch", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 2

    @pytest.mark.asyncio
    async def test_symbols_endpoint(self, app, mock_client):
        """测试股票代码列表端点"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.get("/api/v1/data/symbols?market=us")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_batch_data_limit_exceeded(self, app, mock_client):
        """测试批量数据超出限制"""
        request_data = {
            "queries": [
                {"symbol": f"STOCK{i}", "market": "us", "timeframe": "daily"}
                for i in range(101)
            ],  # 超过100个限制
            "async_processing": False,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.post("/api/v1/data/batch", json=request_data)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_symbol_error(self, app, mock_client):
        """测试无效股票代码的错误处理"""
        mock_client.execute_async.side_effect = Exception("Invalid symbol")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.get("/api/v1/data/stock/INVALID")

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_provider_health_check(self, app, mock_client):
        """测试提供商健康检查"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.get("/api/v1/health/providers")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_cache_health_check(self, app, mock_client):
        """测试缓存健康检查"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.get("/api/v1/health/cache")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "hit_rate" in data["data"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, app, mock_client):
        """测试指标端点"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.get("/api/v1/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "uptime" in data["data"]

    @pytest.mark.asyncio
    async def test_cors_headers(self, app, mock_client):
        """测试 CORS 头设置"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            # 预检请求
            response = await ac.options("/api/v1/health")

        assert response.status_code == 405  # OPTIONS not supported for health check

    @pytest.mark.asyncio
    async def test_openapi_docs(self, app, mock_client):
        """测试 OpenAPI 文档"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_redoc_docs(self, app, mock_client):
        """测试 ReDoc 文档"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            app.state.vprism_client = mock_client

            response = await ac.get("/redoc")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
