"""
Tests for core client implementation.

This module contains comprehensive tests for the VPrismClient class,
ensuring proper functionality and error handling.
"""

import asyncio

import pytest

from vprism.core.client import VPrismClient
from vprism.core.exceptions import VPrismException
from vprism.core.models import AssetType, MarketType, TimeFrame


class TestVPrismClient:
    """Test VPrismClient class."""

    def test_client_initialization(self):
        """Test client initialization with default parameters."""
        client = VPrismClient()

        assert client.config == {}
        assert client._initialized is False
        assert client._data_service is None

    def test_client_initialization_with_config(self):
        """Test client initialization with configuration."""
        config = {"api_key": "test_key", "timeout": 30}
        client = VPrismClient(config=config)

        assert client.config == config
        assert client._initialized is False

    def test_client_initialization_with_kwargs(self):
        """Test client initialization with keyword arguments."""
        client = VPrismClient(api_key="test_key", timeout=30)

        assert client.config["api_key"] == "test_key"
        assert client.config["timeout"] == 30

    def test_client_initialization_config_merge(self):
        """Test that config dict and kwargs are merged properly."""
        config = {"api_key": "test_key", "timeout": 30}
        client = VPrismClient(config=config, timeout=60, debug=True)

        assert client.config["api_key"] == "test_key"
        assert client.config["timeout"] == 60  # kwargs override config
        assert client.config["debug"] is True

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test client as async context manager."""
        client = VPrismClient()

        async with client as c:
            assert c is client
            assert c._initialized is True

    @pytest.mark.asyncio
    async def test_ensure_initialized(self):
        """Test _ensure_initialized method."""
        client = VPrismClient()

        assert client._initialized is False
        await client._ensure_initialized()
        assert client._initialized is True

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test _cleanup method."""
        client = VPrismClient()

        # Should not raise any exceptions
        await client._cleanup()

    @pytest.mark.asyncio
    async def test_get_method_no_providers_available(self):
        """Test that get method raises NoAvailableProviderException when no providers are configured."""
        client = VPrismClient()

        with pytest.raises(VPrismException) as exc_info:
            await client.get(asset=AssetType.STOCK)

        assert exc_info.value.error_code == "NO_PROVIDER_AVAILABLE"
        assert "All capable providers failed to execute query" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_method_with_all_parameters(self):
        """Test get method with all parameters."""
        client = VPrismClient()

        with pytest.raises(VPrismException) as exc_info:
            await client.get(
                asset=AssetType.STOCK,
                market=MarketType.US,
                symbols=["AAPL", "GOOGL"],
                provider="test_provider",
                timeframe=TimeFrame.DAY_1,
                start="2024-01-01",
                end="2024-01-31",
                limit=100,
                custom_param="test_value",
            )

        assert exc_info.value.error_code == "NOT_IMPLEMENTED"
        # Check that query details are included
        assert "query" in exc_info.value.details

    def test_get_sync_method(self):
        """Test synchronous get method."""
        client = VPrismClient()

        with pytest.raises(VPrismException) as exc_info:
            client.get_sync(asset=AssetType.STOCK)

        assert exc_info.value.error_code == "NOT_IMPLEMENTED"

    def test_get_sync_with_parameters(self):
        """Test synchronous get method with parameters."""
        client = VPrismClient()

        with pytest.raises(VPrismException) as exc_info:
            client.get_sync(
                asset=AssetType.STOCK,
                market=MarketType.US,
                symbols=["AAPL"],
                provider="test_provider",
                timeframe=TimeFrame.DAY_1,
                limit=50,
            )

        assert exc_info.value.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_stream_method_not_implemented(self):
        """Test that stream method raises NotImplementedError."""
        client = VPrismClient()

        with pytest.raises(VPrismException) as exc_info:
            async for _ in client.stream(asset=AssetType.STOCK):
                pass

        assert exc_info.value.error_code == "NOT_IMPLEMENTED"
        assert "Streaming service not yet implemented" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_stream_method_with_parameters(self):
        """Test stream method with parameters."""
        client = VPrismClient()

        with pytest.raises(VPrismException) as exc_info:
            async for _ in client.stream(
                asset=AssetType.STOCK,
                market=MarketType.US,
                symbols=["AAPL"],
                provider="test_provider",
                custom_param="test_value",
            ):
                pass

        assert exc_info.value.error_code == "NOT_IMPLEMENTED"
        # Check that query details are included
        assert "query" in exc_info.value.details

    def test_configure_method(self):
        """Test configure method."""
        client = VPrismClient(api_key="old_key")

        assert client.config["api_key"] == "old_key"
        assert client._initialized is False

        client.configure(api_key="new_key", timeout=60)

        assert client.config["api_key"] == "new_key"
        assert client.config["timeout"] == 60
        assert client._initialized is False  # Should reset initialization

    def test_configure_resets_initialization(self):
        """Test that configure resets initialization flag."""
        client = VPrismClient()
        client._initialized = True

        client.configure(new_param="value")

        assert client._initialized is False

    @pytest.mark.asyncio
    async def test_multiple_initialization_calls(self):
        """Test that multiple initialization calls don't cause issues."""
        client = VPrismClient()

        await client._ensure_initialized()
        assert client._initialized is True

        # Second call should not change anything
        await client._ensure_initialized()
        assert client._initialized is True

    @pytest.mark.asyncio
    async def test_context_manager_exception_handling(self):
        """Test context manager handles exceptions properly."""
        client = VPrismClient()

        try:
            async with client:
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected

        # Client should still be properly cleaned up
        # (though cleanup is currently a no-op)

    def test_client_configuration_immutability(self):
        """Test that original config dict is not modified."""
        original_config = {"api_key": "test_key"}
        client = VPrismClient(config=original_config, timeout=30)

        # Original config should not be modified
        assert "timeout" not in original_config
        assert client.config["timeout"] == 30
        assert client.config["api_key"] == "test_key"


class TestVPrismClientIntegration:
    """Integration tests for VPrismClient."""

    @pytest.mark.asyncio
    async def test_full_async_workflow(self):
        """Test complete async workflow with context manager."""
        config = {"api_key": "test_key", "debug": True}

        async with VPrismClient(config=config) as client:
            assert client._initialized is True
            assert client.config["api_key"] == "test_key"
            assert client.config["debug"] is True

            # Try to use the client (will fail with not implemented)
            with pytest.raises(VPrismException):
                await client.get(asset=AssetType.STOCK)

    def test_sync_and_async_consistency(self):
        """Test that sync and async methods produce consistent results."""
        client = VPrismClient()

        # Both should raise the same type of exception
        with pytest.raises(VPrismException) as async_exc:
            asyncio.run(client.get(asset=AssetType.STOCK))

        with pytest.raises(VPrismException) as sync_exc:
            client.get_sync(asset=AssetType.STOCK)

        assert async_exc.value.error_code == sync_exc.value.error_code
        assert async_exc.value.message == sync_exc.value.message

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent operations on the same client."""
        client = VPrismClient()

        # Multiple concurrent get operations
        tasks = [
            client.get(asset=AssetType.STOCK, symbols=[f"SYMBOL{i}"]) for i in range(5)
        ]

        # All should fail with not implemented
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            assert isinstance(result, VPrismException)
            assert result.error_code == "NOT_IMPLEMENTED"

    def test_client_reusability(self):
        """Test that client can be reused after configuration changes."""
        client = VPrismClient(api_key="key1")

        # First configuration
        assert client.config["api_key"] == "key1"

        # Reconfigure
        client.configure(api_key="key2", timeout=60)
        assert client.config["api_key"] == "key2"
        assert client.config["timeout"] == 60

        # Should still work (though not implemented)
        with pytest.raises(VPrismException):
            client.get_sync(asset=AssetType.STOCK)
