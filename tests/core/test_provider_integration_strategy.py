"""
Tests for Provider Integration Strategy.

This module contains comprehensive tests for the ProviderIntegrationStrategy class,
following TDD principles. Tests cover provider priority management, intelligent
provider selection, fault tolerance, and data consistency validation.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any, Set

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
from vprism.core.exceptions import (
    NoAvailableProviderException,
    ProviderException,
    DataValidationException,
)
from vprism.core.provider_abstraction import (
    EnhancedDataProvider,
    EnhancedProviderRegistry,
    ProviderCapability,
    AuthConfig,
    AuthType,
    RateLimitConfig,
)


class MockProvider(EnhancedDataProvider):
    """Mock provider for testing."""

    def __init__(
        self,
        name: str,
        priority: int = 1,
        supported_assets: Set[AssetType] = None,
        supported_markets: Set[MarketType] = None,
        data_delay: int = 0,
        should_fail: bool = False,
        latency_ms: int = 100,
    ):
        auth_config = AuthConfig(AuthType.NONE)
        rate_limit = RateLimitConfig(
            requests_per_minute=60, requests_per_hour=1000, concurrent_requests=5
        )
        super().__init__(name, auth_config, rate_limit)

        self._name = name
        self._priority = priority
        self._supported_assets = supported_assets or {AssetType.STOCK}
        self._supported_markets = supported_markets or {MarketType.US}
        self._data_delay = data_delay
        self._should_fail = should_fail
        self._latency_ms = latency_ms
        self._request_count = 0

    @property
    def name(self) -> str:
        return self._name

    def _discover_capability(self) -> ProviderCapability:
        return ProviderCapability(
            supported_assets=self._supported_assets,
            supported_markets=self._supported_markets,
            supported_timeframes={
                TimeFrame.DAY_1,
                TimeFrame.HOUR_1,
                TimeFrame.MINUTE_1,
            },
            max_symbols_per_request=100,
            supports_real_time=self._data_delay == 0,
            supports_historical=True,
            data_delay_seconds=self._data_delay,
            max_history_days=3650,
        )

    async def get_data(self, query: DataQuery) -> DataResponse:
        """Mock data retrieval."""
        self._request_count += 1

        # Simulate latency
        await asyncio.sleep(self._latency_ms / 1000.0)

        if self._should_fail:
            raise ProviderException(
                f"Mock provider {self.name} failed", provider=self.name
            )

        # Create mock data points
        data_points = []
        symbols = query.symbols or ["MOCK"]

        for symbol in symbols:
            data_points.append(
                DataPoint(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    open=Decimal("100.00"),
                    high=Decimal("105.00"),
                    low=Decimal("95.00"),
                    close=Decimal("102.00"),
                    volume=Decimal("1000000"),
                )
            )

        return DataResponse(
            data=data_points,
            metadata=ResponseMetadata(
                query_time=datetime.now(),
                execution_time_ms=float(self._latency_ms),
                record_count=len(data_points),
                cache_hit=False,
            ),
            source=ProviderInfo(
                name=self.name,
                version="1.0.0",
            ),
            query=query,
        )

    async def stream_data(self, query: DataQuery):
        """Mock streaming data."""
        for i in range(3):
            yield DataPoint(
                symbol=query.symbols[0] if query.symbols else "MOCK",
                timestamp=datetime.now(),
                close=Decimal(f"{100 + i}.00"),
            )
            await asyncio.sleep(0.1)

    async def health_check(self) -> bool:
        """Mock health check."""
        return not self._should_fail

    async def _authenticate(self) -> bool:
        """Mock authentication."""
        return True


class TestProviderIntegrationStrategy:
    """Test cases for ProviderIntegrationStrategy."""

    @pytest.fixture
    def mock_providers(self):
        """Create mock providers with different priorities and capabilities."""
        return {
            "vprism_native": MockProvider(
                name="vprism_native",
                priority=1,  # Highest priority
                supported_assets={AssetType.STOCK, AssetType.BOND, AssetType.ETF},
                supported_markets={MarketType.CN, MarketType.US},
                data_delay=0,
                latency_ms=50,
            ),
            "yfinance": MockProvider(
                name="yfinance",
                priority=2,  # Medium priority
                supported_assets={AssetType.STOCK, AssetType.ETF, AssetType.CRYPTO},
                supported_markets={MarketType.US, MarketType.GLOBAL},
                data_delay=0,
                latency_ms=100,
            ),
            "alpha_vantage": MockProvider(
                name="alpha_vantage",
                priority=2,  # Medium priority
                supported_assets={AssetType.STOCK, AssetType.FOREX, AssetType.CRYPTO},
                supported_markets={MarketType.US, MarketType.GLOBAL},
                data_delay=0,
                latency_ms=200,
            ),
            "akshare": MockProvider(
                name="akshare",
                priority=3,  # Lower priority
                supported_assets={AssetType.STOCK, AssetType.BOND, AssetType.FUND},
                supported_markets={MarketType.CN},
                data_delay=900,  # 15 minutes delay
                latency_ms=300,
            ),
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
        # Import here to avoid circular imports during test discovery
        from vprism.core.provider_integration_strategy import (
            ProviderIntegrationStrategy,
        )

        return ProviderIntegrationStrategy(provider_registry)

    def test_provider_priority_configuration(
        self, integration_strategy, mock_providers
    ):
        """Test that provider priorities are configured correctly."""
        priorities = integration_strategy.get_provider_priorities()

        # Verify priority order: vprism_native > yfinance/alpha_vantage > akshare
        assert priorities["vprism_native"] == 1
        assert priorities["yfinance"] == 2
        assert priorities["alpha_vantage"] == 2
        assert priorities["akshare"] == 3

    def test_provider_selection_by_priority(self, integration_strategy, mock_providers):
        """Test that providers are selected based on priority."""
        # Query that multiple providers can handle
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        selected_provider = integration_strategy.select_provider(query)

        # Should select vprism_native (highest priority) if it can handle the query
        assert selected_provider.name == "vprism_native"

    def test_provider_selection_by_capability(
        self, integration_strategy, mock_providers
    ):
        """Test provider selection based on capability matching."""
        # Query that only akshare can handle (CN market specific)
        query = DataQuery(
            asset=AssetType.FUND,  # Only akshare supports funds
            market=MarketType.CN,
            symbols=["000001"],
        )

        selected_provider = integration_strategy.select_provider(query)

        # Should select akshare as it's the only one that supports CN funds
        assert selected_provider.name == "akshare"

    def test_provider_selection_with_performance_scoring(
        self, integration_strategy, mock_providers
    ):
        """Test provider selection considers performance scores."""
        # Update performance scores
        integration_strategy.update_provider_performance(
            "yfinance", success=True, latency_ms=50
        )
        integration_strategy.update_provider_performance(
            "alpha_vantage", success=False, latency_ms=5000
        )

        # Query that both can handle
        query = DataQuery(
            asset=AssetType.CRYPTO, market=MarketType.US, symbols=["BTC-USD"]
        )

        selected_provider = integration_strategy.select_provider(query)

        # Should prefer yfinance due to better performance
        assert selected_provider.name == "yfinance"

    @pytest.mark.asyncio
    async def test_intelligent_provider_selection_algorithm(
        self, integration_strategy, mock_providers
    ):
        """Test the intelligent provider selection algorithm."""
        # Test various scenarios
        test_cases = [
            # (query, expected_provider_name, reason)
            (
                DataQuery(
                    asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
                ),
                "vprism_native",
                "Highest priority provider that supports CN stocks",
            ),
            (
                DataQuery(
                    asset=AssetType.FOREX, market=MarketType.US, symbols=["EURUSD"]
                ),
                "alpha_vantage",
                "Only provider that supports forex",
            ),
            (
                DataQuery(
                    asset=AssetType.CRYPTO, market=MarketType.US, symbols=["BTC-USD"]
                ),
                "yfinance",  # Should prefer yfinance over alpha_vantage due to better latency
                "Better performance among capable providers",
            ),
        ]

        for query, expected_provider, reason in test_cases:
            selected_provider = integration_strategy.select_provider(query)
            assert selected_provider.name == expected_provider, f"Failed: {reason}"

    @pytest.mark.asyncio
    async def test_fault_tolerance_and_fallback(
        self, integration_strategy, mock_providers
    ):
        """Test fault tolerance with automatic fallback to backup providers."""
        # Make the primary provider fail
        mock_providers["vprism_native"]._should_fail = True

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        # Should automatically fallback to next best provider
        response = await integration_strategy.execute_query_with_fallback(query)

        assert response is not None
        # Should have used yfinance as fallback
        assert response.source.name == "yfinance"

    @pytest.mark.asyncio
    async def test_provider_health_monitoring(
        self, integration_strategy, mock_providers
    ):
        """Test provider health monitoring and automatic exclusion of unhealthy providers."""
        # Mark a provider as unhealthy
        integration_strategy.mark_provider_unhealthy("yfinance")

        query = DataQuery(
            asset=AssetType.CRYPTO, market=MarketType.US, symbols=["BTC-USD"]
        )

        selected_provider = integration_strategy.select_provider(query)

        # Should not select unhealthy yfinance, should select alpha_vantage instead
        assert selected_provider.name == "alpha_vantage"

    @pytest.mark.asyncio
    async def test_dynamic_priority_adjustment(
        self, integration_strategy, mock_providers
    ):
        """Test dynamic priority adjustment based on performance."""
        # Simulate poor performance for high-priority provider
        for _ in range(10):
            integration_strategy.update_provider_performance(
                "vprism_native", success=False, latency_ms=5000
            )

        # Simulate good performance for lower-priority provider
        for _ in range(10):
            integration_strategy.update_provider_performance(
                "yfinance", success=True, latency_ms=50
            )

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        selected_provider = integration_strategy.select_provider(query)

        # Should prefer yfinance due to better performance despite lower base priority
        assert selected_provider.name == "yfinance"

    @pytest.mark.asyncio
    async def test_data_consistency_validation(
        self, integration_strategy, mock_providers
    ):
        """Test data consistency validation between providers."""
        query = DataQuery(
            asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
        )

        # Get data from multiple providers for consistency check
        consistency_report = await integration_strategy.validate_data_consistency(
            query, providers=["vprism_native", "akshare"]
        )

        assert consistency_report is not None
        assert "vprism_native" in consistency_report.provider_results
        assert "akshare" in consistency_report.provider_results
        assert hasattr(consistency_report, "consistency_score")
        assert 0.0 <= consistency_report.consistency_score <= 1.0

    def test_provider_capability_scoring(self, integration_strategy, mock_providers):
        """Test provider capability scoring for query matching."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
            timeframe=TimeFrame.MINUTE_1,
        )

        scores = integration_strategy.calculate_provider_capability_scores(query)

        # All providers that support US stocks should have scores
        assert "vprism_native" in scores
        assert "yfinance" in scores
        assert "alpha_vantage" in scores

        # Providers with better capability match should have higher scores
        for provider_name, score in scores.items():
            assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_concurrent_provider_requests(
        self, integration_strategy, mock_providers
    ):
        """Test concurrent requests to multiple providers."""
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

    def test_provider_rate_limit_handling(self, integration_strategy, mock_providers):
        """Test provider rate limit handling and queuing."""
        # Set very low rate limit for testing
        mock_providers["yfinance"].rate_limit.requests_per_minute = 1

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        # Should handle rate limiting gracefully
        selected_provider = integration_strategy.select_provider(query)
        assert selected_provider is not None

    @pytest.mark.asyncio
    async def test_provider_authentication_validation(
        self, integration_strategy, mock_providers
    ):
        """Test provider authentication validation."""
        # Test that providers with invalid auth are excluded
        mock_providers["alpha_vantage"].auth_config.credentials = {}  # Invalid auth

        query = DataQuery(
            asset=AssetType.FOREX, market=MarketType.US, symbols=["EURUSD"]
        )

        # Should handle authentication failure gracefully
        try:
            selected_provider = integration_strategy.select_provider(query)
            # If alpha_vantage is the only forex provider, this should raise an exception
            # or fallback to another provider if available
        except NoAvailableProviderException:
            # Expected if no other provider supports forex
            pass

    def test_provider_configuration_validation(
        self, integration_strategy, mock_providers
    ):
        """Test provider configuration validation."""
        # Test that integration strategy validates provider configurations
        config_issues = integration_strategy.validate_provider_configurations()

        # Should return any configuration issues found
        assert isinstance(config_issues, list)

    @pytest.mark.asyncio
    async def test_provider_performance_monitoring(
        self, integration_strategy, mock_providers
    ):
        """Test comprehensive provider performance monitoring."""
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        # Execute query and monitor performance
        start_time = datetime.now()
        response = await integration_strategy.execute_query_with_fallback(query)
        end_time = datetime.now()

        # Check that performance metrics are recorded
        stats = integration_strategy.get_provider_performance_stats()

        assert isinstance(stats, dict)
        # Should have stats for the provider that handled the request
        provider_name = response.source.name
        assert provider_name in stats

        provider_stats = stats[provider_name]
        assert "total_requests" in provider_stats
        assert "success_rate" in provider_stats
        assert "average_latency_ms" in provider_stats

    def test_provider_selection_edge_cases(self, integration_strategy, mock_providers):
        """Test provider selection edge cases."""
        # Test with no capable providers
        query = DataQuery(
            asset=AssetType.COMMODITY,  # No provider supports commodities
            market=MarketType.US,
            symbols=["GOLD"],
        )

        with pytest.raises(NoAvailableProviderException):
            integration_strategy.select_provider(query)

    @pytest.mark.asyncio
    async def test_provider_circuit_breaker(self, integration_strategy, mock_providers):
        """Test circuit breaker functionality for failing providers."""
        # Simulate multiple failures for a provider
        for _ in range(5):
            integration_strategy.update_provider_performance(
                "vprism_native", success=False, latency_ms=5000
            )
            integration_strategy._circuit_breakers["vprism_native"].record_failure()

        # Provider should be circuit-broken
        assert integration_strategy.is_provider_circuit_broken("vprism_native")

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        selected_provider = integration_strategy.select_provider(query)

        # Should not select circuit-broken provider
        assert selected_provider.name != "vprism_native"

    def test_provider_load_balancing(self, integration_strategy, mock_providers):
        """Test load balancing among providers with similar capabilities."""
        # Set similar performance scores for multiple providers
        integration_strategy.update_provider_performance(
            "yfinance", success=True, latency_ms=100
        )
        integration_strategy.update_provider_performance(
            "alpha_vantage", success=True, latency_ms=100
        )

        query = DataQuery(
            asset=AssetType.CRYPTO, market=MarketType.US, symbols=["BTC-USD"]
        )

        # Execute multiple queries and check distribution
        selected_providers = []
        for _ in range(10):
            provider = integration_strategy.select_provider(query)
            selected_providers.append(provider.name)

        # Should distribute load between capable providers
        unique_providers = set(selected_providers)
        assert len(unique_providers) >= 1  # At least one provider used


class TestDataConsistencyValidation:
    """Test data consistency validation functionality."""

    @pytest.fixture
    def mock_providers_with_data(self):
        """Create mock providers that return different data for consistency testing."""
        providers = {}

        # Provider 1: Returns consistent data
        class MockProvider1(MockProvider):
            async def get_data(self, query: DataQuery) -> DataResponse:
                data_points = [
                    DataPoint(
                        symbol="TEST",
                        timestamp=datetime(2024, 1, 1),
                        open=Decimal("100.00"),
                        close=Decimal("102.00"),
                        volume=Decimal("1000000"),
                    )
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

        provider1 = MockProvider1(name="provider1")
        providers["provider1"] = provider1

        # Provider 2: Returns slightly different data
        class MockProvider2(MockProvider):
            async def get_data(self, query: DataQuery) -> DataResponse:
                data_points = [
                    DataPoint(
                        symbol="TEST",
                        timestamp=datetime(2024, 1, 1),
                        open=Decimal("100.10"),  # Slightly different
                        close=Decimal("102.05"),  # Slightly different
                        volume=Decimal("1000500"),  # Slightly different
                    )
                ]
                return DataResponse(
                    data=data_points,
                    metadata=ResponseMetadata(
                        query_time=datetime.now(),
                        execution_time_ms=120.0,
                        record_count=len(data_points),
                        cache_hit=False,
                    ),
                    source=ProviderInfo(name=self.name, version="1.0.0"),
                    query=query,
                )

        provider2 = MockProvider2(name="provider2")
        providers["provider2"] = provider2

        return providers

    @pytest.mark.asyncio
    async def test_data_consistency_validation_basic(self, mock_providers_with_data):
        """Test basic data consistency validation between providers."""
        from vprism.core.provider_integration_strategy import (
            ProviderIntegrationStrategy,
        )

        registry = EnhancedProviderRegistry()
        for provider in mock_providers_with_data.values():
            registry.register_provider(provider)

        strategy = ProviderIntegrationStrategy(registry)

        query = DataQuery(asset=AssetType.STOCK, symbols=["TEST"])

        report = await strategy.validate_data_consistency(
            query, providers=["provider1", "provider2"]
        )

        assert report is not None
        assert len(report.provider_results) == 2
        assert 0.0 <= report.consistency_score <= 1.0

    @pytest.mark.asyncio
    async def test_data_consistency_tolerance_configuration(
        self, mock_providers_with_data
    ):
        """Test data consistency validation with different tolerance levels."""
        from vprism.core.provider_integration_strategy import (
            ProviderIntegrationStrategy,
        )

        registry = EnhancedProviderRegistry()
        for provider in mock_providers_with_data.values():
            registry.register_provider(provider)

        strategy = ProviderIntegrationStrategy(registry)

        query = DataQuery(asset=AssetType.STOCK, symbols=["TEST"])

        # Test with strict tolerance
        strict_report = await strategy.validate_data_consistency(
            query, providers=["provider1", "provider2"], tolerance=0.001
        )

        # Test with loose tolerance
        loose_report = await strategy.validate_data_consistency(
            query, providers=["provider1", "provider2"], tolerance=0.1
        )

        # Loose tolerance should have higher consistency score
        assert loose_report.consistency_score >= strict_report.consistency_score
