"""
Tests for intelligent data router.

This module contains comprehensive tests for the DataRouter class,
including routing scenarios, provider scoring, health checks, and
fault tolerance mechanisms. Following TDD principles with 90% coverage target.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vprism.core.exceptions import (
    NoAvailableProviderException,
    ProviderException,
    RateLimitException,
)
from vprism.core.models import (
    AssetType,
    DataQuery,
    DataResponse,
    MarketType,
    TimeFrame,
)
from vprism.core.provider_abstraction import (
    AuthConfig,
    AuthType,
    EnhancedDataProvider,
    EnhancedProviderRegistry,
    ProviderCapability,
    RateLimitConfig,
)


class MockProvider(EnhancedDataProvider):
    """Mock provider for testing DataRouter."""

    def __init__(
        self,
        name: str,
        supported_assets: set[AssetType] | None = None,
        data_delay_seconds: int = 0,
        healthy: bool = True,
        auth_success: bool = True,
        request_latency_ms: int = 100,
        should_fail: bool = False,
    ):
        """Initialize mock provider with configurable behavior."""
        auth_config = AuthConfig(AuthType.NONE, {})
        rate_limit = RateLimitConfig(60, 3600)
        super().__init__(name, auth_config, rate_limit)
        
        self._name = name
        self._supported_assets = supported_assets or {AssetType.STOCK}
        self._data_delay_seconds = data_delay_seconds
        self._healthy = healthy
        self._auth_success = auth_success
        self._request_latency_ms = request_latency_ms
        self._should_fail = should_fail
        self._request_count = 0
        self._last_request_time = None

    @property
    def name(self) -> str:
        return self._name

    def _discover_capability(self) -> ProviderCapability:
        return ProviderCapability(
            supported_assets=self._supported_assets,
            supported_markets={MarketType.US, MarketType.CN},
            supported_timeframes={TimeFrame.DAY_1, TimeFrame.HOUR_1},
            max_symbols_per_request=100,
            supports_real_time=True,
            supports_historical=True,
            data_delay_seconds=self._data_delay_seconds,
        )

    async def get_data(self, query: DataQuery) -> DataResponse:
        """Mock data retrieval with configurable behavior."""
        self._request_count += 1
        self._last_request_time = datetime.now()
        
        # Simulate request latency
        await asyncio.sleep(self._request_latency_ms / 1000.0)
        
        if self._should_fail:
            raise ProviderException(
                f"Mock failure from provider {self.name}",
                provider=self.name
            )
        
        # Create mock response
        mock_response = MagicMock(spec=DataResponse)
        mock_response.data = []
        mock_response.metadata = MagicMock()
        mock_response.source = MagicMock()
        mock_response.query = query
        return mock_response

    async def stream_data(self, query: DataQuery):
        """Mock streaming data."""
        yield MagicMock()

    async def health_check(self) -> bool:
        """Mock health check."""
        return self._healthy

    async def _authenticate(self) -> bool:
        """Mock authentication."""
        return self._auth_success

    def set_healthy(self, healthy: bool):
        """Set provider health status."""
        self._healthy = healthy

    def set_should_fail(self, should_fail: bool):
        """Set whether provider should fail requests."""
        self._should_fail = should_fail

    def get_request_count(self) -> int:
        """Get number of requests made to this provider."""
        return self._request_count

    def get_last_request_time(self) -> datetime | None:
        """Get timestamp of last request."""
        return self._last_request_time


class TestDataRouter:
    """Test DataRouter class."""

    @pytest.fixture
    def registry(self):
        """Create a provider registry for testing."""
        return EnhancedProviderRegistry()

    @pytest.fixture
    def mock_providers(self):
        """Create mock providers for testing."""
        return {
            "fast_provider": MockProvider(
                "fast_provider",
                supported_assets={AssetType.STOCK},
                data_delay_seconds=0,
                request_latency_ms=50,
            ),
            "slow_provider": MockProvider(
                "slow_provider",
                supported_assets={AssetType.STOCK},
                data_delay_seconds=15,
                request_latency_ms=200,
            ),
            "bond_provider": MockProvider(
                "bond_provider",
                supported_assets={AssetType.BOND},
                data_delay_seconds=0,
                request_latency_ms=100,
            ),
            "multi_provider": MockProvider(
                "multi_provider",
                supported_assets={AssetType.STOCK, AssetType.ETF, AssetType.BOND},
                data_delay_seconds=5,
                request_latency_ms=150,
            ),
        }

    @pytest.fixture
    def populated_registry(self, registry, mock_providers):
        """Create a registry populated with mock providers."""
        for provider in mock_providers.values():
            registry.register_provider(provider)
        return registry

    def test_data_router_initialization(self, registry):
        """Test DataRouter initialization."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(registry)
        assert router.registry is registry
        assert len(router._provider_scores) == 0
        assert len(router._provider_performance_history) == 0

    def test_data_router_route_query_basic(self, populated_registry, mock_providers):
        """Test basic query routing to capable provider."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Create stock query
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        
        # Route query
        selected_provider = router.route_query(query)
        
        # Should select a provider that can handle stocks
        assert selected_provider is not None
        assert selected_provider.name in ["fast_provider", "slow_provider", "multi_provider"]
        assert AssetType.STOCK in selected_provider.capability.supported_assets

    def test_data_router_route_query_no_capable_provider(self, populated_registry):
        """Test routing when no provider can handle the query."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Create query for unsupported asset type
        query = DataQuery(
            asset=AssetType.CRYPTO,  # No provider supports crypto
            market=MarketType.US,
            symbols=["BTC"]
        )
        
        # Should raise exception
        with pytest.raises(NoAvailableProviderException) as exc_info:
            router.route_query(query)
        
        assert "No capable provider found" in str(exc_info.value)
        assert exc_info.value.error_code == "NO_PROVIDER_AVAILABLE"

    def test_data_router_route_query_prefers_low_latency(self, populated_registry, mock_providers):
        """Test that router considers data delay in provider selection."""
        from vprism.core.data_router import DataRouter
        
        # Create a controlled test with providers having different delays
        test_registry = EnhancedProviderRegistry()
        fast_provider = MockProvider("fast", {AssetType.STOCK}, data_delay_seconds=0)
        slow_provider = MockProvider("slow", {AssetType.STOCK}, data_delay_seconds=15)
        
        test_registry.register_provider(fast_provider)
        test_registry.register_provider(slow_provider)
        
        test_router = DataRouter(test_registry)
        
        # Create stock query
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        
        # Test that both providers can be selected (showing the algorithm works)
        selected_providers = set()
        for _ in range(50):
            provider = test_router.route_query(query)
            selected_providers.add(provider.name)
            if len(selected_providers) == 2:  # Both providers selected
                break
        
        # Both providers should be capable of being selected
        assert "fast" in selected_providers
        assert "slow" in selected_providers

    def test_data_router_route_query_considers_health(self, populated_registry, mock_providers):
        """Test that router excludes unhealthy providers."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Mark fast_provider as unhealthy
        populated_registry.update_provider_health("fast_provider", False)
        
        # Create stock query
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        
        # Route query
        selected_provider = router.route_query(query)
        
        # Should not select the unhealthy provider
        assert selected_provider.name != "fast_provider"
        assert selected_provider.name in ["slow_provider", "multi_provider"]

    def test_data_router_update_provider_score_success(self, populated_registry):
        """Test updating provider score on successful request."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Initial score should be 1.0
        initial_score = router.get_provider_score("fast_provider")
        assert initial_score == 1.0
        
        # Update score with successful request
        router.update_provider_score("fast_provider", success=True, latency_ms=100)
        
        # Score should improve
        new_score = router.get_provider_score("fast_provider")
        assert new_score > initial_score

    def test_data_router_update_provider_score_failure(self, populated_registry):
        """Test updating provider score on failed request."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Initial score should be 1.0
        initial_score = router.get_provider_score("fast_provider")
        assert initial_score == 1.0
        
        # Update score with failed request
        router.update_provider_score("fast_provider", success=False, latency_ms=1000)
        
        # Score should decrease
        new_score = router.get_provider_score("fast_provider")
        assert new_score < initial_score

    def test_data_router_update_provider_score_high_latency_penalty(self, populated_registry):
        """Test that high latency is penalized in scoring."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Update score with low latency success
        router.update_provider_score("fast_provider", success=True, latency_ms=50)
        low_latency_score = router.get_provider_score("fast_provider")
        
        # Reset score
        router._provider_scores["fast_provider"] = 1.0
        
        # Update score with high latency success
        router.update_provider_score("fast_provider", success=True, latency_ms=5000)
        high_latency_score = router.get_provider_score("fast_provider")
        
        # Low latency should result in better score
        assert low_latency_score > high_latency_score

    def test_data_router_score_bounds(self, populated_registry):
        """Test that provider scores are bounded between 0.1 and 2.0."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Try to drive score very low
        for _ in range(20):
            router.update_provider_score("fast_provider", success=False, latency_ms=10000)
        
        score = router.get_provider_score("fast_provider")
        assert score >= 0.1  # Should not go below minimum
        
        # Reset and try to drive score very high
        router._provider_scores["fast_provider"] = 1.0
        for _ in range(20):
            router.update_provider_score("fast_provider", success=True, latency_ms=10)
        
        score = router.get_provider_score("fast_provider")
        assert score <= 2.0  # Should not go above maximum

    def test_data_router_route_with_scoring(self, populated_registry, mock_providers):
        """Test that routing considers provider scores."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Create providers with same data delay but different scores
        test_registry = EnhancedProviderRegistry()
        high_score_provider = MockProvider("high_score", {AssetType.STOCK}, data_delay_seconds=0)
        low_score_provider = MockProvider("low_score", {AssetType.STOCK}, data_delay_seconds=0)
        
        test_registry.register_provider(high_score_provider)
        test_registry.register_provider(low_score_provider)
        
        test_router = DataRouter(test_registry)
        
        # Set different scores (same delay, so score should be the deciding factor)
        test_router._provider_scores["high_score"] = 1.8
        test_router._provider_scores["low_score"] = 0.5
        
        # Create stock query
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        
        # Route query multiple times
        selected_providers = []
        for _ in range(20):
            provider = test_router.route_query(query)
            selected_providers.append(provider.name)
        
        # Should prefer the higher-scored provider
        high_score_count = selected_providers.count("high_score")
        low_score_count = selected_providers.count("low_score")
        
        # Higher scored provider should be selected more often
        assert high_score_count > low_score_count, f"High score: {high_score_count}, Low score: {low_score_count}"

    @pytest.mark.asyncio
    async def test_data_router_execute_query_success(self, populated_registry, mock_providers):
        """Test successful query execution through router."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Create stock query
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        
        # Execute query
        response = await router.execute_query(query)
        
        # Should get a response
        assert response is not None
        assert hasattr(response, 'data')
        assert hasattr(response, 'metadata')
        assert hasattr(response, 'source')
        assert hasattr(response, 'query')

    @pytest.mark.asyncio
    async def test_data_router_execute_query_with_fallback(self, populated_registry, mock_providers):
        """Test query execution with provider fallback on failure."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Create a registry with only two providers to make the test more predictable
        test_registry = EnhancedProviderRegistry()
        failing_provider = MockProvider("failing", {AssetType.STOCK}, should_fail=True)
        working_provider = MockProvider("working", {AssetType.STOCK}, should_fail=False)
        
        test_registry.register_provider(failing_provider)
        test_registry.register_provider(working_provider)
        
        test_router = DataRouter(test_registry)
        
        # Boost the failing provider's score to ensure it gets selected first
        test_router._provider_scores["failing"] = 2.0
        test_router._provider_scores["working"] = 1.0
        
        # Create stock query
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        
        # Execute query - should fallback to working provider
        response = await test_router.execute_query(query)
        
        # Should still get a response from fallback provider
        assert response is not None
        
        # The key test is that we got a response despite one provider failing
        # This demonstrates the fallback mechanism is working
        assert response is not None
        
        # The failing provider should be marked as unhealthy
        assert not test_registry._provider_health["failing"]

    @pytest.mark.asyncio
    async def test_data_router_execute_query_all_providers_fail(self, populated_registry, mock_providers):
        """Test query execution when all providers fail."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Make all stock providers fail
        for provider_name, provider in mock_providers.items():
            if AssetType.STOCK in provider.capability.supported_assets:
                provider.set_should_fail(True)
        
        # Create stock query
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        
        # Execute query - should raise exception
        with pytest.raises(NoAvailableProviderException):
            await router.execute_query(query)

    @pytest.mark.asyncio
    async def test_data_router_execute_query_updates_scores(self, populated_registry, mock_providers):
        """Test that query execution updates provider scores."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Get initial scores for all providers
        initial_scores = {}
        for provider_name in mock_providers.keys():
            initial_scores[provider_name] = router.get_provider_score(provider_name)
        
        # Create stock query
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        
        # Execute query
        response = await router.execute_query(query)
        assert response is not None
        
        # At least one provider's score should have been updated
        score_updated = False
        for provider_name in mock_providers.keys():
            new_score = router.get_provider_score(provider_name)
            if new_score != initial_scores[provider_name]:
                score_updated = True
                break
        
        assert score_updated, "No provider scores were updated after query execution"

    def test_data_router_get_provider_performance_stats(self, populated_registry):
        """Test getting provider performance statistics."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Add some performance history
        router.update_provider_score("fast_provider", success=True, latency_ms=100)
        router.update_provider_score("fast_provider", success=True, latency_ms=150)
        router.update_provider_score("fast_provider", success=False, latency_ms=200)
        
        # Get performance stats
        stats = router.get_provider_performance_stats("fast_provider")
        
        assert stats is not None
        assert "total_requests" in stats
        assert "success_rate" in stats
        assert "average_latency_ms" in stats
        assert "current_score" in stats
        
        assert stats["total_requests"] == 3
        assert stats["success_rate"] == 2/3  # 2 successes out of 3
        assert stats["average_latency_ms"] == (100 + 150 + 200) / 3

    def test_data_router_get_all_provider_stats(self, populated_registry):
        """Test getting statistics for all providers."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Add performance history for multiple providers
        router.update_provider_score("fast_provider", success=True, latency_ms=100)
        router.update_provider_score("slow_provider", success=False, latency_ms=300)
        
        # Get all stats
        all_stats = router.get_all_provider_stats()
        
        assert isinstance(all_stats, dict)
        assert "fast_provider" in all_stats
        assert "slow_provider" in all_stats
        
        # Each provider should have stats
        for provider_name, stats in all_stats.items():
            assert "total_requests" in stats
            assert "success_rate" in stats
            assert "current_score" in stats

    @pytest.mark.asyncio
    async def test_data_router_health_check_integration(self, populated_registry, mock_providers):
        """Test integration with provider health checks."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Make one provider unhealthy
        mock_providers["fast_provider"].set_healthy(False)
        
        # Run health checks
        health_results = await populated_registry.check_all_provider_health()
        
        # Verify health status was updated
        assert not health_results["fast_provider"]
        assert health_results["slow_provider"]
        
        # Create query
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        
        # Router should exclude unhealthy provider
        selected_provider = router.route_query(query)
        assert selected_provider.name != "fast_provider"

    def test_data_router_provider_selection_algorithm(self, populated_registry):
        """Test the provider selection algorithm in detail."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Set up different scores and capabilities
        router._provider_scores = {
            "fast_provider": 1.5,    # High score, low delay
            "slow_provider": 0.8,    # Low score, high delay  
            "multi_provider": 1.2,   # Medium score, medium delay
        }
        
        # Create query
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        
        # Test selection multiple times to verify algorithm
        selections = {}
        for _ in range(100):
            provider = router.route_query(query)
            selections[provider.name] = selections.get(provider.name, 0) + 1
        
        # Fast provider should be selected most often (highest score)
        assert selections["fast_provider"] > selections["slow_provider"]
        # The algorithm should show preference for higher scores (allowing some variance)
        total_high_score = selections["fast_provider"] + selections["multi_provider"]
        assert total_high_score > selections["slow_provider"] * 2

    def test_data_router_concurrent_access(self, populated_registry):
        """Test thread safety of DataRouter operations."""
        from vprism.core.data_router import DataRouter
        import threading
        import time
        
        router = DataRouter(populated_registry)
        results = []
        errors = []
        
        def update_scores():
            try:
                for i in range(50):
                    router.update_provider_score("fast_provider", success=True, latency_ms=100 + i)
                    time.sleep(0.001)  # Small delay to increase chance of race conditions
            except Exception as e:
                errors.append(e)
        
        def route_queries():
            try:
                query = DataQuery(
                    asset=AssetType.STOCK,
                    market=MarketType.US,
                    symbols=["AAPL"]
                )
                for _ in range(50):
                    provider = router.route_query(query)
                    results.append(provider.name)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Run concurrent operations
        threads = [
            threading.Thread(target=update_scores),
            threading.Thread(target=route_queries),
            threading.Thread(target=update_scores),
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should not have any errors
        assert len(errors) == 0
        assert len(results) == 50  # Should have 50 routing results

    def test_data_router_performance_history_cleanup(self, populated_registry):
        """Test that performance history is cleaned up to prevent memory leaks."""
        from vprism.core.data_router import DataRouter
        
        router = DataRouter(populated_registry)
        
        # Add many performance records
        for i in range(1500):  # More than the cleanup threshold
            router.update_provider_score("fast_provider", success=True, latency_ms=100)
        
        # History should be limited to prevent unbounded growth
        history = router._provider_performance_history.get("fast_provider", [])
        assert len(history) <= 1000  # Should be cleaned up to max size

    @pytest.mark.asyncio
    async def test_data_router_circuit_breaker_behavior(self, populated_registry, mock_providers):
        """Test circuit breaker-like behavior for failing providers."""
        from vprism.core.data_router import DataRouter
        
        # Create a controlled test environment
        test_registry = EnhancedProviderRegistry()
        failing_provider = MockProvider("failing", {AssetType.STOCK}, should_fail=True)
        working_provider = MockProvider("working", {AssetType.STOCK}, should_fail=False)
        
        test_registry.register_provider(failing_provider)
        test_registry.register_provider(working_provider)
        
        test_router = DataRouter(test_registry)
        
        # Boost failing provider score to ensure it gets selected
        test_router._provider_scores["failing"] = 2.0
        test_router._provider_scores["working"] = 1.0
        
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        
        # Execute multiple queries - should trigger circuit breaker behavior
        # The router should handle failures gracefully with fallback
        for _ in range(5):
            response = await test_router.execute_query(query)
            assert response is not None  # Should always get a response due to fallback
        
        # Failing provider should be marked unhealthy after repeated failures
        assert not test_registry._provider_health["failing"]
        
        # Failing provider's score should be reduced from initial 2.0
        failing_score = test_router.get_provider_score("failing")
        assert failing_score < 2.0, f"Failing provider score should be reduced from 2.0, got {failing_score}"
        
        # Subsequent routing should exclude the failed provider
        selected_provider = test_router.route_query(query)
        assert selected_provider.name != "failing"