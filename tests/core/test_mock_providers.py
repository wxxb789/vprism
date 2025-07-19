"""
Tests for mock data providers.

This module contains comprehensive tests for the mock provider implementations,
ensuring they behave correctly and can be used reliably for testing other components.
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from vprism.core.exceptions import (
    ProviderException,
    RateLimitException,
    ValidationException,
)
from vprism.core.mock_providers import (
    MOCK_BOND_PROVIDER,
    MOCK_CRYPTO_PROVIDER,
    MOCK_MULTI_ASSET_PROVIDER,
    MOCK_STOCK_PROVIDER,
    AlwaysFailingProvider,
    MockDataProvider,
    RateLimitedProvider,
    SlowProvider,
    SpecializedProvider,
    create_test_provider_suite,
)
from vprism.core.models import AssetType, DataQuery, MarketType, TimeFrame


class TestMockDataProvider:
    """Test MockDataProvider class."""

    def test_mock_provider_initialization(self):
        """Test mock provider initialization with default values."""
        provider = MockDataProvider("test_provider")
        
        assert provider.name == "test_provider"
        assert provider.info.name == "test_provider"
        assert provider.info.version == "1.0.0"
        assert provider.info.rate_limit == 1000
        assert provider.info.cost == "free"
        assert AssetType.STOCK in provider.supported_assets

    def test_mock_provider_custom_initialization(self):
        """Test mock provider initialization with custom values."""
        provider = MockDataProvider(
            "custom_provider",
            supported_assets={AssetType.BOND, AssetType.ETF},
            supported_markets={MarketType.EU, MarketType.JP},
            rate_limit=500,
            version="2.0.0",
            cost="premium",
        )
        
        assert provider.name == "custom_provider"
        assert provider.info.rate_limit == 500
        assert provider.info.version == "2.0.0"
        assert provider.info.cost == "premium"
        assert provider.supported_assets == {AssetType.BOND, AssetType.ETF}

    def test_can_handle_query_supported_asset(self):
        """Test can_handle_query with supported asset type."""
        provider = MockDataProvider(
            "test_provider",
            supported_assets={AssetType.STOCK},
            supported_markets={MarketType.US},
        )
        
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US)
        assert provider.can_handle_query(query) is True

    def test_can_handle_query_unsupported_asset(self):
        """Test can_handle_query with unsupported asset type."""
        provider = MockDataProvider(
            "test_provider",
            supported_assets={AssetType.STOCK},
        )
        
        query = DataQuery(asset=AssetType.BOND)
        assert provider.can_handle_query(query) is False

    def test_can_handle_query_unsupported_market(self):
        """Test can_handle_query with unsupported market."""
        provider = MockDataProvider(
            "test_provider",
            supported_assets={AssetType.STOCK},
            supported_markets={MarketType.US},
        )
        
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.JP)
        assert provider.can_handle_query(query) is False

    def test_can_handle_query_disabled_provider(self):
        """Test can_handle_query with disabled provider."""
        provider = MockDataProvider("test_provider", can_handle=False)
        
        query = DataQuery(asset=AssetType.STOCK)
        assert provider.can_handle_query(query) is False

    @pytest.mark.asyncio
    async def test_get_data_success(self):
        """Test successful data retrieval."""
        provider = MockDataProvider("test_provider")
        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["TEST001", "TEST002"],
            limit=10,
        )
        
        response = await provider.get_data(query)
        
        assert response is not None
        assert len(response.data) > 0
        assert response.metadata.record_count == len(response.data)
        assert response.source.name == "test_provider"
        assert response.query == query
        
        # Check data point structure
        data_point = response.data[0]
        assert data_point.symbol in ["TEST001", "TEST002"]
        assert data_point.open is not None
        assert data_point.high is not None
        assert data_point.low is not None
        assert data_point.close is not None
        assert data_point.volume is not None

    @pytest.mark.asyncio
    async def test_get_data_with_date_range(self):
        """Test data retrieval with date range."""
        provider = MockDataProvider("test_provider")
        start_date = datetime.now() - timedelta(days=10)
        end_date = datetime.now() - timedelta(days=5)
        
        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["TEST001"],
            start=start_date,
            end=end_date,
        )
        
        response = await provider.get_data(query)
        
        assert len(response.data) > 0
        for data_point in response.data:
            assert start_date <= data_point.timestamp <= end_date

    @pytest.mark.asyncio
    async def test_get_data_unsupported_query(self):
        """Test data retrieval with unsupported query raises exception."""
        provider = MockDataProvider(
            "test_provider",
            supported_assets={AssetType.STOCK},
        )
        
        query = DataQuery(asset=AssetType.BOND)
        
        with pytest.raises(ValidationException) as exc_info:
            await provider.get_data(query)
        
        assert "cannot handle this query" in str(exc_info.value)
        assert exc_info.value.error_code == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_get_data_with_failure_rate(self):
        """Test data retrieval with failure rate."""
        provider = MockDataProvider("test_provider", failure_rate=1.0)  # Always fail
        query = DataQuery(asset=AssetType.STOCK)
        
        with pytest.raises(ProviderException) as exc_info:
            await provider.get_data(query)
        
        assert "Random failure" in str(exc_info.value)
        assert exc_info.value.error_code == "PROVIDER_FAILURE"

    @pytest.mark.asyncio
    async def test_stream_data_success(self):
        """Test successful data streaming."""
        provider = MockDataProvider("test_provider")
        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["TEST001", "TEST002"],
        )
        
        data_points = []
        async for point in provider.stream_data(query):
            data_points.append(point)
        
        assert len(data_points) > 0
        assert all(point.symbol in ["TEST001", "TEST002"] for point in data_points)

    @pytest.mark.asyncio
    async def test_stream_data_with_delay(self):
        """Test data streaming with delay simulation."""
        provider = MockDataProvider("test_provider", simulate_delay=True)
        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["TEST001"],
        )
        
        start_time = datetime.now()
        data_points = []
        async for point in provider.stream_data(query):
            data_points.append(point)
            if len(data_points) >= 2:  # Limit to avoid long test
                break
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        assert len(data_points) >= 2
        assert elapsed > 0.1  # Should have some delay

    @pytest.mark.asyncio
    async def test_stream_data_unsupported_query(self):
        """Test data streaming with unsupported query raises exception."""
        provider = MockDataProvider(
            "test_provider",
            supported_assets={AssetType.STOCK},
        )
        
        query = DataQuery(asset=AssetType.BOND)
        
        with pytest.raises(ValidationException):
            async for _ in provider.stream_data(query):
                pass

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check for healthy provider."""
        provider = MockDataProvider("test_provider", is_healthy=True)
        
        is_healthy = await provider.health_check()
        
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        """Test health check for unhealthy provider."""
        provider = MockDataProvider("test_provider", is_healthy=False)
        
        is_healthy = await provider.health_check()
        
        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_health_check_with_failure_rate(self):
        """Test health check with failure rate affecting results."""
        # Provider with high failure rate but marked as healthy
        provider = MockDataProvider("test_provider", is_healthy=True, failure_rate=1.0)
        
        # Due to failure rate, health check should sometimes return False
        # We'll test multiple times to catch the random failure
        health_results = []
        for _ in range(10):
            result = await provider.health_check()
            health_results.append(result)
        
        # With 100% failure rate, we should get at least some False results
        assert not all(health_results), "Expected some health checks to fail due to failure rate"

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting functionality."""
        provider = MockDataProvider("test_provider", rate_limit=2)
        query = DataQuery(asset=AssetType.STOCK)
        
        # First two requests should succeed
        await provider.get_data(query)
        await provider.get_data(query)
        
        # Third request should fail with rate limit exception
        with pytest.raises(RateLimitException) as exc_info:
            await provider.get_data(query)
        
        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.error_code == "RATE_LIMIT_EXCEEDED"

    @pytest.mark.asyncio
    async def test_rate_limit_reset(self):
        """Test rate limit counter reset after time window."""
        import time
        
        provider = MockDataProvider("test_provider", rate_limit=2)
        query = DataQuery(asset=AssetType.STOCK)
        
        # Use up the rate limit
        await provider.get_data(query)
        await provider.get_data(query)
        
        # Manually reset the last reset time to simulate time passage
        provider._last_reset = datetime.now() - timedelta(minutes=2)
        
        # This should succeed because the rate limit window has reset
        response = await provider.get_data(query)
        assert len(response.data) > 0

    @pytest.mark.asyncio
    async def test_simulate_delay(self):
        """Test delay simulation."""
        provider = MockDataProvider("test_provider", simulate_delay=True)
        query = DataQuery(asset=AssetType.STOCK)
        
        start_time = datetime.now()
        await provider.get_data(query)
        end_time = datetime.now()
        
        # Should take at least some time due to simulated delay
        elapsed = (end_time - start_time).total_seconds()
        assert elapsed > 0.05  # At least 50ms delay


class TestAlwaysFailingProvider:
    """Test AlwaysFailingProvider class."""

    @pytest.mark.asyncio
    async def test_get_data_always_fails(self):
        """Test that get_data always fails."""
        provider = AlwaysFailingProvider()
        query = DataQuery(asset=AssetType.STOCK)
        
        with pytest.raises(ProviderException) as exc_info:
            await provider.get_data(query)
        
        assert "always fails" in str(exc_info.value)
        assert exc_info.value.error_code == "PROVIDER_ALWAYS_FAILS"

    @pytest.mark.asyncio
    async def test_stream_data_always_fails(self):
        """Test that stream_data always fails."""
        provider = AlwaysFailingProvider()
        query = DataQuery(asset=AssetType.STOCK)
        
        with pytest.raises(ProviderException) as exc_info:
            async for _ in provider.stream_data(query):
                pass
        
        assert "always fails" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_health_check_always_unhealthy(self):
        """Test that health check always returns False."""
        provider = AlwaysFailingProvider()
        
        is_healthy = await provider.health_check()
        
        assert is_healthy is False


class TestRateLimitedProvider:
    """Test RateLimitedProvider class."""

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self):
        """Test that rate limiting is enforced."""
        provider = RateLimitedProvider(rate_limit=3)
        query = DataQuery(asset=AssetType.STOCK)
        
        # Should succeed for first 3 requests
        for _ in range(3):
            await provider.get_data(query)
        
        # Fourth request should fail
        with pytest.raises(RateLimitException):
            await provider.get_data(query)


class TestSlowProvider:
    """Test SlowProvider class."""

    @pytest.mark.asyncio
    async def test_slow_response(self):
        """Test that provider responses are slow."""
        provider = SlowProvider(delay_seconds=0.1)  # Use small delay for testing
        query = DataQuery(asset=AssetType.STOCK)
        
        start_time = datetime.now()
        await provider.get_data(query)
        end_time = datetime.now()
        
        elapsed = (end_time - start_time).total_seconds()
        assert elapsed >= 0.1  # Should take at least the delay time

    @pytest.mark.asyncio
    async def test_slow_health_check(self):
        """Test that health check is slow."""
        provider = SlowProvider(delay_seconds=0.1)
        
        start_time = datetime.now()
        await provider.health_check()
        end_time = datetime.now()
        
        elapsed = (end_time - start_time).total_seconds()
        assert elapsed >= 0.1

    @pytest.mark.asyncio
    async def test_slow_stream_data(self):
        """Test that stream data is slow."""
        provider = SlowProvider(delay_seconds=0.1)
        query = DataQuery(asset=AssetType.STOCK, symbols=["SLOW001"])
        
        start_time = datetime.now()
        data_points = []
        async for point in provider.stream_data(query):
            data_points.append(point)
            if len(data_points) >= 2:  # Limit to avoid long test
                break
        end_time = datetime.now()
        
        elapsed = (end_time - start_time).total_seconds()
        assert elapsed >= 0.1  # Should have delay
        assert len(data_points) >= 2


class TestSpecializedProvider:
    """Test SpecializedProvider class."""

    def test_specialized_asset_support(self):
        """Test that specialized provider only supports specific asset."""
        provider = SpecializedProvider("crypto_specialist", AssetType.CRYPTO)
        
        crypto_query = DataQuery(asset=AssetType.CRYPTO)
        stock_query = DataQuery(asset=AssetType.STOCK)
        
        assert provider.can_handle_query(crypto_query) is True
        assert provider.can_handle_query(stock_query) is False

    def test_specialized_market_support(self):
        """Test that specialized provider only supports specific market."""
        provider = SpecializedProvider(
            "cn_specialist", AssetType.STOCK, MarketType.CN
        )
        
        cn_query = DataQuery(asset=AssetType.STOCK, market=MarketType.CN)
        us_query = DataQuery(asset=AssetType.STOCK, market=MarketType.US)
        
        assert provider.can_handle_query(cn_query) is True
        assert provider.can_handle_query(us_query) is False


class TestPredefinedProviders:
    """Test predefined provider instances."""

    def test_mock_stock_provider(self):
        """Test MOCK_STOCK_PROVIDER configuration."""
        provider = MOCK_STOCK_PROVIDER
        
        assert provider.name == "mock_stock_provider"
        assert AssetType.STOCK in provider.supported_assets
        assert len(provider.supported_assets) == 1

    def test_mock_crypto_provider(self):
        """Test MOCK_CRYPTO_PROVIDER configuration."""
        provider = MOCK_CRYPTO_PROVIDER
        
        assert provider.name == "mock_crypto_provider"
        assert AssetType.CRYPTO in provider.supported_assets
        assert len(provider.supported_assets) == 1

    def test_mock_bond_provider(self):
        """Test MOCK_BOND_PROVIDER configuration."""
        provider = MOCK_BOND_PROVIDER
        
        assert provider.name == "mock_bond_provider"
        assert AssetType.BOND in provider.supported_assets
        assert len(provider.supported_assets) == 1

    def test_mock_multi_asset_provider(self):
        """Test MOCK_MULTI_ASSET_PROVIDER configuration."""
        provider = MOCK_MULTI_ASSET_PROVIDER
        
        assert provider.name == "mock_multi_asset_provider"
        expected_assets = {AssetType.STOCK, AssetType.ETF, AssetType.FUND}
        assert provider.supported_assets == expected_assets


class TestProviderSuite:
    """Test provider suite creation."""

    def test_create_test_provider_suite(self):
        """Test creation of comprehensive test provider suite."""
        suite = create_test_provider_suite()
        
        # Check that all expected providers are present
        expected_providers = {
            "healthy_stock",
            "healthy_crypto",
            "healthy_bond",
            "multi_asset",
            "always_failing",
            "rate_limited",
            "slow_provider",
            "cn_stocks",
            "us_options",
        }
        
        assert set(suite.keys()) == expected_providers
        
        # Check that all providers implement the DataProvider interface
        for provider in suite.values():
            assert hasattr(provider, "get_data")
            assert hasattr(provider, "stream_data")
            assert hasattr(provider, "health_check")
            assert hasattr(provider, "can_handle_query")

    def test_provider_suite_diversity(self):
        """Test that provider suite covers diverse scenarios."""
        suite = create_test_provider_suite()
        
        # Test different asset types
        stock_providers = [
            p for p in suite.values() 
            if AssetType.STOCK in p.supported_assets
        ]
        crypto_providers = [
            p for p in suite.values() 
            if AssetType.CRYPTO in p.supported_assets
        ]
        bond_providers = [
            p for p in suite.values() 
            if AssetType.BOND in p.supported_assets
        ]
        
        assert len(stock_providers) > 0
        assert len(crypto_providers) > 0
        assert len(bond_providers) > 0

    @pytest.mark.asyncio
    async def test_provider_suite_functionality(self):
        """Test that all providers in suite are functional."""
        suite = create_test_provider_suite()
        
        for name, provider in suite.items():
            # Test health check
            try:
                health = await provider.health_check()
                assert isinstance(health, bool)
            except Exception:
                # Some providers (like AlwaysFailingProvider) may fail health checks
                pass
            
            # Test can_handle_query
            query = DataQuery(asset=AssetType.STOCK)
            can_handle = provider.can_handle_query(query)
            assert isinstance(can_handle, bool)


class TestMockProviderIntegration:
    """Integration tests for mock providers."""

    @pytest.mark.asyncio
    async def test_provider_lifecycle(self):
        """Test complete provider lifecycle."""
        provider = MockDataProvider(
            "lifecycle_test",
            supported_assets={AssetType.STOCK, AssetType.ETF},
            rate_limit=10,
        )
        
        # 1. Health check
        assert await provider.health_check() is True
        
        # 2. Query validation
        valid_query = DataQuery(asset=AssetType.STOCK, symbols=["TEST001"])
        invalid_query = DataQuery(asset=AssetType.BOND)
        
        assert provider.can_handle_query(valid_query) is True
        assert provider.can_handle_query(invalid_query) is False
        
        # 3. Data retrieval
        response = await provider.get_data(valid_query)
        assert len(response.data) > 0
        
        # 4. Data streaming
        stream_count = 0
        async for point in provider.stream_data(valid_query):
            stream_count += 1
            if stream_count >= 5:  # Limit to avoid long test
                break
        
        assert stream_count > 0

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling concurrent requests."""
        provider = MockDataProvider("concurrent_test", rate_limit=100)
        query = DataQuery(asset=AssetType.STOCK, symbols=["TEST001"])
        
        # Make multiple concurrent requests
        tasks = [provider.get_data(query) for _ in range(5)]
        responses = await asyncio.gather(*tasks)
        
        assert len(responses) == 5
        for response in responses:
            assert len(response.data) > 0

    @pytest.mark.asyncio
    async def test_error_handling_scenarios(self):
        """Test various error handling scenarios."""
        # Test provider that always fails
        failing_provider = AlwaysFailingProvider()
        query = DataQuery(asset=AssetType.STOCK)
        
        with pytest.raises(ProviderException):
            await failing_provider.get_data(query)
        
        # Test rate limiting
        rate_limited = RateLimitedProvider(rate_limit=1)
        await rate_limited.get_data(query)  # First request succeeds
        
        with pytest.raises(RateLimitException):
            await rate_limited.get_data(query)  # Second request fails
        
        # Test unsupported query
        specialized = SpecializedProvider("test", AssetType.CRYPTO)
        stock_query = DataQuery(asset=AssetType.STOCK)
        
        with pytest.raises(ValidationException):
            await specialized.get_data(stock_query)