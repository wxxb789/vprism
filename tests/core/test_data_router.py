"""
Tests for intelligent data router.

This module contains comprehensive tests for the data routing logic,
following TDD principles with 100% coverage target.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from vprism.core.data_router import IntelligentDataRouter
from vprism.core.exceptions import NoAvailableProviderException
from vprism.core.interfaces import DataProvider
from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    MarketType,
    ProviderInfo,
)
from vprism.core.provider_registry import ProviderRegistry


class MockDataProvider(DataProvider):
    """Mock data provider for testing."""

    def __init__(
        self,
        name: str,
        supported_assets: set[AssetType] | None = None,
        can_handle: bool = True,
        is_healthy: bool = True,
        response_delay: float = 0.1,
    ):
        self._name = name
        self._supported_assets = supported_assets or {AssetType.STOCK}
        self._can_handle = can_handle
        self._is_healthy = is_healthy
        self._response_delay = response_delay
        self._info = ProviderInfo(
            name=name,
            version="1.0.0",
            url=f"https://api.{name}.com",
            rate_limit=1000,
            cost="free",
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def info(self) -> ProviderInfo:
        return self._info

    @property
    def supported_assets(self) -> set[AssetType]:
        return self._supported_assets

    async def get_data(self, query: DataQuery) -> DataResponse:
        await asyncio.sleep(self._response_delay)
        return MagicMock(spec=DataResponse)

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        yield MagicMock(spec=DataPoint)

    async def health_check(self) -> bool:
        return self._is_healthy

    def can_handle_query(self, query: DataQuery) -> bool:
        return self._can_handle and query.asset in self._supported_assets


class TestIntelligentDataRouter:
    """Test IntelligentDataRouter class."""

    def test_router_initialization(self):
        """Test router initialization."""
        router = IntelligentDataRouter()
        
        assert router._registry is not None
        assert router._provider_metrics == {}
        assert router._health_check_interval == 300
        assert router._circuit_breaker_threshold == 5

    def test_router_initialization_with_registry(self):
        """Test router initialization with custom registry."""
        registry = ProviderRegistry()
        router = IntelligentDataRouter(registry)
        
        assert router._registry is registry

    def test_register_provider(self):
        """Test provider registration."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)

        assert router._registry.get_provider("test_provider") == provider
        assert "test_provider" in router._provider_metrics

    def test_unregister_provider(self):
        """Test provider unregistration."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)
        assert "test_provider" in router._provider_metrics

        result = router.unregister_provider("test_provider")

        assert result is True
        assert router._registry.get_provider("test_provider") is None
        assert "test_provider" not in router._provider_metrics

    def test_unregister_nonexistent_provider(self):
        """Test unregistering non-existent provider."""
        router = IntelligentDataRouter()

        result = router.unregister_provider("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_route_query_single_provider(self):
        """Test routing query with single compatible provider."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider", {AssetType.STOCK})

        router.register_provider(provider)

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US)
        selected_provider = await router.route_query(query)

        assert selected_provider == provider

    @pytest.mark.asyncio
    async def test_route_query_multiple_providers(self):
        """Test routing query with multiple compatible providers."""
        router = IntelligentDataRouter()
        
        provider1 = MockDataProvider("provider1", {AssetType.STOCK})
        provider2 = MockDataProvider("provider2", {AssetType.STOCK})

        router.register_provider(provider1)
        router.register_provider(provider2)

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US)
        selected_provider = await router.route_query(query)

        # Should select one of the providers
        assert selected_provider in [provider1, provider2]

    @pytest.mark.asyncio
    async def test_route_query_no_compatible_providers(self):
        """Test routing query with no compatible providers."""
        router = IntelligentDataRouter()
        
        # Provider only supports bonds
        provider = MockDataProvider("bond_provider", {AssetType.BOND})
        router.register_provider(provider)

        # Query for stocks
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US)

        with pytest.raises(NoAvailableProviderException) as exc_info:
            await router.route_query(query)

        assert "No compatible providers found" in str(exc_info.value)
        assert exc_info.value.error_code == "NO_PROVIDER_AVAILABLE"

    @pytest.mark.asyncio
    async def test_route_query_unhealthy_providers(self):
        """Test routing query with unhealthy providers."""
        router = IntelligentDataRouter()
        
        # Unhealthy provider
        unhealthy_provider = MockDataProvider("unhealthy", {AssetType.STOCK}, is_healthy=False)
        router.register_provider(unhealthy_provider)

        # Mark as unhealthy in registry
        router._registry.update_provider_health("unhealthy", False)

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US)

        with pytest.raises(NoAvailableProviderException) as exc_info:
            await router.route_query(query)

        assert "No compatible providers found" in str(exc_info.value)



    @pytest.mark.asyncio
    async def test_route_query_circuit_breaker(self):
        """Test routing query with circuit breaker logic."""
        router = IntelligentDataRouter()
        
        provider1 = MockDataProvider("provider1", {AssetType.STOCK})
        provider2 = MockDataProvider("provider2", {AssetType.STOCK})

        router.register_provider(provider1)
        router.register_provider(provider2)

        # Trigger circuit breaker for provider1
        for _ in range(router._circuit_breaker_threshold):
            router.record_provider_failure("provider1", Exception("Test failure"))

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US)
        selected_provider = await router.route_query(query)

        # Should select provider2 since provider1 is in circuit breaker state
        assert selected_provider == provider2

    @pytest.mark.asyncio
    async def test_route_query_all_circuit_breaker(self):
        """Test routing query when all providers are in circuit breaker state."""
        router = IntelligentDataRouter()
        
        provider1 = MockDataProvider("provider1", {AssetType.STOCK})
        provider2 = MockDataProvider("provider2", {AssetType.STOCK})

        router.register_provider(provider1)
        router.register_provider(provider2)

        # Trigger circuit breaker for both providers
        for _ in range(router._circuit_breaker_threshold):
            router.record_provider_failure("provider1", Exception("Test failure"))
            router.record_provider_failure("provider2", Exception("Test failure"))

        # Make provider1 fail earlier
        router._circuit_breaker_last_failure["provider1"] = time.time() - 10
        router._circuit_breaker_last_failure["provider2"] = time.time() - 5

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US)
        selected_provider = await router.route_query(query)

        # Should select provider1 (oldest failure)
        assert selected_provider == provider1

    def test_get_available_providers(self):
        """Test getting available providers for a query."""
        router = IntelligentDataRouter()
        
        stock_provider = MockDataProvider("stock", {AssetType.STOCK})
        bond_provider = MockDataProvider("bond", {AssetType.BOND})

        router.register_provider(stock_provider)
        router.register_provider(bond_provider)

        stock_query = DataQuery(asset=AssetType.STOCK)
        available_providers = router.get_available_providers(stock_query)

        assert len(available_providers) == 1
        assert available_providers[0] == stock_provider

    def test_record_provider_success(self):
        """Test recording provider success."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)
        router.record_provider_success("test_provider", 0.5)

        metrics = router.get_provider_metrics("test_provider")
        assert metrics["total_requests"] == 1
        assert metrics["successful_requests"] == 1
        assert metrics["total_response_time"] == 0.5
        assert metrics["average_response_time"] == 0.5
        assert metrics["last_success_time"] > 0

    def test_record_provider_success_unregistered(self):
        """Test recording success for unregistered provider initializes metrics."""
        router = IntelligentDataRouter()

        # Record success for provider that wasn't registered
        router.record_provider_success("unregistered", 0.3)

        metrics = router.get_provider_metrics("unregistered")
        assert metrics["total_requests"] == 1
        assert metrics["successful_requests"] == 1

    def test_record_provider_failure(self):
        """Test recording provider failure."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)
        router.record_provider_failure("test_provider", Exception("Test error"))

        metrics = router.get_provider_metrics("test_provider")
        assert metrics["total_requests"] == 1
        assert metrics["failed_requests"] == 1
        assert metrics["failure_rate"] == 1.0
        assert metrics["last_failure_time"] > 0

    def test_record_provider_failure_unregistered(self):
        """Test recording failure for unregistered provider initializes metrics."""
        router = IntelligentDataRouter()

        # Record failure for provider that wasn't registered
        router.record_provider_failure("unregistered", Exception("Test"))

        metrics = router.get_provider_metrics("unregistered")
        assert metrics["total_requests"] == 1
        assert metrics["failed_requests"] == 1

    def test_record_multiple_requests(self):
        """Test recording multiple requests for metrics calculation."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)

        # Record successes and failures
        router.record_provider_success("test_provider", 0.3)
        router.record_provider_success("test_provider", 0.7)
        router.record_provider_failure("test_provider", Exception("Test error"))

        metrics = router.get_provider_metrics("test_provider")
        assert metrics["total_requests"] == 3
        assert metrics["successful_requests"] == 2
        assert metrics["failed_requests"] == 1
        assert metrics["failure_rate"] == 1/3
        assert metrics["average_response_time"] == 0.5  # (0.3 + 0.7) / 2

    def test_get_provider_metrics_nonexistent(self):
        """Test getting metrics for non-existent provider."""
        router = IntelligentDataRouter()

        metrics = router.get_provider_metrics("nonexistent")

        assert metrics == {}

    def test_get_all_provider_metrics(self):
        """Test getting all provider metrics."""
        router = IntelligentDataRouter()
        
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")

        router.register_provider(provider1)
        router.register_provider(provider2)

        router.record_provider_success("provider1", 0.5)
        router.record_provider_failure("provider2", Exception("Test"))

        all_metrics = router.get_all_provider_metrics()

        assert "provider1" in all_metrics
        assert "provider2" in all_metrics
        assert all_metrics["provider1"]["successful_requests"] == 1
        assert all_metrics["provider2"]["failed_requests"] == 1

    def test_reset_provider_metrics(self):
        """Test resetting provider metrics."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)
        router.record_provider_success("test_provider", 0.5)

        # Verify metrics exist
        metrics = router.get_provider_metrics("test_provider")
        assert metrics["successful_requests"] == 1

        # Reset metrics
        router.reset_provider_metrics("test_provider")

        # Verify metrics are reset
        metrics = router.get_provider_metrics("test_provider")
        assert metrics["successful_requests"] == 0
        assert metrics["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_health_check_all_providers(self):
        """Test health checking all providers."""
        router = IntelligentDataRouter()
        
        healthy_provider = MockDataProvider("healthy", is_healthy=True)
        unhealthy_provider = MockDataProvider("unhealthy", is_healthy=False)

        router.register_provider(healthy_provider)
        router.register_provider(unhealthy_provider)

        health_results = await router.health_check_all_providers()

        assert health_results["healthy"] is True
        assert health_results["unhealthy"] is False

    def test_calculate_provider_score_new_provider(self):
        """Test calculating score for new provider."""
        router = IntelligentDataRouter()
        query = DataQuery(asset=AssetType.STOCK)

        score = router._calculate_provider_score("new_provider", query)

        assert score == 50.0  # Neutral score for new provider

    def test_calculate_provider_score_with_metrics(self):
        """Test calculating score with various metrics."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)
        
        # Record some successful requests
        router.record_provider_success("test_provider", 0.5)
        router.record_provider_success("test_provider", 0.3)

        query = DataQuery(asset=AssetType.STOCK)
        score = router._calculate_provider_score("test_provider", query)

        # Should have high score due to good performance
        assert score > 90.0

    def test_calculate_provider_score_high_failure_rate(self):
        """Test calculating score with high failure rate."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)
        
        # Record failures
        for _ in range(10):
            router.record_provider_failure("test_provider", Exception("Test"))

        query = DataQuery(asset=AssetType.STOCK)
        score = router._calculate_provider_score("test_provider", query)

        # Should have low score due to high failure rate
        assert score < 60.0

    def test_calculate_provider_score_slow_response(self):
        """Test calculating score with slow response times."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)
        
        # Record slow responses
        router.record_provider_success("test_provider", 5.0)  # 5 seconds
        router.record_provider_success("test_provider", 3.0)  # 3 seconds

        query = DataQuery(asset=AssetType.STOCK)
        score = router._calculate_provider_score("test_provider", query)

        # Should have lower score due to slow responses (accounting for random factor)
        assert score < 85.0

    def test_is_circuit_breaker_open(self):
        """Test circuit breaker logic."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)

        # Initially closed
        assert not router._is_circuit_breaker_open("test_provider")

        # Record failures below threshold
        for _ in range(router._circuit_breaker_threshold - 1):
            router.record_provider_failure("test_provider", Exception("Test"))

        assert not router._is_circuit_breaker_open("test_provider")

        # Record one more failure to trigger circuit breaker
        router.record_provider_failure("test_provider", Exception("Test"))

        assert router._is_circuit_breaker_open("test_provider")

    def test_circuit_breaker_timeout(self):
        """Test circuit breaker timeout logic."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)

        # Trigger circuit breaker
        for _ in range(router._circuit_breaker_threshold):
            router.record_provider_failure("test_provider", Exception("Test"))

        assert router._is_circuit_breaker_open("test_provider")

        # Simulate timeout by setting old failure time
        router._circuit_breaker_last_failure["test_provider"] = (
            time.time() - router._circuit_breaker_timeout - 1
        )

        assert not router._is_circuit_breaker_open("test_provider")

    def test_circuit_breaker_reset_on_success(self):
        """Test circuit breaker reset on successful request."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)

        # Trigger circuit breaker
        for _ in range(router._circuit_breaker_threshold):
            router.record_provider_failure("test_provider", Exception("Test"))

        assert router._circuit_breaker_failures["test_provider"] == router._circuit_breaker_threshold

        # Record success should reset circuit breaker
        router.record_provider_success("test_provider", 0.5)

        assert router._circuit_breaker_failures["test_provider"] == 0

    @pytest.mark.asyncio
    async def test_check_provider_health_if_needed(self):
        """Test conditional health checking."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider", is_healthy=True)

        router.register_provider(provider)

        # Set short health check interval for testing
        router._health_check_interval = 0.1

        providers = [provider]
        
        # First call should trigger health check
        await router._check_provider_health_if_needed(providers)
        
        # Verify health check was performed
        assert "test_provider" in router._last_health_check
        assert router._registry._provider_health["test_provider"] is True

        # Immediate second call should not trigger health check
        last_check_time = router._last_health_check["test_provider"]
        await router._check_provider_health_if_needed(providers)
        
        # Time should be the same (no new health check)
        assert router._last_health_check["test_provider"] == last_check_time

    @pytest.mark.asyncio
    async def test_check_single_provider_health_success(self):
        """Test single provider health check success."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider", is_healthy=True)

        router.register_provider(provider)

        await router._check_single_provider_health(provider)

        assert router._registry._provider_health["test_provider"] is True
        assert "test_provider" in router._last_health_check

    @pytest.mark.asyncio
    async def test_check_single_provider_health_failure(self):
        """Test single provider health check failure."""
        router = IntelligentDataRouter()
        
        class FailingProvider(MockDataProvider):
            async def health_check(self) -> bool:
                raise Exception("Health check failed")

        provider = FailingProvider("failing_provider")
        router.register_provider(provider)

        await router._check_single_provider_health(provider)

        assert router._registry._provider_health["failing_provider"] is False
        assert "failing_provider" in router._last_health_check

    def test_initialize_provider_metrics(self):
        """Test provider metrics initialization."""
        router = IntelligentDataRouter()

        router._initialize_provider_metrics("test_provider")

        metrics = router._provider_metrics["test_provider"]
        assert metrics["total_requests"] == 0
        assert metrics["successful_requests"] == 0
        assert metrics["failed_requests"] == 0
        assert metrics["total_response_time"] == 0.0
        assert metrics["average_response_time"] == 0.0
        assert metrics["failure_rate"] == 0.0
        assert metrics["last_success_time"] == 0.0
        assert metrics["last_failure_time"] == 0.0

    def test_cleanup_provider_metrics(self):
        """Test provider metrics cleanup."""
        router = IntelligentDataRouter()
        provider = MockDataProvider("test_provider")

        router.register_provider(provider)
        router.record_provider_success("test_provider", 0.5)

        # Verify metrics exist
        assert "test_provider" in router._provider_metrics
        assert "test_provider" in router._circuit_breaker_failures

        router._cleanup_provider_metrics("test_provider")

        # Verify metrics are cleaned up
        assert "test_provider" not in router._provider_metrics
        assert "test_provider" not in router._circuit_breaker_failures


class TestDataRouterIntegration:
    """Integration tests for data router."""

    @pytest.mark.asyncio
    async def test_complete_routing_scenario(self):
        """Test complete routing scenario with multiple providers."""
        router = IntelligentDataRouter()
        
        # Create providers with different characteristics
        fast_provider = MockDataProvider("fast", {AssetType.STOCK}, response_delay=0.1)
        slow_provider = MockDataProvider("slow", {AssetType.STOCK}, response_delay=0.5)
        unreliable_provider = MockDataProvider("unreliable", {AssetType.STOCK})

        router.register_provider(fast_provider)
        router.register_provider(slow_provider)
        router.register_provider(unreliable_provider)

        # Simulate some history
        router.record_provider_success("fast", 0.1)
        router.record_provider_success("fast", 0.12)
        router.record_provider_success("slow", 0.5)
        router.record_provider_success("slow", 0.6)
        router.record_provider_failure("unreliable", Exception("Network error"))
        router.record_provider_failure("unreliable", Exception("Timeout"))

        query = DataQuery(asset=AssetType.STOCK, symbols=["AAPL"])
        
        # Route multiple queries and verify fast provider is preferred
        selections = []
        for _ in range(5):
            selected = await router.route_query(query)
            selections.append(selected.name)

        # Fast provider should be selected at least once due to better metrics
        # (randomness makes exact counts unpredictable)
        assert "fast" in selections
        # Unreliable provider should not be selected due to failures
        assert "unreliable" not in selections

    @pytest.mark.asyncio
    async def test_failover_scenario(self):
        """Test failover scenario when primary provider fails."""
        router = IntelligentDataRouter()
        
        primary_provider = MockDataProvider("primary", {AssetType.STOCK})
        backup_provider = MockDataProvider("backup", {AssetType.STOCK})

        router.register_provider(primary_provider)
        router.register_provider(backup_provider)

        # Initially, both providers should be available
        query = DataQuery(asset=AssetType.STOCK)
        
        # Simulate primary provider failures
        for _ in range(router._circuit_breaker_threshold):
            router.record_provider_failure("primary", Exception("Service unavailable"))

        # Now primary should be in circuit breaker state
        selected_provider = await router.route_query(query)
        assert selected_provider == backup_provider

        # After timeout, primary should be available again
        router._circuit_breaker_last_failure["primary"] = (
            time.time() - router._circuit_breaker_timeout - 1
        )

        # Primary should be selectable again
        available_providers = router.get_available_providers(query)
        assert primary_provider in available_providers

    @pytest.mark.asyncio
    async def test_load_balancing_scenario(self):
        """Test load balancing between equivalent providers."""
        router = IntelligentDataRouter()
        
        provider1 = MockDataProvider("provider1", {AssetType.STOCK})
        provider2 = MockDataProvider("provider2", {AssetType.STOCK})

        router.register_provider(provider1)
        router.register_provider(provider2)

        query = DataQuery(asset=AssetType.STOCK)
        
        # Route multiple queries and track selections
        selections = []
        for i in range(50):  # Increase iterations for better randomness
            selected = await router.route_query(query)
            selections.append(selected.name)
            
            # Simulate successful requests to maintain equal scores
            router.record_provider_success(selected.name, 0.3)
            
            # Reset metrics periodically to ensure fair load balancing
            if i % 10 == 0:
                router.reset_provider_metrics("provider1")
                router.reset_provider_metrics("provider2")

        # With randomness, both providers should be selected at least once
        # We don't require perfect distribution due to randomness
        unique_selections = set(selections)
        assert len(unique_selections) >= 2, f"Expected both providers to be selected, got: {unique_selections}"

    @pytest.mark.asyncio
    async def test_health_monitoring_integration(self):
        """Test health monitoring integration with routing."""
        router = IntelligentDataRouter()
        
        # Set short health check interval for testing
        router._health_check_interval = 0.1
        
        healthy_provider = MockDataProvider("healthy", {AssetType.STOCK}, is_healthy=True)
        unhealthy_provider = MockDataProvider("unhealthy", {AssetType.STOCK}, is_healthy=False)

        router.register_provider(healthy_provider)
        router.register_provider(unhealthy_provider)

        query = DataQuery(asset=AssetType.STOCK)
        
        # First routing should trigger health checks
        selected_provider = await router.route_query(query)
        
        # Should select healthy provider
        assert selected_provider == healthy_provider
        
        # Verify health status was updated
        assert router._registry._provider_health["healthy"] is True
        assert router._registry._provider_health["unhealthy"] is False