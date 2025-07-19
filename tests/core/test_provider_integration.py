"""
Integration tests for the complete provider abstraction system.

This module tests the integration between DataProvider interfaces,
ProviderRegistry, and MockProviders to ensure the complete system
works together as designed.
"""

import pytest

from vprism.core import (
    MockDataProvider,
    AlwaysFailingProvider,
    RateLimitedProvider,
    ProviderRegistry,
    create_test_provider_suite,
)
from vprism.core.exceptions import (
    NoAvailableProviderException,
    ProviderException,
    RateLimitException,
)
from vprism.core.models import AssetType, DataQuery, MarketType


class TestProviderAbstractionIntegration:
    """Test complete provider abstraction system integration."""

    def test_provider_registration_and_discovery(self):
        """Test provider registration and discovery workflow."""
        registry = ProviderRegistry()

        # Create diverse providers
        stock_provider = MockDataProvider(
            "stock_specialist",
            supported_assets={AssetType.STOCK},
            supported_markets={MarketType.US, MarketType.CN},
        )

        crypto_provider = MockDataProvider(
            "crypto_specialist",
            supported_assets={AssetType.CRYPTO},
            supported_markets={MarketType.GLOBAL},
        )

        multi_provider = MockDataProvider(
            "multi_asset",
            supported_assets={AssetType.STOCK, AssetType.ETF, AssetType.BOND},
            supported_markets={MarketType.US, MarketType.EU},
        )

        # Register providers
        registry.register_provider(stock_provider, {"api_key": "stock_key"})
        registry.register_provider(crypto_provider, {"api_key": "crypto_key"})
        registry.register_provider(multi_provider, {"api_key": "multi_key"})

        # Test discovery by asset type
        stock_query = DataQuery(asset=AssetType.STOCK, market=MarketType.US)
        stock_providers = registry.find_providers(stock_query)

        assert len(stock_providers) == 2  # stock_specialist + multi_asset
        provider_names = {p.name for p in stock_providers}
        assert "stock_specialist" in provider_names
        assert "multi_asset" in provider_names

        # Test discovery by crypto
        crypto_query = DataQuery(asset=AssetType.CRYPTO)
        crypto_providers = registry.find_providers(crypto_query)

        assert len(crypto_providers) == 1
        assert crypto_providers[0].name == "crypto_specialist"

        # Test discovery with no matches
        forex_query = DataQuery(asset=AssetType.FOREX)
        forex_providers = registry.find_providers(forex_query)

        assert len(forex_providers) == 0

    @pytest.mark.asyncio
    async def test_provider_health_monitoring(self):
        """Test provider health monitoring and filtering."""
        registry = ProviderRegistry()

        healthy_provider = MockDataProvider("healthy", is_healthy=True)
        unhealthy_provider = MockDataProvider("unhealthy", is_healthy=False)
        failing_provider = AlwaysFailingProvider("always_failing")

        registry.register_provider(healthy_provider)
        registry.register_provider(unhealthy_provider)
        registry.register_provider(failing_provider)

        # Check initial health
        health_results = await registry.check_all_provider_health()

        assert health_results["healthy"] is True
        assert health_results["unhealthy"] is False
        assert health_results["always_failing"] is False

        # Test that only healthy providers are returned in queries
        query = DataQuery(asset=AssetType.STOCK)
        available_providers = registry.find_providers(query)

        assert len(available_providers) == 1
        assert available_providers[0].name == "healthy"

    @pytest.mark.asyncio
    async def test_provider_error_handling_and_fallback(self):
        """Test error handling and fallback scenarios."""
        registry = ProviderRegistry()

        # Create providers with different failure modes
        reliable_provider = MockDataProvider("reliable", failure_rate=0.0)
        unreliable_provider = MockDataProvider("unreliable", failure_rate=0.8)
        failing_provider = AlwaysFailingProvider("failing")

        registry.register_provider(reliable_provider)
        registry.register_provider(unreliable_provider)
        registry.register_provider(failing_provider)

        query = DataQuery(asset=AssetType.STOCK, symbols=["TEST001"])

        # Test that we can get providers even when some fail
        available_providers = registry.find_providers(query)

        # Should have reliable and unreliable (failing is marked unhealthy)
        assert len(available_providers) >= 1

        # Test data retrieval from reliable provider
        reliable_response = await reliable_provider.get_data(query)
        assert len(reliable_response.data) > 0

        # Test that failing provider always fails
        with pytest.raises(ProviderException):
            await failing_provider.get_data(query)

    @pytest.mark.asyncio
    async def test_rate_limiting_across_providers(self):
        """Test rate limiting behavior across different providers."""
        registry = ProviderRegistry()

        # Create rate-limited providers
        limited_provider = RateLimitedProvider("limited", rate_limit=2)
        unlimited_provider = MockDataProvider("unlimited", rate_limit=1000)

        registry.register_provider(limited_provider)
        registry.register_provider(unlimited_provider)

        query = DataQuery(asset=AssetType.STOCK)

        # Use up the rate limit on limited provider
        await limited_provider.get_data(query)
        await limited_provider.get_data(query)

        # Third request should fail
        with pytest.raises(RateLimitException):
            await limited_provider.get_data(query)

        # But unlimited provider should still work
        response = await unlimited_provider.get_data(query)
        assert len(response.data) > 0

    def test_provider_configuration_management(self):
        """Test provider configuration management."""
        registry = ProviderRegistry()
        provider = MockDataProvider("configurable")

        initial_config = {
            "api_key": "initial_key",
            "timeout": 30,
            "base_url": "https://api.example.com",
        }

        # Register with initial config
        registry.register_provider(provider, initial_config)

        # Verify config is stored
        stored_config = registry.get_provider_config("configurable")
        assert stored_config == initial_config

        # Update config
        updated_config = {
            "api_key": "updated_key",
            "timeout": 60,
            "base_url": "https://api.example.com",
            "retry_count": 3,
        }

        registry.update_provider_config("configurable", updated_config)

        # Verify config is updated
        new_stored_config = registry.get_provider_config("configurable")
        assert new_stored_config == updated_config
        assert new_stored_config["retry_count"] == 3

    def test_provider_metadata_and_info(self):
        """Test provider metadata and information management."""
        registry = ProviderRegistry()

        provider = MockDataProvider("metadata_test", version="2.1.0", cost="premium")

        registry.register_provider(provider)

        # Test provider info retrieval
        info = registry.get_provider_info("metadata_test")

        assert info is not None
        assert info.name == "metadata_test"
        assert info.version == "2.1.0"
        assert info.cost == "premium"
        assert info.url == "https://api.metadata-test.com"

    def test_provider_statistics_and_monitoring(self):
        """Test provider statistics and monitoring."""
        registry = ProviderRegistry()

        # Create diverse provider suite
        providers = create_test_provider_suite()

        for name, provider in providers.items():
            registry.register_provider(provider)

        # Get statistics
        stats = registry.get_provider_statistics()

        assert stats["total_providers"] == len(providers)
        assert stats["healthy_providers"] > 0
        assert "asset_coverage" in stats
        assert "provider_names" in stats

        # Check asset coverage
        assert stats["asset_coverage"][AssetType.STOCK.value] > 0
        assert stats["asset_coverage"][AssetType.CRYPTO.value] > 0

    @pytest.mark.asyncio
    async def test_complete_data_retrieval_workflow(self):
        """Test complete data retrieval workflow from query to response."""
        registry = ProviderRegistry()

        # Set up providers
        us_stock_provider = MockDataProvider(
            "us_stocks",
            supported_assets={AssetType.STOCK},
            supported_markets={MarketType.US},
        )

        cn_stock_provider = MockDataProvider(
            "cn_stocks",
            supported_assets={AssetType.STOCK},
            supported_markets={MarketType.CN},
        )

        registry.register_provider(us_stock_provider)
        registry.register_provider(cn_stock_provider)

        # Test US stock query
        us_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL", "GOOGL"],
            limit=50,
        )

        us_providers = registry.find_providers(us_query)
        assert len(us_providers) == 1
        assert us_providers[0].name == "us_stocks"

        # Get data from US provider
        us_response = await us_providers[0].get_data(us_query)

        assert len(us_response.data) > 0
        assert us_response.source.name == "us_stocks"
        assert us_response.query == us_query

        # Test CN stock query
        cn_query = DataQuery(
            asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001", "000002"]
        )

        cn_providers = registry.find_providers(cn_query)
        assert len(cn_providers) == 1
        assert cn_providers[0].name == "cn_stocks"

        # Get data from CN provider
        cn_response = await cn_providers[0].get_data(cn_query)

        assert len(cn_response.data) > 0
        assert cn_response.source.name == "cn_stocks"

    @pytest.mark.asyncio
    async def test_streaming_data_integration(self):
        """Test streaming data integration across providers."""
        registry = ProviderRegistry()

        streaming_provider = MockDataProvider("streaming_test")
        registry.register_provider(streaming_provider)

        query = DataQuery(asset=AssetType.STOCK, symbols=["STREAM001", "STREAM002"])

        # Test streaming
        stream_count = 0
        received_symbols = set()

        async for data_point in streaming_provider.stream_data(query):
            stream_count += 1
            received_symbols.add(data_point.symbol)

            if stream_count >= 10:  # Limit for test
                break

        assert stream_count == 10
        assert len(received_symbols) > 0
        assert all(symbol in ["STREAM001", "STREAM002"] for symbol in received_symbols)

    def test_provider_suite_completeness(self):
        """Test that the provider suite covers all major scenarios."""
        suite = create_test_provider_suite()

        # Verify we have providers for different scenarios
        assert "healthy_stock" in suite
        assert "always_failing" in suite
        assert "rate_limited" in suite
        assert "slow_provider" in suite

        # Verify asset type coverage
        all_assets = set()
        for provider in suite.values():
            all_assets.update(provider.supported_assets)

        # Should cover major asset types
        assert AssetType.STOCK in all_assets
        assert AssetType.CRYPTO in all_assets
        assert AssetType.BOND in all_assets

    @pytest.mark.asyncio
    async def test_concurrent_provider_operations(self):
        """Test concurrent operations across multiple providers."""
        import asyncio

        registry = ProviderRegistry()

        # Create multiple providers
        providers = [
            MockDataProvider(f"concurrent_{i}", rate_limit=100) for i in range(5)
        ]

        for provider in providers:
            registry.register_provider(provider)

        query = DataQuery(asset=AssetType.STOCK, symbols=["CONCURRENT"])

        # Make concurrent requests to all providers
        tasks = [provider.get_data(query) for provider in providers]

        responses = await asyncio.gather(*tasks)

        # All requests should succeed
        assert len(responses) == 5
        for response in responses:
            assert len(response.data) > 0
            assert response.metadata.record_count > 0

    def test_provider_lifecycle_management(self):
        """Test complete provider lifecycle management."""
        registry = ProviderRegistry()

        # 1. Registration
        provider = MockDataProvider("lifecycle")
        config = {"key": "value"}

        registry.register_provider(provider, config)
        assert registry.get_provider("lifecycle") == provider

        # 2. Configuration updates
        new_config = {"key": "new_value", "timeout": 30}
        registry.update_provider_config("lifecycle", new_config)
        assert registry.get_provider_config("lifecycle") == new_config

        # 3. Health monitoring
        registry.update_provider_health("lifecycle", False)
        query = DataQuery(asset=AssetType.STOCK)
        unhealthy_providers = registry.find_providers(query)
        assert len(unhealthy_providers) == 0  # Should be filtered out

        # 4. Health restoration
        registry.update_provider_health("lifecycle", True)
        healthy_providers = registry.find_providers(query)
        assert len(healthy_providers) == 1

        # 5. Unregistration
        result = registry.unregister_provider("lifecycle")
        assert result is True
        assert registry.get_provider("lifecycle") is None
