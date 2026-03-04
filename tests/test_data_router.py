"""Test data router routing scenarios and failover mechanisms."""

from typing import Any
from unittest.mock import Mock

import pytest

from vprism.core.data.providers.base import DataProvider
from vprism.core.data.routing import DataRouter
from vprism.core.exceptions import NoCapableProviderError
from vprism.core.models import AssetType, DataQuery, MarketType, TimeFrame


class MockProvider(DataProvider):
    def __init__(self, name: str, capability: Any) -> None:
        from vprism.core.data.providers.base import (
            AuthConfig,
            AuthType,
            RateLimitConfig,
        )

        super().__init__(
            name=name,
            auth_config=AuthConfig(auth_type=AuthType.NONE, credentials={}),
            rate_limit=RateLimitConfig(
                requests_per_minute=100,
                requests_per_hour=1000,
                requests_per_day=10000,
                concurrent_requests=5,
            ),
        )
        self.name = name
        self._capability = capability

    def _discover_capability(self) -> Any:
        return self._capability

    async def get_data(self, query: DataQuery) -> Any:
        return None

    async def stream_data(self, query: DataQuery) -> Any:
        yield None

    async def authenticate(self) -> bool:
        return True


class TestDataRouter:
    """Test data router functionality."""

    @pytest.fixture
    def mock_registry(self, sample_providers: list[MockProvider]) -> Mock:
        """Create a mock provider registry."""
        registry = Mock()
        registry.find_capable_providers = Mock()
        registry.mark_unhealthy = Mock()
        registry.mark_healthy = Mock()
        registry.providers = {p.name: p for p in sample_providers}
        registry.get_all_providers = Mock(return_value=sample_providers)
        return registry

    @pytest.fixture
    def sample_providers(self) -> list[MockProvider]:
        """Create sample providers."""
        from vprism.core.data.providers.base import ProviderCapability

        return [
            MockProvider(
                "tushare",
                ProviderCapability(
                    supported_assets={"stock"},
                    supported_markets={"cn"},
                    supported_timeframes={"1d", "1m"},
                    max_symbols_per_request=100,
                    supports_real_time=True,
                    supports_historical=True,
                    data_delay_seconds=1,
                ),
            ),
            MockProvider(
                "yahoo",
                ProviderCapability(
                    supported_assets={"stock", "etf"},
                    supported_markets={"us", "hk"},
                    supported_timeframes={"1d", "1w", "1m"},
                    max_symbols_per_request=200,
                    supports_real_time=True,
                    supports_historical=True,
                    data_delay_seconds=15,
                ),
            ),
            MockProvider(
                "alpha_vantage",
                ProviderCapability(
                    supported_assets={"stock", "forex"},
                    supported_markets={"us", "global"},
                    supported_timeframes={"1d", "1m", "5m"},
                    max_symbols_per_request=50,
                    supports_real_time=False,
                    supports_historical=True,
                    data_delay_seconds=60,
                ),
            ),
        ]

    @pytest.mark.asyncio
    async def test_route_single_provider(self, mock_registry: Mock, sample_providers: list[MockProvider]) -> None:
        """Test routing with a single capable provider."""
        mock_registry.find_capable_providers.return_value = [sample_providers[0]]

        router = DataRouter(mock_registry)
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"])

        provider = await router.route_query(query)

        assert provider.name == "tushare"
        mock_registry.find_capable_providers.assert_called_once_with(query)

    @pytest.mark.asyncio
    async def test_route_multiple_providers_select_best(self, mock_registry: Mock, sample_providers: list[MockProvider]) -> None:
        """Test selecting best provider among multiple capable ones."""
        mock_registry.providers = {p.name: p for p in sample_providers}
        capable_providers = [p for p in sample_providers if p.name in ["yahoo", "alpha_vantage"]]
        mock_registry.find_capable_providers.return_value = capable_providers

        router = DataRouter(mock_registry)
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        provider = await router.route_query(query)

        # yahoo has lower latency (15s vs 60s)
        assert provider.name == "yahoo"

    @pytest.mark.asyncio
    async def test_route_no_capable_provider(self, mock_registry: Mock) -> None:
        """Test routing when no provider can handle the query."""
        mock_registry.find_capable_providers.return_value = []

        router = DataRouter(mock_registry)
        query = DataQuery(asset=AssetType.CRYPTO, market=MarketType.GLOBAL)

        with pytest.raises(NoCapableProviderError) as exc_info:
            await router.route_query(query)

        assert "No provider can handle query" in str(exc_info.value)

    def test_update_provider_score_success(self, mock_registry: Mock) -> None:
        """Test updating provider score on success."""
        router = DataRouter(mock_registry)
        router.provider_scores["tushare"] = 1.0

        router.update_provider_score("tushare", success=True, latency_ms=50)

        assert router.provider_scores["tushare"] > 1.0

    def test_update_provider_score_failure(self, mock_registry: Mock) -> None:
        """Test updating provider score on failure."""
        router = DataRouter(mock_registry)
        router.provider_scores["tushare"] = 1.0

        router.update_provider_score("tushare", success=False, latency_ms=0)

        assert router.provider_scores["tushare"] < 1.0
        assert router.provider_scores["tushare"] >= 0.1

    def test_update_provider_score_bounds(self, mock_registry: Mock) -> None:
        """Test score clamping to [0.1, 2.0]."""
        router = DataRouter(mock_registry)

        # Upper bound
        router.provider_scores["tushare"] = 2.0
        router.update_provider_score("tushare", success=True, latency_ms=10)
        assert router.provider_scores["tushare"] <= 2.0

        # Lower bound
        router.provider_scores["tushare"] = 0.1
        router.update_provider_score("tushare", success=False, latency_ms=0)
        assert router.provider_scores["tushare"] >= 0.1

    @pytest.mark.asyncio
    async def test_complex_query_routing(self, mock_registry: Mock, sample_providers: list[MockProvider]) -> None:
        """Test routing for a complex multi-symbol minute-level query."""
        capable_providers = [sample_providers[2]]  # alpha_vantage
        mock_registry.find_capable_providers.return_value = capable_providers

        router = DataRouter(mock_registry)
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            timeframe=TimeFrame.MINUTE_1,
            symbols=["AAPL", "GOOGL"],
        )

        provider = await router.route_query(query)

        assert provider.name == "alpha_vantage"
