"""Test library-mode interface (VPrismClient, global helpers, config)."""

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

import vprism
from vprism.core.client.client import VPrismClient
from vprism.core.exceptions import VPrismError
from vprism.core.models import AssetType, MarketType, TimeFrame


class TestVPrismClient:
    """Test VPrismClient class."""

    def test_configure(self):
        """Test configuration updates."""
        client = VPrismClient()

        client.configure(cache={"memory_size": 2000}, providers={"max_retries": 5})

        config = client.config_manager.get_config()
        assert config.cache.memory_size == 2000
        assert config.providers.max_retries == 5

    def test_query_builder(self):
        """Test fluent query builder."""
        client = VPrismClient()

        query = client.query().asset("stock").market("cn").symbols(["000001"]).timeframe("1d").date_range("2024-01-01", "2024-12-31").build()

        assert query.asset == AssetType.STOCK
        assert query.market == MarketType.CN
        assert query.symbols == ["000001"]
        assert query.timeframe == TimeFrame.DAY_1

    @patch(
        "vprism.core.data.routing.DataRouter.route_query",
        new_callable=AsyncMock,
    )
    @patch("vprism.core.data.providers.base.DataProvider.get_data")
    @pytest.mark.asyncio
    async def test_execute_query(self, mock_get_data, mock_route_query):
        """Test query execution via client."""
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = {"data": "test"}
        mock_route_query.return_value = mock_provider

        client = VPrismClient()

        query = client.query().asset("stock").market("cn").symbols(["000001"]).timeframe("1d").build()

        result = await client.execute(query)

        mock_route_query.assert_called_once_with(query)
        mock_provider.get_data.assert_called_once_with(query)
        assert result == {"data": "test"}

    @patch(
        "vprism.core.data.routing.DataRouter.route_query",
        new_callable=AsyncMock,
    )
    @patch("vprism.core.data.providers.base.DataProvider.get_data")
    def test_get_sync(self, mock_get_data, mock_route_query):
        """Test synchronous data retrieval."""

        async def mock_coro(query):
            return {"data": "sync_test"}

        mock_provider = AsyncMock()
        mock_provider.get_data = mock_coro
        mock_route_query.return_value = mock_provider

        client = VPrismClient()

        result = client.get(asset="stock", market="cn", symbols=["000001"], timeframe="1d")

        assert result == {"data": "sync_test"}

    @patch(
        "vprism.core.data.routing.DataRouter.route_query",
        new_callable=AsyncMock,
    )
    @patch("vprism.core.data.providers.base.DataProvider.get_data")
    @pytest.mark.asyncio
    async def test_get_async(self, mock_get_data, mock_route_query):
        """Test asynchronous data retrieval."""
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = {"data": "async_test"}
        mock_route_query.return_value = mock_provider

        client = VPrismClient()

        result = await client.get_async(asset="stock", market="cn", symbols=["000001"], timeframe="1d")

        assert result == {"data": "async_test"}


class TestGlobalInterface:
    """Test global module-level helpers."""

    @patch(
        "vprism.core.data.routing.DataRouter.route_query",
        new_callable=AsyncMock,
    )
    @patch("vprism.core.data.providers.base.DataProvider.get_data")
    def test_global_query_and_execute(self, mock_get_data, mock_route_query):
        """Test global query() and execute() helpers."""

        async def mock_coro(query):
            return {"data": "mock_execute"}

        mock_provider = AsyncMock()
        mock_provider.get_data = mock_coro
        mock_route_query.return_value = mock_provider

        query = vprism.query().asset("stock").market("us").symbols(["AAPL"]).timeframe("1d").build()

        result = asyncio.run(vprism.execute(query))

        assert result == {"data": "mock_execute"}


class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_invalid_asset_type(self):
        """Test that an invalid asset type raises ValueError."""
        with pytest.raises(ValueError):
            client = VPrismClient()
            client.get(asset="invalid_asset", market="cn", symbols=["000001"])

    def test_invalid_market_type(self):
        """Test that an invalid market type raises ValueError."""
        with pytest.raises(ValueError):
            client = VPrismClient()
            client.get(asset="stock", market="invalid_market", symbols=["000001"])

    def test_invalid_timeframe(self):
        """Test that an invalid timeframe raises ValueError."""
        with pytest.raises(ValueError):
            client = VPrismClient()
            client.get(asset="stock", market="cn", symbols=["000001"], timeframe="invalid")

    @patch(
        "vprism.core.data.routing.DataRouter.route_query",
        new_callable=AsyncMock,
    )
    @patch("vprism.core.data.providers.base.DataProvider.get_data")
    def test_provider_error_propagates(self, mock_get_data, mock_route_query):
        """Test that ProviderError propagates as VPrismError."""
        from vprism.core.exceptions.base import ProviderError

        async def mock_coro(query):
            raise ProviderError("Invalid stock symbol: 0000001", "akshare", "INVALID_SYMBOL")

        mock_provider = AsyncMock()
        mock_provider.get_data = mock_coro
        mock_route_query.return_value = mock_provider

        client = VPrismClient()
        with pytest.raises(VPrismError):
            client.get(asset="stock", market="cn", symbols=["0000001"])


class TestConfiguration:
    """Test configuration loading and priority."""

    def test_config_from_dict(self):
        """Test configuration from a dictionary."""
        config = {
            "cache": {"enabled": False, "memory_size": 500},
            "providers": {"timeout": 120, "max_retries": 10},
        }

        client = VPrismClient(config)
        config_obj = client.config_manager.get_config()

        assert config_obj.cache.enabled is False
        assert config_obj.cache.memory_size == 500
        assert config_obj.providers.timeout == 120
        assert config_obj.providers.max_retries == 10

    @patch.dict(os.environ, {"VPRISM_CACHE_ENABLED": "false", "VPRISM_PROVIDER_TIMEOUT": "90"})
    def test_config_from_env(self):
        """Test configuration from environment variables."""
        client = VPrismClient()
        config = client.config_manager.get_config()

        assert config.cache.enabled is False
        assert config.providers.timeout == 90

    def test_config_priority(self):
        """Test that explicit config overrides environment variables."""
        with patch.dict(os.environ, {"VPRISM_CACHE_ENABLED": "false"}):
            client = VPrismClient({"cache": {"enabled": True}})
            config = client.config_manager.get_config()

            assert config.cache.enabled is True
