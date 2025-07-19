"""
Integration tests for DataRouter with the complete provider system.

This module tests the integration between DataRouter, ProviderRegistry,
and various provider implementations to ensure the complete routing
system works as designed.
"""

import pytest

from vprism.core.data_router import DataRouter, RoutingStrategy
from vprism.core.exceptions import NoAvailableProviderException
from vprism.core.mock_providers import (
    MOCK_STOCK_PROVIDER,
    MOCK_CRYPTO_PROVIDER,
    MOCK_BOND_PROVIDER,
    AlwaysFailingProvider,
    MockDataProvider,
    create_test_provider_suite,
)
from vprism.core.models import AssetType, DataQuery, MarketType
from vprism.core.provider_registry import ProviderRegistry


class TestDataRouterIntegrationComplete:
    """Complete integration tests for DataRouter system."""

    @pytest.mark.asyncio
    async def test_complete_routing_workflow_with_registry(self):
        """Test complete routing workflow using ProviderRegistry."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Register diverse providers
        registry.register_provider(MOCK_STOCK_PROVIDER)
        registry.register_provider(MOCK_CRYPTO_PROVIDER)
        registry.register_provider(MOCK_BOND_PROVIDER)
        
        # Test stock query routing
        stock_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL", "GOOGL"],
        )
        
        selected_provider = await router.route_query(stock_query)
        
        assert selected_provider == MOCK_STOCK_PROVIDER
        assert selected_provider.can_handle_query(stock_query)
        
        # Test crypto query routing
        crypto_query = DataQuery(
            asset=AssetType.CRYPTO,
            symbols=["BTC", "ETH"],
        )
        
        selected_provider = await router.route_query(crypto_query)
        
        assert selected_provider == MOCK_CRYPTO_PROVIDER
        assert selected_provider.can_handle_query(crypto_query)

    @pytest.mark.asyncio
    async def test_routing_with_health_monitoring(self):
        """Test routing with automatic health monitoring."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Mix of healthy and unhealthy providers
        healthy_provider = MockDataProvider("healthy", is_healthy=True)
        unhealthy_provider = MockDataProvider("unhealthy", is_healthy=False)
        failing_provider = AlwaysFailingProvider("failing")
        
        router.register_provider(healthy_provider)
        router.register_provider(unhealthy_provider)
        router.register_provider(failing_provider)
        
        # Perform health checks
        health_results = await router.check_all_provider_health()
        
        assert health_results["healthy"] is True
        assert health_results["unhealthy"] is False
        assert health_results["failing"] is False
        
        # Routing should select only healthy provider
        query = DataQuery(asset=AssetType.STOCK)
        selected_provider = await router.route_query(query)
        
        assert selected_provider == healthy_provider

    @pytest.mark.asyncio
    async def test_routing_strategies_comparison(self):
        """Test different routing strategies with same provider set."""
        registry = ProviderRegistry()
        
        providers = [
            MockDataProvider("provider1"),
            MockDataProvider("provider2"),
            MockDataProvider("provider3"),
        ]
        
        strategies = [
            RoutingStrategy.INTELLIGENT,
            RoutingStrategy.ROUND_ROBIN,
            RoutingStrategy.RANDOM,
            RoutingStrategy.WEIGHTED,
        ]
        
        query = DataQuery(asset=AssetType.STOCK)
        
        for strategy in strategies:
            router = DataRouter(registry, routing_strategy=strategy)
            
            # Register providers with the router (which also registers with registry)
            for provider in providers:
                router.register_provider(provider)
            
            # Make multiple requests
            selections = []
            for _ in range(6):
                selected = await router.route_query(query)
                selections.append(selected.name)
            
            # All strategies should work and select valid providers
            assert len(selections) == 6
            assert all(name in ["provider1", "provider2", "provider3"] for name in selections)
            
            # Round-robin should show predictable pattern
            if strategy == RoutingStrategy.ROUND_ROBIN:
                expected_pattern = ["provider1", "provider2", "provider3"] * 2
                assert selections == expected_pattern

    @pytest.mark.asyncio
    async def test_provider_performance_tracking(self):
        """Test provider performance tracking and scoring."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        query = DataQuery(asset=AssetType.STOCK)
        
        # Make multiple requests to generate performance data
        for _ in range(10):
            await router.route_query(query)
        
        # Check that performance is being tracked
        stats = router.get_provider_statistics()
        
        assert stats["total_providers"] == 2
        assert "provider1" in stats["providers"]
        assert "provider2" in stats["providers"]
        
        # Both providers should have some requests recorded
        provider1_stats = stats["providers"]["provider1"]
        provider2_stats = stats["providers"]["provider2"]
        
        total_requests = provider1_stats["total_requests"] + provider2_stats["total_requests"]
        assert total_requests == 10

    @pytest.mark.asyncio
    async def test_comprehensive_provider_suite_integration(self):
        """Test integration with comprehensive provider suite."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Use the complete test provider suite
        provider_suite = create_test_provider_suite()
        
        for name, provider in provider_suite.items():
            router.register_provider(provider)
        
        # Test various query types
        test_queries = [
            DataQuery(asset=AssetType.STOCK, market=MarketType.US),
            DataQuery(asset=AssetType.CRYPTO),
            DataQuery(asset=AssetType.BOND),
            DataQuery(asset=AssetType.STOCK, market=MarketType.CN),
            DataQuery(asset=AssetType.OPTIONS, market=MarketType.US),
        ]
        
        for query in test_queries:
            try:
                selected_provider = await router.route_query(query)
                assert selected_provider is not None
                assert selected_provider.can_handle_query(query)
            except NoAvailableProviderException:
                # Some queries might not have compatible providers
                # This is expected behavior
                pass

    @pytest.mark.asyncio
    async def test_routing_with_preferred_providers(self):
        """Test routing with preferred provider specifications."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        provider1 = MockDataProvider("preferred_provider")
        provider2 = MockDataProvider("fallback_provider")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        # Query with preferred provider
        query_with_preference = DataQuery(
            asset=AssetType.STOCK,
            provider="preferred_provider"
        )
        
        selected = await router.route_query(query_with_preference)
        assert selected == provider1
        
        # Query with non-existent preferred provider should fallback
        query_with_invalid_preference = DataQuery(
            asset=AssetType.STOCK,
            provider="non_existent_provider"
        )
        
        selected = await router.route_query(query_with_invalid_preference)
        assert selected in [provider1, provider2]

    @pytest.mark.asyncio
    async def test_routing_error_scenarios(self):
        """Test routing behavior in various error scenarios."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Test with no providers
        query = DataQuery(asset=AssetType.STOCK)
        
        with pytest.raises(NoAvailableProviderException) as exc_info:
            await router.route_query(query)
        
        assert "No available provider" in str(exc_info.value)
        
        # Test with providers that don't support the asset
        forex_provider = MockDataProvider(
            "forex_only",
            supported_assets={AssetType.FOREX}
        )
        router.register_provider(forex_provider)
        
        stock_query = DataQuery(asset=AssetType.STOCK)
        
        with pytest.raises(NoAvailableProviderException):
            await router.route_query(stock_query)

    @pytest.mark.asyncio
    async def test_concurrent_routing_with_health_checks(self):
        """Test concurrent routing requests with health monitoring."""
        import asyncio
        
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        providers = [
            MockDataProvider(f"concurrent_provider_{i}")
            for i in range(3)
        ]
        
        for provider in providers:
            router.register_provider(provider)
        
        query = DataQuery(asset=AssetType.STOCK)
        
        # Start background health monitoring
        await router.start_background_tasks()
        
        try:
            # Make concurrent routing requests
            routing_tasks = [router.route_query(query) for _ in range(20)]
            
            # Also run health checks concurrently
            health_task = router.check_all_provider_health()
            
            # Wait for all tasks
            routing_results = await asyncio.gather(*routing_tasks)
            health_results = await health_task
            
            # All routing requests should succeed
            assert len(routing_results) == 20
            assert all(provider in providers for provider in routing_results)
            
            # Health checks should complete
            assert len(health_results) == 3
            
        finally:
            # Clean up background tasks
            await router.stop_background_tasks()

    def test_router_configuration_options(self):
        """Test DataRouter with various configuration options."""
        registry = ProviderRegistry()
        
        # Test different configurations
        configs = [
            {
                "routing_strategy": RoutingStrategy.ROUND_ROBIN,
                "health_check_interval": 60,
                "max_concurrent_health_checks": 5,
                "enable_caching": True,
            },
            {
                "routing_strategy": RoutingStrategy.RANDOM,
                "health_check_interval": 300,
                "max_concurrent_health_checks": 20,
                "enable_caching": False,
            },
            {
                "routing_strategy": RoutingStrategy.WEIGHTED,
                "health_check_interval": 120,
                "max_concurrent_health_checks": 10,
                "enable_caching": True,
                "score_decay_factor": 0.8,
            },
        ]
        
        for config in configs:
            router = DataRouter(registry, **config)
            
            assert router.routing_strategy == config["routing_strategy"]
            assert router.health_check_interval == config["health_check_interval"]
            assert router.max_concurrent_health_checks == config["max_concurrent_health_checks"]
            assert router.enable_caching == config["enable_caching"]
            
            if "score_decay_factor" in config:
                assert router.score_decay_factor == config["score_decay_factor"]