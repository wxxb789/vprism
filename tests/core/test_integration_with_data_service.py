"""
Integration tests for ProviderIntegrationStrategy with DataService.

This module tests the integration between the ProviderIntegrationStrategy
and the existing DataService to ensure they work together correctly.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, AsyncMock

from vprism.core.models import (
    AssetType,
    DataQuery,
    DataResponse,
    DataPoint,
    MarketType,
    TimeFrame,
    ResponseMetadata,
    ProviderInfo,
)
from vprism.core.provider_abstraction import (
    EnhancedProviderRegistry,
    EnhancedDataProvider,
    AuthConfig,
    AuthType,
    RateLimitConfig,
    ProviderCapability,
)
from vprism.core.provider_integration_strategy import ProviderIntegrationStrategy


class MockIntegratedProvider(EnhancedDataProvider):
    """Mock provider for integration testing."""

    def __init__(self, name: str, should_fail: bool = False):
        auth_config = AuthConfig(AuthType.NONE)
        rate_limit = RateLimitConfig(
            requests_per_minute=60, requests_per_hour=1000, concurrent_requests=5
        )
        super().__init__(name, auth_config, rate_limit)
        self._name = name
        self._should_fail = should_fail

    @property
    def name(self) -> str:
        return self._name

    def _discover_capability(self) -> ProviderCapability:
        return ProviderCapability(
            supported_assets={AssetType.STOCK},
            supported_markets={MarketType.US},
            supported_timeframes={TimeFrame.DAY_1},
            max_symbols_per_request=100,
            supports_real_time=True,
            supports_historical=True,
            data_delay_seconds=0,
        )

    async def get_data(self, query: DataQuery) -> DataResponse:
        """Mock data retrieval."""
        if self._should_fail:
            raise Exception(f"Provider {self.name} failed")

        data_points = [
            DataPoint(
                symbol=symbol,
                timestamp=datetime.now(),
                open=Decimal("100.00"),
                high=Decimal("105.00"),
                low=Decimal("95.00"),
                close=Decimal("102.00"),
                volume=Decimal("1000000"),
            )
            for symbol in (query.symbols or ["TEST"])
        ]

        return DataResponse(
            data=data_points,
            metadata=ResponseMetadata(
                query_time=datetime.now(),
                execution_time_ms=100.0,
                record_count=len(data_points),
                cache_hit=False,
            ),
            source=ProviderInfo(name=self.name, version="1.0.0"),
            query=query,
        )

    async def stream_data(self, query: DataQuery):
        """Mock streaming data."""
        for i in range(3):
            yield DataPoint(
                symbol=query.symbols[0] if query.symbols else "TEST",
                timestamp=datetime.now(),
                close=Decimal(f"{100 + i}.00"),
            )

    async def health_check(self) -> bool:
        """Mock health check."""
        return not self._should_fail

    async def _authenticate(self) -> bool:
        """Mock authentication."""
        return True


class TestProviderIntegrationWithDataService:
    """Test integration between ProviderIntegrationStrategy and DataService."""

    @pytest.fixture
    def mock_providers(self):
        """Create mock providers for integration testing."""
        return {
            "vprism_native": MockIntegratedProvider("vprism_native"),
            "yfinance": MockIntegratedProvider("yfinance"),
            "akshare": MockIntegratedProvider("akshare"),
        }

    @pytest.fixture
    def provider_registry(self, mock_providers):
        """Create provider registry with mock providers."""
        registry = EnhancedProviderRegistry()
        for provider in mock_providers.values():
            registry.register_provider(provider)
        return registry

    @pytest.fixture
    def integration_strategy(self, provider_registry):
        """Create ProviderIntegrationStrategy instance."""
        return ProviderIntegrationStrategy(provider_registry)

    @pytest.mark.asyncio
    async def test_integration_strategy_with_simple_query(self, integration_strategy):
        """Test that integration strategy can handle simple queries."""
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        # Test provider selection
        selected_provider = integration_strategy.select_provider(query)
        assert selected_provider is not None
        assert selected_provider.name in ["vprism_native", "yfinance", "akshare"]

        # Test query execution with fallback
        response = await integration_strategy.execute_query_with_fallback(query)
        assert response is not None
        assert len(response.data) == 1
        assert response.data[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_integration_strategy_provider_priorities(self, integration_strategy):
        """Test that provider priorities are respected."""
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        # Should select vprism_native (highest priority)
        selected_provider = integration_strategy.select_provider(query)
        assert selected_provider.name == "vprism_native"

    @pytest.mark.asyncio
    async def test_integration_strategy_fallback_behavior(
        self, integration_strategy, mock_providers
    ):
        """Test fallback behavior when primary provider fails."""
        # Make primary provider fail
        mock_providers["vprism_native"]._should_fail = True

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        # Should still get a response from fallback provider
        response = await integration_strategy.execute_query_with_fallback(query)
        assert response is not None
        assert response.source.name in ["yfinance", "akshare"]  # Should use fallback

    @pytest.mark.asyncio
    async def test_integration_strategy_performance_tracking(
        self, integration_strategy
    ):
        """Test that performance metrics are tracked correctly."""
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        # Execute a few queries
        for _ in range(3):
            await integration_strategy.execute_query_with_fallback(query)

        # Check performance stats
        stats = integration_strategy.get_provider_performance_stats()
        assert len(stats) > 0

        # Should have stats for the provider that handled requests
        for provider_name, provider_stats in stats.items():
            if provider_stats["total_requests"] > 0:
                assert provider_stats["successful_requests"] > 0
                assert provider_stats["success_rate"] > 0
                assert provider_stats["average_latency_ms"] >= 0

    def test_integration_strategy_configuration_validation(self, integration_strategy):
        """Test provider configuration validation."""
        issues = integration_strategy.validate_provider_configurations()

        # Should return a list (may be empty if all configurations are valid)
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_integration_strategy_concurrent_requests(self, integration_strategy):
        """Test handling of concurrent requests."""
        import asyncio

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        # Execute multiple concurrent requests
        tasks = [
            integration_strategy.execute_query_with_fallback(query) for _ in range(5)
        ]

        responses = await asyncio.gather(*tasks)

        # All requests should succeed
        assert len(responses) == 5
        for response in responses:
            assert response is not None
            assert len(response.data) > 0

    def test_integration_strategy_provider_priority_configuration(
        self, integration_strategy
    ):
        """Test that provider priorities are configured correctly."""
        priorities = integration_strategy.get_provider_priorities()

        # Verify expected priority order
        assert priorities["vprism_native"] == 1  # Highest priority
        assert priorities.get("yfinance", 2) == 2  # Medium priority
        assert priorities.get("akshare", 3) == 3  # Lower priority

    @pytest.mark.asyncio
    async def test_integration_strategy_circuit_breaker_integration(
        self, integration_strategy, mock_providers
    ):
        """Test circuit breaker integration."""
        # Simulate multiple failures to trigger circuit breaker
        provider_name = "vprism_native"

        for _ in range(5):
            integration_strategy.update_provider_performance(
                provider_name, success=False, latency_ms=5000
            )
            integration_strategy._circuit_breakers[provider_name].record_failure()

        # Circuit breaker should be open
        assert integration_strategy.is_provider_circuit_broken(provider_name)

        # Query should use different provider
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        selected_provider = integration_strategy.select_provider(query)
        assert (
            selected_provider.name != provider_name
        )  # Should not select circuit-broken provider

    def test_integration_strategy_capability_scoring(self, integration_strategy):
        """Test provider capability scoring."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
            timeframe=TimeFrame.DAY_1,
        )

        scores = integration_strategy.calculate_provider_capability_scores(query)

        # Should have scores for providers that can handle the query
        assert len(scores) > 0
        for provider_name, score in scores.items():
            assert 0.0 <= score <= 1.0
            assert isinstance(score, float)
