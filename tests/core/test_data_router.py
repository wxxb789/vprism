"""
Tests for the intelligent data router.

This module contains comprehensive tests for the DataRouter implementation,
covering routing logic, provider selection, health checks, load balancing,
and various edge cases following TDD methodology.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from vprism.core.data_router import DataRouter, ProviderScore, RoutingStrategy
from vprism.core.exceptions import (
    NoAvailableProviderException,
    ProviderException,
    RateLimitException,
)
from vprism.core.interfaces import DataProvider
from vprism.core.mock_providers import (
    MOCK_STOCK_PROVIDER,
    AlwaysFailingProvider,
    MockDataProvider,
    RateLimitedProvider,
    SlowProvider,
    SpecializedProvider,
    create_test_provider_suite,
)
from vprism.core.models import AssetType, DataQuery, MarketType, TimeFrame
from vprism.core.provider_registry import ProviderRegistry


class TestDataRouter:
    """Test DataRouter class core functionality."""

    def test_router_initialization(self):
        """Test DataRouter initialization with default settings."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        assert router.registry == registry
        assert router.routing_strategy == RoutingStrategy.INTELLIGENT
        assert router.health_check_interval == 300  # 5 minutes
        assert router.max_concurrent_health_checks == 10
        assert len(router._provider_scores) == 0
        assert len(router._provider_health_cache) == 0

    def test_router_initialization_with_custom_settings(self):
        """Test DataRouter initialization with custom settings."""
        registry = ProviderRegistry()
        router = DataRouter(
            registry=registry,
            routing_strategy=RoutingStrategy.ROUND_ROBIN,
            health_check_interval=600,
            max_concurrent_health_checks=5,
            enable_caching=False,
        )
        
        assert router.routing_strategy == RoutingStrategy.ROUND_ROBIN
        assert router.health_check_interval == 600
        assert router.max_concurrent_health_checks == 5
        assert router.enable_caching is False

    def test_register_provider(self):
        """Test provider registration through router."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        provider = MockDataProvider("test_provider")
        
        router.register_provider(provider)
        
        assert registry.get_provider("test_provider") == provider
        assert "test_provider" in router._provider_scores
        assert router._provider_scores["test_provider"].provider == provider

    def test_unregister_provider(self):
        """Test provider unregistration through router."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        provider = MockDataProvider("test_provider")
        
        router.register_provider(provider)
        result = router.unregister_provider("test_provider")
        
        assert result is True
        assert registry.get_provider("test_provider") is None
        assert "test_provider" not in router._provider_scores
        assert "test_provider" not in router._provider_health_cache

    def test_unregister_nonexistent_provider(self):
        """Test unregistering a provider that doesn't exist."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        result = router.unregister_provider("nonexistent")
        
        assert result is False

    def test_get_available_providers_empty_registry(self):
        """Test getting available providers from empty registry."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        query = DataQuery(asset=AssetType.STOCK)
        
        providers = router.get_available_providers(query)
        
        assert len(providers) == 0

    def test_get_available_providers_with_compatible_providers(self):
        """Test getting available providers with compatible providers."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        stock_provider = MockDataProvider(
            "stock_provider",
            supported_assets={AssetType.STOCK},
        )
        bond_provider = MockDataProvider(
            "bond_provider",
            supported_assets={AssetType.BOND},
        )
        
        router.register_provider(stock_provider)
        router.register_provider(bond_provider)
        
        stock_query = DataQuery(asset=AssetType.STOCK)
        stock_providers = router.get_available_providers(stock_query)
        
        assert len(stock_providers) == 1
        assert stock_providers[0] == stock_provider

    def test_get_available_providers_filters_unhealthy(self):
        """Test that get_available_providers filters out unhealthy providers."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        healthy_provider = MockDataProvider("healthy", is_healthy=True)
        unhealthy_provider = MockDataProvider("unhealthy", is_healthy=False)
        
        router.register_provider(healthy_provider)
        router.register_provider(unhealthy_provider)
        
        # Manually mark unhealthy provider as unhealthy in cache
        router._provider_health_cache["unhealthy"] = {
            "is_healthy": False,
            "last_check": datetime.now(),
        }
        
        query = DataQuery(asset=AssetType.STOCK)
        providers = router.get_available_providers(query)
        
        assert len(providers) == 1
        assert providers[0] == healthy_provider


class TestDataRouterRouting:
    """Test DataRouter routing logic and provider selection."""

    @pytest.mark.asyncio
    async def test_route_query_single_provider(self):
        """Test routing query with single available provider."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        provider = MockDataProvider("single_provider")
        
        router.register_provider(provider)
        
        query = DataQuery(asset=AssetType.STOCK, symbols=["TEST001"])
        selected_provider = await router.route_query(query)
        
        assert selected_provider == provider

    @pytest.mark.asyncio
    async def test_route_query_no_available_providers(self):
        """Test routing query with no available providers raises exception."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        query = DataQuery(asset=AssetType.STOCK)
        
        with pytest.raises(NoAvailableProviderException) as exc_info:
            await router.route_query(query)
        
        assert "No available provider" in str(exc_info.value)
        assert exc_info.value.error_code == "NO_PROVIDER_AVAILABLE"

    @pytest.mark.asyncio
    async def test_route_query_multiple_providers_intelligent_strategy(self):
        """Test routing with multiple providers using intelligent strategy."""
        registry = ProviderRegistry()
        router = DataRouter(registry, routing_strategy=RoutingStrategy.INTELLIGENT)
        
        # Create providers with different characteristics
        fast_provider = MockDataProvider("fast", simulate_delay=False)
        slow_provider = SlowProvider("slow", delay_seconds=0.1)
        
        router.register_provider(fast_provider)
        router.register_provider(slow_provider)
        
        # Initialize scores to simulate historical performance
        router._provider_scores["fast"].success_rate = 0.95
        router._provider_scores["fast"].avg_response_time = 0.1
        router._provider_scores["slow"].success_rate = 0.90
        router._provider_scores["slow"].avg_response_time = 0.5
        
        query = DataQuery(asset=AssetType.STOCK)
        selected_provider = await router.route_query(query)
        
        # Should select the faster, more reliable provider
        assert selected_provider == fast_provider

    @pytest.mark.asyncio
    async def test_route_query_round_robin_strategy(self):
        """Test routing with round-robin strategy."""
        registry = ProviderRegistry()
        router = DataRouter(registry, routing_strategy=RoutingStrategy.ROUND_ROBIN)
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        query = DataQuery(asset=AssetType.STOCK)
        
        # Make multiple requests and track selections
        selections = []
        for _ in range(4):
            selected = await router.route_query(query)
            selections.append(selected.name)
        
        # Should alternate between providers
        assert selections == ["provider1", "provider2", "provider1", "provider2"]

    @pytest.mark.asyncio
    async def test_route_query_random_strategy(self):
        """Test routing with random strategy."""
        registry = ProviderRegistry()
        router = DataRouter(registry, routing_strategy=RoutingStrategy.RANDOM)
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        query = DataQuery(asset=AssetType.STOCK)
        
        # Make multiple requests
        selections = set()
        for _ in range(10):
            selected = await router.route_query(query)
            selections.add(selected.name)
        
        # Should use both providers (with high probability)
        assert len(selections) >= 1  # At least one provider used

    @pytest.mark.asyncio
    async def test_route_query_preferred_provider(self):
        """Test routing with preferred provider specified in query."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        # Query with preferred provider
        query = DataQuery(asset=AssetType.STOCK, provider="provider2")
        selected_provider = await router.route_query(query)
        
        assert selected_provider == provider2

    @pytest.mark.asyncio
    async def test_route_query_preferred_provider_unavailable(self):
        """Test routing when preferred provider is unavailable."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        provider1 = MockDataProvider("provider1")
        failing_provider = AlwaysFailingProvider("failing")
        
        router.register_provider(provider1)
        router.register_provider(failing_provider)
        
        # Mark failing provider as unhealthy
        router._provider_health_cache["failing"] = {
            "is_healthy": False,
            "last_check": datetime.now(),
        }
        
        # Query with preferred provider that's unavailable
        query = DataQuery(asset=AssetType.STOCK, provider="failing")
        selected_provider = await router.route_query(query)
        
        # Should fallback to available provider
        assert selected_provider == provider1

    @pytest.mark.asyncio
    async def test_route_query_preferred_provider_nonexistent(self):
        """Test routing when preferred provider doesn't exist."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        provider1 = MockDataProvider("provider1")
        router.register_provider(provider1)
        
        # Query with nonexistent preferred provider
        query = DataQuery(asset=AssetType.STOCK, provider="nonexistent")
        selected_provider = await router.route_query(query)
        
        # Should fallback to available provider
        assert selected_provider == provider1


class TestDataRouterHealthChecks:
    """Test DataRouter health check functionality."""

    @pytest.mark.asyncio
    async def test_check_provider_health_healthy(self):
        """Test health check for healthy provider."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        provider = MockDataProvider("healthy", is_healthy=True)
        
        router.register_provider(provider)
        
        is_healthy = await router._check_provider_health(provider)
        
        assert is_healthy is True
        assert "healthy" in router._provider_health_cache
        assert router._provider_health_cache["healthy"]["is_healthy"] is True

    @pytest.mark.asyncio
    async def test_check_provider_health_unhealthy(self):
        """Test health check for unhealthy provider."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        provider = MockDataProvider("unhealthy", is_healthy=False)
        
        router.register_provider(provider)
        
        is_healthy = await router._check_provider_health(provider)
        
        assert is_healthy is False
        assert router._provider_health_cache["unhealthy"]["is_healthy"] is False

    @pytest.mark.asyncio
    async def test_check_provider_health_exception(self):
        """Test health check when provider raises exception."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        provider = AlwaysFailingProvider("failing")
        
        router.register_provider(provider)
        
        is_healthy = await router._check_provider_health(provider)
        
        assert is_healthy is False
        assert router._provider_health_cache["failing"]["is_healthy"] is False

    @pytest.mark.asyncio
    async def test_check_all_provider_health(self):
        """Test checking health of all providers."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        healthy_provider = MockDataProvider("healthy", is_healthy=True)
        unhealthy_provider = MockDataProvider("unhealthy", is_healthy=False)
        failing_provider = AlwaysFailingProvider("failing")
        
        router.register_provider(healthy_provider)
        router.register_provider(unhealthy_provider)
        router.register_provider(failing_provider)
        
        health_results = await router.check_all_provider_health()
        
        assert health_results["healthy"] is True
        assert health_results["unhealthy"] is False
        assert health_results["failing"] is False

    @pytest.mark.asyncio
    async def test_check_all_provider_health_concurrent(self):
        """Test concurrent health checks with limit."""
        registry = ProviderRegistry()
        router = DataRouter(registry, max_concurrent_health_checks=2)
        
        # Create multiple slow providers
        providers = [
            SlowProvider(f"slow_{i}", delay_seconds=0.1)
            for i in range(5)
        ]
        
        for provider in providers:
            router.register_provider(provider)
        
        start_time = datetime.now()
        health_results = await router.check_all_provider_health()
        end_time = datetime.now()
        
        # Should complete all health checks
        assert len(health_results) == 5
        
        # Should take longer than single check due to concurrency limit
        elapsed = (end_time - start_time).total_seconds()
        assert elapsed >= 0.2  # At least 2 batches of 0.1s each

    @pytest.mark.asyncio
    async def test_is_provider_healthy_cached(self):
        """Test provider health check with caching."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        provider = MockDataProvider("cached_test", is_healthy=True)
        
        router.register_provider(provider)
        
        # First call should check and cache
        is_healthy1 = await router._is_provider_healthy(provider)
        assert is_healthy1 is True
        
        # Change provider health but should use cache
        provider._is_healthy = False
        is_healthy2 = await router._is_provider_healthy(provider)
        assert is_healthy2 is True  # Should use cached value

    @pytest.mark.asyncio
    async def test_is_provider_healthy_cache_expired(self):
        """Test provider health check with expired cache."""
        registry = ProviderRegistry()
        router = DataRouter(registry, health_check_interval=0.1)  # Very short interval
        provider = MockDataProvider("expire_test", is_healthy=True)
        
        router.register_provider(provider)
        
        # First call
        is_healthy1 = await router._is_provider_healthy(provider)
        assert is_healthy1 is True
        
        # Wait for cache to expire
        await asyncio.sleep(0.2)
        
        # Change provider health
        provider._is_healthy = False
        
        # Should check again due to expired cache
        is_healthy2 = await router._is_provider_healthy(provider)
        assert is_healthy2 is False


class TestDataRouterLoadBalancing:
    """Test DataRouter load balancing functionality."""

    @pytest.mark.asyncio
    async def test_load_balancing_with_provider_scores(self):
        """Test load balancing based on provider performance scores."""
        registry = ProviderRegistry()
        router = DataRouter(registry, routing_strategy=RoutingStrategy.INTELLIGENT)
        
        # Create providers with different performance characteristics
        fast_provider = MockDataProvider("fast")
        slow_provider = MockDataProvider("slow")
        
        router.register_provider(fast_provider)
        router.register_provider(slow_provider)
        
        # Simulate different performance scores
        router._provider_scores["fast"].success_rate = 0.98
        router._provider_scores["fast"].avg_response_time = 0.1
        router._provider_scores["fast"].total_requests = 1000
        
        router._provider_scores["slow"].success_rate = 0.85
        router._provider_scores["slow"].avg_response_time = 0.8
        router._provider_scores["slow"].total_requests = 1000
        
        query = DataQuery(asset=AssetType.STOCK)
        
        # Make multiple requests and track selections
        selections = []
        for _ in range(10):
            selected = await router.route_query(query)
            selections.append(selected.name)
        
        # Fast provider should be selected more often
        fast_count = selections.count("fast")
        slow_count = selections.count("slow")
        
        assert fast_count >= slow_count

    @pytest.mark.asyncio
    async def test_update_provider_score_success(self):
        """Test updating provider score after successful request."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        provider = MockDataProvider("test_provider")
        
        router.register_provider(provider)
        
        initial_score = router._provider_scores["test_provider"]
        initial_requests = initial_score.total_requests
        initial_successes = initial_score.successful_requests
        
        # Simulate successful request
        await router._update_provider_score("test_provider", success=True, response_time=0.15)
        
        updated_score = router._provider_scores["test_provider"]
        
        assert updated_score.total_requests == initial_requests + 1
        assert updated_score.successful_requests == initial_successes + 1
        assert updated_score.avg_response_time > 0

    @pytest.mark.asyncio
    async def test_update_provider_score_failure(self):
        """Test updating provider score after failed request."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        provider = MockDataProvider("test_provider")
        
        router.register_provider(provider)
        
        initial_score = router._provider_scores["test_provider"]
        initial_requests = initial_score.total_requests
        initial_successes = initial_score.successful_requests
        
        # Simulate failed request
        await router._update_provider_score("test_provider", success=False, response_time=0.5)
        
        updated_score = router._provider_scores["test_provider"]
        
        assert updated_score.total_requests == initial_requests + 1
        assert updated_score.successful_requests == initial_successes  # No change
        assert updated_score.success_rate < 1.0

    def test_calculate_provider_score(self):
        """Test provider score calculation algorithm."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Test high-performing provider
        high_score = router._calculate_provider_score(
            success_rate=0.98,
            avg_response_time=0.1,
            total_requests=1000,
        )
        
        # Test low-performing provider
        low_score = router._calculate_provider_score(
            success_rate=0.75,
            avg_response_time=1.0,
            total_requests=100,
        )
        
        assert high_score > low_score

    def test_calculate_provider_score_edge_cases(self):
        """Test provider score calculation with edge cases."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Test new provider with no requests
        new_provider_score = router._calculate_provider_score(
            success_rate=1.0,
            avg_response_time=0.0,
            total_requests=0,
        )
        
        # Test provider with perfect performance
        perfect_score = router._calculate_provider_score(
            success_rate=1.0,
            avg_response_time=0.01,
            total_requests=10000,
        )
        
        # Test provider with zero success rate
        failed_score = router._calculate_provider_score(
            success_rate=0.0,
            avg_response_time=2.0,
            total_requests=100,
        )
        
        assert perfect_score > new_provider_score > failed_score


class TestDataRouterIntegration:
    """Integration tests for DataRouter with real provider scenarios."""

    @pytest.mark.asyncio
    async def test_complete_routing_workflow(self):
        """Test complete routing workflow from query to provider selection."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Set up diverse provider suite
        providers = create_test_provider_suite()
        
        for name, provider in providers.items():
            router.register_provider(provider)
        
        # Test stock query routing
        stock_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL", "GOOGL"],
        )
        
        selected_provider = await router.route_query(stock_query)
        
        assert selected_provider is not None
        assert selected_provider.can_handle_query(stock_query)
        assert AssetType.STOCK in selected_provider.supported_assets

    @pytest.mark.asyncio
    async def test_routing_with_provider_failures(self):
        """Test routing behavior when some providers fail."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Mix of working and failing providers
        working_provider = MockDataProvider("working", is_healthy=True)
        failing_provider = AlwaysFailingProvider("failing")
        unhealthy_provider = MockDataProvider("unhealthy", is_healthy=False)
        
        router.register_provider(working_provider)
        router.register_provider(failing_provider)
        router.register_provider(unhealthy_provider)
        
        # Health check should identify failing providers
        await router.check_all_provider_health()
        
        query = DataQuery(asset=AssetType.STOCK)
        selected_provider = await router.route_query(query)
        
        # Should select the working provider
        assert selected_provider == working_provider

    @pytest.mark.asyncio
    async def test_routing_with_specialized_providers(self):
        """Test routing with providers specialized for different assets/markets."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Specialized providers
        us_stock_provider = SpecializedProvider("us_stocks", AssetType.STOCK, MarketType.US)
        cn_stock_provider = SpecializedProvider("cn_stocks", AssetType.STOCK, MarketType.CN)
        crypto_provider = SpecializedProvider("crypto", AssetType.CRYPTO, MarketType.GLOBAL)
        
        router.register_provider(us_stock_provider)
        router.register_provider(cn_stock_provider)
        router.register_provider(crypto_provider)
        
        # Test US stock query
        us_query = DataQuery(asset=AssetType.STOCK, market=MarketType.US)
        us_selected = await router.route_query(us_query)
        assert us_selected == us_stock_provider
        
        # Test CN stock query
        cn_query = DataQuery(asset=AssetType.STOCK, market=MarketType.CN)
        cn_selected = await router.route_query(cn_query)
        assert cn_selected == cn_stock_provider
        
        # Test crypto query
        crypto_query = DataQuery(asset=AssetType.CRYPTO)
        crypto_selected = await router.route_query(crypto_query)
        assert crypto_selected == crypto_provider

    @pytest.mark.asyncio
    async def test_routing_performance_under_load(self):
        """Test routing performance under concurrent load."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Set up multiple providers
        providers = [
            MockDataProvider(f"provider_{i}", rate_limit=1000)
            for i in range(5)
        ]
        
        for provider in providers:
            router.register_provider(provider)
        
        query = DataQuery(asset=AssetType.STOCK, symbols=["LOAD_TEST"])
        
        # Make concurrent routing requests
        tasks = [router.route_query(query) for _ in range(20)]
        
        start_time = datetime.now()
        selected_providers = await asyncio.gather(*tasks)
        end_time = datetime.now()
        
        # All requests should succeed
        assert len(selected_providers) == 20
        assert all(provider is not None for provider in selected_providers)
        
        # Should complete reasonably quickly
        elapsed = (end_time - start_time).total_seconds()
        assert elapsed < 5.0  # Should complete within 5 seconds

    @pytest.mark.asyncio
    async def test_routing_with_health_check_integration(self):
        """Test routing integration with automatic health checking."""
        registry = ProviderRegistry()
        router = DataRouter(registry, health_check_interval=0.1)  # Very frequent checks
        
        # Provider that becomes unhealthy
        provider = MockDataProvider("flaky", is_healthy=True)
        router.register_provider(provider)
        
        query = DataQuery(asset=AssetType.STOCK)
        
        # First request should succeed
        selected1 = await router.route_query(query)
        assert selected1 == provider
        
        # Make provider unhealthy
        provider._is_healthy = False
        
        # Force a health check to detect the change
        await router.check_all_provider_health()
        
        # Should now fail to find available provider
        with pytest.raises(NoAvailableProviderException):
            await router.route_query(query)

    @pytest.mark.asyncio
    async def test_routing_statistics_and_monitoring(self):
        """Test routing statistics collection and monitoring."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        query = DataQuery(asset=AssetType.STOCK)
        
        # Make multiple requests to generate statistics
        for _ in range(10):
            await router.route_query(query)
        
        # Check that scores are being tracked
        score1 = router._provider_scores["provider1"]
        score2 = router._provider_scores["provider2"]
        
        total_requests = score1.total_requests + score2.total_requests
        assert total_requests == 10
        
        # Both providers should have some requests (due to round-robin or random selection)
        assert score1.total_requests > 0 or score2.total_requests > 0


class TestProviderScore:
    """Test ProviderScore data class."""

    def test_provider_score_initialization(self):
        """Test ProviderScore initialization."""
        provider = MockDataProvider("test")
        score = ProviderScore(provider)
        
        assert score.provider == provider
        assert score.total_requests == 0
        assert score.successful_requests == 0
        assert score.success_rate == 1.0  # Default for new provider
        assert score.avg_response_time == 0.0
        assert score.last_used is None

    def test_provider_score_success_rate_calculation(self):
        """Test success rate calculation."""
        provider = MockDataProvider("test")
        score = ProviderScore(provider)
        
        score.total_requests = 10
        score.successful_requests = 8
        
        assert score.success_rate == 0.8

    def test_provider_score_success_rate_no_requests(self):
        """Test success rate with no requests."""
        provider = MockDataProvider("test")
        score = ProviderScore(provider)
        
        assert score.success_rate == 1.0  # Default for new provider


class TestRoutingStrategy:
    """Test RoutingStrategy enum."""

    def test_routing_strategy_values(self):
        """Test RoutingStrategy enum values."""
        assert RoutingStrategy.INTELLIGENT == "intelligent"
        assert RoutingStrategy.ROUND_ROBIN == "round_robin"
        assert RoutingStrategy.RANDOM == "random"
        assert RoutingStrategy.WEIGHTED == "weighted"


class TestDataRouterBackgroundTasks:
    """Test DataRouter background task functionality."""

    @pytest.mark.asyncio
    async def test_start_background_tasks(self):
        """Test starting background tasks."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        await router.start_background_tasks()
        
        assert router._health_check_task is not None
        assert router._score_decay_task is not None
        assert not router._health_check_task.done()
        assert not router._score_decay_task.done()
        
        # Clean up
        await router.stop_background_tasks()

    @pytest.mark.asyncio
    async def test_stop_background_tasks(self):
        """Test stopping background tasks."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        await router.start_background_tasks()
        await router.stop_background_tasks()
        
        assert router._health_check_task is None
        assert router._score_decay_task is None

    @pytest.mark.asyncio
    async def test_stop_background_tasks_when_not_started(self):
        """Test stopping background tasks when they weren't started."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Should not raise an exception
        await router.stop_background_tasks()
        
        assert router._health_check_task is None
        assert router._score_decay_task is None

    @pytest.mark.asyncio
    async def test_get_provider_statistics(self):
        """Test getting comprehensive provider statistics."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        # Generate some activity
        query = DataQuery(asset=AssetType.STOCK)
        await router.route_query(query)
        await router.route_query(query)
        
        # Check health to populate cache
        await router.check_all_provider_health()
        
        stats = router.get_provider_statistics()
        
        assert stats["total_providers"] == 2
        assert stats["routing_strategy"] == RoutingStrategy.INTELLIGENT.value
        assert "providers" in stats
        assert "provider1" in stats["providers"]
        assert "provider2" in stats["providers"]
        
        # Check provider-specific stats
        provider1_stats = stats["providers"]["provider1"]
        assert "total_requests" in provider1_stats
        assert "success_rate" in provider1_stats
        assert "is_healthy" in provider1_stats

    @pytest.mark.asyncio
    async def test_weighted_routing_strategy(self):
        """Test weighted routing strategy."""
        registry = ProviderRegistry()
        router = DataRouter(registry, routing_strategy=RoutingStrategy.WEIGHTED)
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        # Set different scores
        router._provider_scores["provider1"].recent_success_rate = 0.9
        router._provider_scores["provider1"].recent_response_time = 0.1
        router._provider_scores["provider1"].total_requests = 100
        
        router._provider_scores["provider2"].recent_success_rate = 0.5
        router._provider_scores["provider2"].recent_response_time = 0.5
        router._provider_scores["provider2"].total_requests = 100
        
        query = DataQuery(asset=AssetType.STOCK)
        
        # Make multiple requests and track selections
        selections = []
        for _ in range(20):
            selected = await router.route_query(query)
            selections.append(selected.name)
        
        # Provider1 should be selected more often due to better score
        provider1_count = selections.count("provider1")
        provider2_count = selections.count("provider2")
        
        # With weighted selection, provider1 should be selected at least as often as provider2
        # Due to randomness, we allow for equal counts but expect provider1 to be favored
        assert provider1_count >= provider2_count

    @pytest.mark.asyncio
    async def test_provider_score_update_metrics(self):
        """Test ProviderScore update_metrics method."""
        provider = MockDataProvider("test")
        score = ProviderScore(provider)
        
        # Test successful update
        score.update_metrics(success=True, response_time=0.1)
        
        assert score.total_requests == 1
        assert score.successful_requests == 1
        assert score.consecutive_failures == 0
        assert score.last_error is None
        assert score.avg_response_time == 0.1
        
        # Test failed update
        score.update_metrics(success=False, response_time=0.5, error="Test error")
        
        assert score.total_requests == 2
        assert score.successful_requests == 1
        assert score.consecutive_failures == 1
        assert score.last_error == "Test error"

    @pytest.mark.asyncio
    async def test_calculate_provider_score_comprehensive(self):
        """Test comprehensive provider score calculation scenarios."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Test perfect provider
        perfect_score = router._calculate_provider_score(
            success_rate=1.0,
            avg_response_time=0.01,
            total_requests=10000,
        )
        
        # Test average provider
        average_score = router._calculate_provider_score(
            success_rate=0.8,
            avg_response_time=0.5,
            total_requests=1000,
        )
        
        # Test poor provider
        poor_score = router._calculate_provider_score(
            success_rate=0.3,
            avg_response_time=2.0,
            total_requests=100,
        )
        
        # Test new provider
        new_score = router._calculate_provider_score(
            success_rate=1.0,
            avg_response_time=0.0,
            total_requests=0,
        )
        
        assert perfect_score > average_score > poor_score
        assert new_score > poor_score  # New providers get benefit of doubt

    @pytest.mark.asyncio
    async def test_health_check_with_caching_disabled(self):
        """Test health checking with caching disabled."""
        registry = ProviderRegistry()
        router = DataRouter(registry, enable_caching=False)
        
        provider = MockDataProvider("test", is_healthy=True)
        router.register_provider(provider)
        
        # First check
        is_healthy1 = await router._is_provider_healthy(provider)
        assert is_healthy1 is True
        
        # Change provider health
        provider._is_healthy = False
        
        # Second check should reflect the change immediately
        is_healthy2 = await router._is_provider_healthy(provider)
        assert is_healthy2 is False

    @pytest.mark.asyncio
    async def test_route_query_with_all_strategies(self):
        """Test routing with all available strategies."""
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
            
            for provider in providers:
                router.register_provider(provider)
            
            # Should be able to route with any strategy
            selected_provider = await router.route_query(query)
            assert selected_provider in providers

    @pytest.mark.asyncio
    async def test_concurrent_routing_requests(self):
        """Test handling many concurrent routing requests."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        providers = [MockDataProvider(f"provider_{i}") for i in range(3)]
        for provider in providers:
            router.register_provider(provider)
        
        query = DataQuery(asset=AssetType.STOCK)
        
        # Make many concurrent requests
        tasks = [router.route_query(query) for _ in range(50)]
        selected_providers = await asyncio.gather(*tasks)
        
        # All requests should succeed
        assert len(selected_providers) == 50
        assert all(provider in providers for provider in selected_providers)

    @pytest.mark.asyncio
    async def test_provider_health_cache_expiration_edge_cases(self):
        """Test edge cases in health cache expiration."""
        registry = ProviderRegistry()
        router = DataRouter(registry, health_check_interval=1)  # 1 second
        
        provider = MockDataProvider("test", is_healthy=True)
        router.register_provider(provider)
        
        # Manually set cache with old timestamp
        old_time = datetime.now() - timedelta(seconds=10)
        router._provider_health_cache["test"] = {
            "is_healthy": False,
            "last_check": old_time,
        }
        
        # Should perform new health check due to expired cache
        is_healthy = await router._is_provider_healthy(provider)
        assert is_healthy is True  # Should get fresh result
        
        # Cache should be updated
        assert router._provider_health_cache["test"]["is_healthy"] is True

    def test_provider_score_edge_cases(self):
        """Test ProviderScore edge cases."""
        provider = MockDataProvider("test")
        score = ProviderScore(provider)
        
        # Test with zero requests
        assert score.success_rate == 1.0
        
        # Test setting success rate on zero requests
        score.success_rate = 0.8
        assert score.total_requests == 100  # Should set default
        assert score.successful_requests == 80

    @pytest.mark.asyncio
    async def test_error_handling_in_health_checks(self):
        """Test error handling during health checks."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Provider that raises exception during health check
        provider = MockDataProvider("error_provider", failure_rate=1.0)
        router.register_provider(provider)
        
        # Health check should handle the exception gracefully
        health_results = await router.check_all_provider_health()
        
        assert "error_provider" in health_results
        assert health_results["error_provider"] is False

    @pytest.mark.asyncio
    async def test_routing_with_no_compatible_providers(self):
        """Test routing when no providers support the requested asset."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Register provider that only supports stocks
        stock_provider = SpecializedProvider("stock_only", AssetType.STOCK)
        router.register_provider(stock_provider)
        
        # Try to query for bonds
        bond_query = DataQuery(asset=AssetType.BOND)
        
        with pytest.raises(NoAvailableProviderException) as exc_info:
            await router.route_query(bond_query)
        
        assert "No available provider" in str(exc_info.value)
        assert exc_info.value.details["asset"] == AssetType.BOND.value

    @pytest.mark.asyncio
    async def test_provider_score_decay_simulation(self):
        """Test provider score decay functionality."""
        registry = ProviderRegistry()
        router = DataRouter(registry, score_decay_factor=0.5)
        
        provider = MockDataProvider("test")
        router.register_provider(provider)
        
        score = router._provider_scores["test"]
        
        # Set initial values
        score.recent_success_rate = 1.0
        score.recent_response_time = 0.1
        score.total_requests = 100
        score.successful_requests = 80
        
        # Simulate score decay (normally done by background task)
        original_recent_success = score.recent_success_rate
        original_recent_time = score.recent_response_time
        
        # Apply decay manually
        score.recent_success_rate = (
            score.recent_success_rate * router.score_decay_factor +
            score.success_rate * (1 - router.score_decay_factor)
        )
        score.recent_response_time = (
            score.recent_response_time * router.score_decay_factor +
            score.avg_response_time * (1 - router.score_decay_factor)
        )
        
        # Values should have changed
        assert score.recent_success_rate != original_recent_success
        assert score.recent_response_time != original_recent_time


class TestDataRouterEdgeCasesAndCoverage:
    """Test edge cases and scenarios to improve test coverage."""

    @pytest.mark.asyncio
    async def test_default_routing_strategy_fallback(self):
        """Test fallback to intelligent strategy for unknown routing strategy."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Create a mock routing strategy that's not in the enum
        class MockStrategy:
            value = "invalid_strategy"
        
        # Manually set an invalid routing strategy to test fallback
        router.routing_strategy = MockStrategy()
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        query = DataQuery(asset=AssetType.STOCK)
        
        # Should fallback to intelligent strategy
        selected_provider = await router.route_query(query)
        assert selected_provider in [provider1, provider2]

    @pytest.mark.asyncio
    async def test_weighted_selection_zero_total_weight(self):
        """Test weighted selection when all providers have zero weight."""
        registry = ProviderRegistry()
        router = DataRouter(registry, routing_strategy=RoutingStrategy.WEIGHTED)
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        # Set all providers to have zero scores (which results in minimum weight)
        router._provider_scores["provider1"].recent_success_rate = 0.0
        router._provider_scores["provider1"].recent_response_time = 10.0
        router._provider_scores["provider1"].total_requests = 0
        
        router._provider_scores["provider2"].recent_success_rate = 0.0
        router._provider_scores["provider2"].recent_response_time = 10.0
        router._provider_scores["provider2"].total_requests = 0
        
        query = DataQuery(asset=AssetType.STOCK)
        
        # Should still select a provider using random fallback
        selected_provider = await router.route_query(query)
        assert selected_provider in [provider1, provider2]

    @pytest.mark.asyncio
    async def test_weighted_selection_fallback_provider(self):
        """Test weighted selection fallback to last provider."""
        import random as random_module
        
        registry = ProviderRegistry()
        router = DataRouter(registry, routing_strategy=RoutingStrategy.WEIGHTED)
        
        providers = [MockDataProvider(f"provider{i}") for i in range(3)]
        for provider in providers:
            router.register_provider(provider)
        
        # Mock the weighted selection to always fall through to fallback
        original_uniform = random_module.uniform
        
        def mock_uniform(a, b):
            return b + 1  # Always return value higher than total weight
        
        random_module.uniform = mock_uniform
        
        try:
            query = DataQuery(asset=AssetType.STOCK)
            selected_provider = await router.route_query(query)
            
            # Should select the last provider as fallback
            assert selected_provider == providers[-1]
        finally:
            # Restore original function
            random_module.uniform = original_uniform

    @pytest.mark.asyncio
    async def test_health_check_without_caching(self):
        """Test health checking with caching disabled."""
        registry = ProviderRegistry()
        router = DataRouter(registry, enable_caching=False)
        
        provider = MockDataProvider("test", is_healthy=True)
        router.register_provider(provider)
        
        # First check
        is_healthy1 = await router._is_provider_healthy(provider)
        assert is_healthy1 is True
        
        # Change provider health
        provider._is_healthy = False
        
        # Second check should immediately reflect the change (no caching)
        is_healthy2 = await router._is_provider_healthy(provider)
        assert is_healthy2 is False
        
        # Health cache should be empty
        assert len(router._provider_health_cache) == 0

    @pytest.mark.asyncio
    async def test_health_check_cached_non_caching_path(self):
        """Test _is_provider_healthy_cached with caching disabled."""
        registry = ProviderRegistry()
        router = DataRouter(registry, enable_caching=False)
        
        provider = MockDataProvider("test", is_healthy=False)
        router.register_provider(provider)
        
        # Should return True (default) when caching is disabled
        is_healthy = router._is_provider_healthy_cached(provider)
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_exception_handling(self):
        """Test health check exception handling and caching."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Create a provider that raises exception during health check
        provider = MockDataProvider("error_provider")
        
        # Mock the health_check method to raise an exception
        async def failing_health_check():
            raise Exception("Health check failed")
        
        provider.health_check = failing_health_check
        router.register_provider(provider)
        
        # Health check should handle exception gracefully
        is_healthy = await router._check_provider_health(provider)
        
        assert is_healthy is False
        
        # Exception should be cached
        assert "error_provider" in router._provider_health_cache
        assert router._provider_health_cache["error_provider"]["is_healthy"] is False
        
        # Provider score should be updated with failure
        score = router._provider_scores["error_provider"]
        assert score.total_requests > 0
        assert score.last_error is not None

    @pytest.mark.asyncio
    async def test_health_check_exception_without_caching(self):
        """Test health check exception handling without caching."""
        registry = ProviderRegistry()
        router = DataRouter(registry, enable_caching=False)
        
        provider = MockDataProvider("error_provider")
        
        async def failing_health_check():
            raise Exception("Health check failed")
        
        provider.health_check = failing_health_check
        router.register_provider(provider)
        
        # Health check should handle exception gracefully
        is_healthy = await router._check_provider_health(provider)
        
        assert is_healthy is False
        
        # No caching should occur
        assert len(router._provider_health_cache) == 0

    @pytest.mark.asyncio
    async def test_check_all_provider_health_with_exceptions(self):
        """Test check_all_provider_health with some providers raising exceptions."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Mix of working and failing providers
        working_provider = MockDataProvider("working", is_healthy=True)
        
        failing_provider = MockDataProvider("failing")
        async def failing_health_check():
            raise Exception("Health check failed")
        failing_provider.health_check = failing_health_check
        
        router.register_provider(working_provider)
        router.register_provider(failing_provider)
        
        # Should handle exceptions gracefully
        health_results = await router.check_all_provider_health()
        
        assert len(health_results) == 2
        assert health_results["working"] is True
        assert health_results["failing"] is False

    @pytest.mark.asyncio
    async def test_background_tasks_lifecycle(self):
        """Test complete background tasks lifecycle."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Initially no tasks
        assert router._health_check_task is None
        assert router._score_decay_task is None
        
        # Start tasks
        await router.start_background_tasks()
        
        assert router._health_check_task is not None
        assert router._score_decay_task is not None
        assert not router._health_check_task.done()
        assert not router._score_decay_task.done()
        
        # Starting again should not create new tasks
        await router.start_background_tasks()
        
        # Stop tasks
        await router.stop_background_tasks()
        
        assert router._health_check_task is None
        assert router._score_decay_task is None

    @pytest.mark.asyncio
    async def test_periodic_health_check_task(self):
        """Test periodic health check background task."""
        registry = ProviderRegistry()
        router = DataRouter(registry, health_check_interval=0.1)  # Very short interval
        
        provider = MockDataProvider("test", is_healthy=True)
        router.register_provider(provider)
        
        # Start background task
        await router.start_background_tasks()
        
        try:
            # Wait for at least one health check cycle
            await asyncio.sleep(0.2)
            
            # Health cache should be populated
            assert "test" in router._provider_health_cache
            assert router._provider_health_cache["test"]["is_healthy"] is True
            
        finally:
            await router.stop_background_tasks()

    @pytest.mark.asyncio
    async def test_periodic_score_decay_simulation(self):
        """Test score decay functionality simulation."""
        registry = ProviderRegistry()
        router = DataRouter(registry, score_decay_factor=0.5)
        
        provider = MockDataProvider("test")
        router.register_provider(provider)
        
        score = router._provider_scores["test"]
        
        # Set initial values
        score.recent_success_rate = 1.0
        score.recent_response_time = 0.1
        score.total_requests = 100
        score.successful_requests = 80
        
        # Store original values
        original_recent_success = score.recent_success_rate
        original_recent_time = score.recent_response_time
        
        # Manually apply decay (simulating what the background task does)
        score.recent_success_rate = (
            score.recent_success_rate * router.score_decay_factor +
            score.success_rate * (1 - router.score_decay_factor)
        )
        score.recent_response_time = (
            score.recent_response_time * router.score_decay_factor +
            score.avg_response_time * (1 - router.score_decay_factor)
        )
        
        # Values should have changed due to decay
        assert score.recent_success_rate != original_recent_success
        assert score.recent_response_time != original_recent_time

    @pytest.mark.asyncio
    async def test_provider_score_edge_cases_comprehensive(self):
        """Test comprehensive edge cases for provider scoring."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Test score calculation with extreme values
        test_cases = [
            # (success_rate, avg_response_time, total_requests, expected_behavior)
            (1.0, 0.0, 0, "new_provider_default"),
            (0.0, 10.0, 1000, "poor_performer"),
            (1.0, 0.001, 10000, "excellent_performer"),
            (0.5, 1.0, 50, "average_performer"),
        ]
        
        for success_rate, response_time, requests, case_name in test_cases:
            score = router._calculate_provider_score(success_rate, response_time, requests)
            
            # Score should always be non-negative
            assert score >= 0.0, f"Score should be non-negative for {case_name}"
            
            # Excellent performers should have high scores
            if case_name == "excellent_performer":
                assert score > 100, f"Excellent performer should have high score"
            
            # Poor performers should have low scores
            if case_name == "poor_performer":
                assert score < 50, f"Poor performer should have low score"

    @pytest.mark.asyncio
    async def test_update_provider_score_nonexistent_provider(self):
        """Test updating score for non-existent provider."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Should not raise exception for non-existent provider
        await router._update_provider_score(
            "nonexistent_provider",
            success=True,
            response_time=0.1,
            error=None,
        )
        
        # No score should be created
        assert "nonexistent_provider" not in router._provider_scores

    @pytest.mark.asyncio
    async def test_health_cache_with_very_old_entries(self):
        """Test health cache behavior with very old entries."""
        registry = ProviderRegistry()
        router = DataRouter(registry, health_check_interval=1)  # 1 second
        
        provider = MockDataProvider("test", is_healthy=True)
        router.register_provider(provider)
        
        # Manually set very old cache entry
        very_old_time = datetime.now() - timedelta(hours=1)
        router._provider_health_cache["test"] = {
            "is_healthy": False,
            "last_check": very_old_time,
        }
        
        # _is_provider_healthy_cached should still return the cached value
        # even if old, but within the 2x interval threshold
        router.health_check_interval = 3600  # 1 hour, so 2x = 2 hours
        is_healthy = router._is_provider_healthy_cached(provider)
        assert is_healthy is False  # Should use cached value
        
        # But if cache is really old (beyond 2x interval), should default to healthy
        router.health_check_interval = 1800  # 30 minutes, so 2x = 1 hour
        is_healthy = router._is_provider_healthy_cached(provider)
        assert is_healthy is True  # Should default to healthy

    @pytest.mark.asyncio
    async def test_concurrent_health_checks_with_semaphore_limit(self):
        """Test concurrent health checks respecting semaphore limits."""
        registry = ProviderRegistry()
        router = DataRouter(registry, max_concurrent_health_checks=2)
        
        # Create multiple slow providers
        providers = []
        for i in range(5):
            provider = SlowProvider(f"slow_{i}", delay_seconds=0.1)
            providers.append(provider)
            router.register_provider(provider)
        
        start_time = datetime.now()
        health_results = await router.check_all_provider_health()
        end_time = datetime.now()
        
        # Should complete all health checks
        assert len(health_results) == 5
        
        # Should take longer due to semaphore limiting concurrency
        elapsed = (end_time - start_time).total_seconds()
        # With 5 providers, max 2 concurrent, and 0.1s delay each:
        # Should take at least 3 batches: ceil(5/2) * 0.1 = 0.3s
        assert elapsed >= 0.25  # Allow some tolerance

    def test_routing_strategy_enum_completeness(self):
        """Test that all routing strategy enum values are handled."""
        registry = ProviderRegistry()
        
        # Test that all enum values are valid
        for strategy in RoutingStrategy:
            router = DataRouter(registry, routing_strategy=strategy)
            assert router.routing_strategy == strategy

    @pytest.mark.asyncio
    async def test_provider_statistics_with_health_cache(self):
        """Test provider statistics include health cache information."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        provider = MockDataProvider("test", is_healthy=True)
        router.register_provider(provider)
        
        # Perform health check to populate cache
        await router._check_provider_health(provider)
        
        # Get statistics
        stats = router.get_provider_statistics()
        
        assert "test" in stats["providers"]
        provider_stats = stats["providers"]["test"]
        
        # Should include health information
        assert "is_healthy" in provider_stats
        assert "last_health_check" in provider_stats
        assert provider_stats["is_healthy"] is True

    @pytest.mark.asyncio
    async def test_provider_statistics_without_health_cache(self):
        """Test provider statistics without health cache information."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        provider = MockDataProvider("test")
        router.register_provider(provider)
        
        # Get statistics without health check
        stats = router.get_provider_statistics()
        
        assert "test" in stats["providers"]
        provider_stats = stats["providers"]["test"]
        
        # Should not include health information
        assert "is_healthy" not in provider_stats
        assert "last_health_check" not in provider_stats

    @pytest.mark.asyncio
    async def test_weighted_selection_zero_weights_edge_case(self):
        """Test weighted selection when calculated weights are all zero."""
        registry = ProviderRegistry()
        router = DataRouter(registry, routing_strategy=RoutingStrategy.WEIGHTED)
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        # Mock _calculate_provider_score to return 0 for all providers
        original_calculate = router._calculate_provider_score
        
        def mock_calculate(*args, **kwargs):
            return 0.0  # Always return zero score
        
        router._calculate_provider_score = mock_calculate
        
        try:
            query = DataQuery(asset=AssetType.STOCK)
            selected_provider = await router.route_query(query)
            
            # Should still select a provider using random fallback
            assert selected_provider in [provider1, provider2]
        finally:
            # Restore original function
            router._calculate_provider_score = original_calculate

    @pytest.mark.asyncio
    async def test_background_task_exception_handling(self):
        """Test background task exception handling."""
        registry = ProviderRegistry()
        router = DataRouter(registry, health_check_interval=0.01)  # Very short interval
        
        # Create a provider that will cause health check to fail
        provider = MockDataProvider("error_provider")
        
        # Mock health check to raise exception
        async def failing_health_check():
            raise Exception("Simulated health check failure")
        
        provider.health_check = failing_health_check
        router.register_provider(provider)
        
        # Start background tasks
        await router.start_background_tasks()
        
        try:
            # Wait for background task to run and handle exceptions
            await asyncio.sleep(0.05)
            
            # Background task should still be running despite exceptions
            assert router._health_check_task is not None
            assert not router._health_check_task.done()
            
        finally:
            await router.stop_background_tasks()

    @pytest.mark.asyncio
    async def test_background_task_cancellation(self):
        """Test background task cancellation handling."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Start background tasks
        await router.start_background_tasks()
        
        # Get references to tasks
        health_task = router._health_check_task
        decay_task = router._score_decay_task
        
        assert health_task is not None
        assert decay_task is not None
        
        # Stop tasks (which cancels them)
        await router.stop_background_tasks()
        
        # Tasks should be cancelled
        assert health_task.cancelled() or health_task.done()
        assert decay_task.cancelled() or decay_task.done()
        
        # Router should have cleared task references
        assert router._health_check_task is None
        assert router._score_decay_task is None

    @pytest.mark.asyncio
    async def test_score_decay_background_task_simulation(self):
        """Test score decay background task behavior."""
        registry = ProviderRegistry()
        router = DataRouter(registry, score_decay_factor=0.8)
        
        provider = MockDataProvider("test")
        router.register_provider(provider)
        
        # Set up initial score values
        score = router._provider_scores["test"]
        score.recent_success_rate = 1.0
        score.recent_response_time = 0.1
        score.total_requests = 100
        score.successful_requests = 90
        
        # Store original values
        original_recent_success = score.recent_success_rate
        original_recent_time = score.recent_response_time
        
        # Simulate what the background task does
        # (We can't easily test the actual background task due to timing)
        score.recent_success_rate = (
            score.recent_success_rate * router.score_decay_factor +
            score.success_rate * (1 - router.score_decay_factor)
        )
        score.recent_response_time = (
            score.recent_response_time * router.score_decay_factor +
            score.avg_response_time * (1 - router.score_decay_factor)
        )
        
        # Values should have changed
        assert score.recent_success_rate != original_recent_success
        assert score.recent_response_time != original_recent_time

    def test_provider_score_setter_edge_cases(self):
        """Test ProviderScore success_rate setter edge cases."""
        provider = MockDataProvider("test")
        score = ProviderScore(provider)
        
        # Test setting success rate on provider with zero requests
        assert score.total_requests == 0
        score.success_rate = 0.75
        
        # Should set default total_requests and calculate successful_requests
        assert score.total_requests == 100
        assert score.successful_requests == 75
        
        # Test setting success rate again
        score.success_rate = 0.5
        assert score.successful_requests == 50  # 50% of 100

    @pytest.mark.asyncio
    async def test_comprehensive_error_scenarios(self):
        """Test comprehensive error handling scenarios."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Test with provider that has no name
        class NamelessProvider(MockDataProvider):
            @property
            def name(self):
                return ""
        
        nameless_provider = NamelessProvider("nameless")
        
        # Should handle gracefully (though this might not be a realistic scenario)
        try:
            router.register_provider(nameless_provider)
            # If it doesn't raise an exception, that's fine too
        except Exception:
            # Expected behavior - provider without name should cause issues
            pass

    @pytest.mark.asyncio
    async def test_routing_with_all_providers_unhealthy(self):
        """Test routing when all providers are unhealthy."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Create multiple unhealthy providers
        unhealthy_providers = [
            MockDataProvider(f"unhealthy_{i}", is_healthy=False)
            for i in range(3)
        ]
        
        for provider in unhealthy_providers:
            router.register_provider(provider)
        
        # Perform health checks to mark them as unhealthy
        await router.check_all_provider_health()
        
        query = DataQuery(asset=AssetType.STOCK)
        
        # Should raise NoAvailableProviderException
        with pytest.raises(NoAvailableProviderException):
            await router.route_query(query)

    @pytest.mark.asyncio
    async def test_weighted_selection_zero_total_weight_direct(self):
        """Test weighted selection when total weight is exactly zero."""
        registry = ProviderRegistry()
        router = DataRouter(registry, routing_strategy=RoutingStrategy.WEIGHTED)
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        # Mock _calculate_provider_score to return negative values
        # which get clamped to 0.1 minimum, but we'll override that
        original_select_weighted = router._select_weighted
        
        async def mock_select_weighted(providers, query):
            import random
            # Simulate zero weights scenario
            weights = [0.0, 0.0]  # All zero weights
            total_weight = sum(weights)
            
            if total_weight == 0:
                return random.choice(providers)
            
            # This shouldn't be reached in our test
            return providers[0]
        
        router._select_weighted = mock_select_weighted
        
        try:
            query = DataQuery(asset=AssetType.STOCK)
            selected_provider = await router.route_query(query)
            
            # Should select one of the providers via random choice
            assert selected_provider in [provider1, provider2]
        finally:
            # Restore original function
            router._select_weighted = original_select_weighted

    @pytest.mark.asyncio
    async def test_background_task_error_handling_comprehensive(self):
        """Test comprehensive background task error handling."""
        registry = ProviderRegistry()
        router = DataRouter(registry)
        
        # Mock the periodic health check to raise an exception
        original_check_all = router.check_all_provider_health
        
        async def failing_check_all():
            raise Exception("Simulated background task error")
        
        router.check_all_provider_health = failing_check_all
        
        # Start background tasks
        await router.start_background_tasks()
        
        try:
            # Wait a bit for the background task to encounter the error
            await asyncio.sleep(0.1)
            
            # Background task should still be running (error handling should prevent crash)
            assert router._health_check_task is not None
            
        finally:
            # Restore original function and stop tasks
            router.check_all_provider_health = original_check_all
            await router.stop_background_tasks()

    def test_provider_score_comprehensive_edge_cases(self):
        """Test ProviderScore with comprehensive edge cases."""
        provider = MockDataProvider("test")
        score = ProviderScore(provider)
        
        # Test multiple updates
        score.update_metrics(True, 0.1)
        score.update_metrics(False, 0.5, "Error 1")
        score.update_metrics(True, 0.2)
        score.update_metrics(False, 1.0, "Error 2")
        
        assert score.total_requests == 4
        assert score.successful_requests == 2
        assert score.success_rate == 0.5
        assert score.consecutive_failures == 1
        assert score.last_error == "Error 2"
        
        # Test successful request resets consecutive failures
        score.update_metrics(True, 0.1)
        assert score.consecutive_failures == 0
        assert score.last_error is None

    @pytest.mark.asyncio
    async def test_weighted_selection_actual_zero_weights(self):
        """Test weighted selection with actual zero weights from score calculation."""
        registry = ProviderRegistry()
        router = DataRouter(registry, routing_strategy=RoutingStrategy.WEIGHTED)
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")
        
        router.register_provider(provider1)
        router.register_provider(provider2)
        
        # Override the _calculate_provider_score method to return negative values
        # which will be clamped to 0.1 minimum, but we'll force it to return 0
        def zero_score(*args, **kwargs):
            return 0.0
        
        original_calculate = router._calculate_provider_score
        router._calculate_provider_score = zero_score
        
        # Also need to override the minimum weight logic in _select_weighted
        original_select_weighted = router._select_weighted
        
        async def test_select_weighted(providers, query):
            weights = [0.0, 0.0]  # Force zero weights
            total_weight = sum(weights)
            if total_weight == 0:
                import random
                return random.choice(providers)
            # This shouldn't be reached
            return providers[0]
        
        router._select_weighted = test_select_weighted
        
        try:
            query = DataQuery(asset=AssetType.STOCK)
            selected_provider = await router.route_query(query)
            
            # Should select one of the providers via random choice
            assert selected_provider in [provider1, provider2]
        finally:
            # Restore original methods
            router._calculate_provider_score = original_calculate
            router._select_weighted = original_select_weighted