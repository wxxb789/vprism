"""Tests for data provider abstraction interfaces."""

import pytest
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from unittest.mock import Mock, AsyncMock

from vprism.models.data import DataQuery, DataResponse, DataPoint, ProviderInfo, ResponseMetadata
from vprism.models.enums import AssetType, MarketType, TimeFrame, AuthType
from vprism.providers.base import (
    DataProvider,
    ProviderCapability,
    AuthConfig,
    RateLimitConfig,
    ProviderRegistry,
)


class TestAuthConfig:
    """Test authentication configuration."""

    def test_auth_config_api_key(self):
        """Test API key authentication configuration."""
        config = AuthConfig(
            auth_type=AuthType.API_KEY,
            config={"api_key": "test_key_123"}
        )
        
        assert config.auth_type == AuthType.API_KEY
        assert config.config["api_key"] == "test_key_123"

    def test_auth_config_bearer_token(self):
        """Test bearer token authentication configuration."""
        config = AuthConfig(
            auth_type=AuthType.BEARER_TOKEN,
            config={"token": "bearer_token_456"}
        )
        
        assert config.auth_type == AuthType.BEARER_TOKEN
        assert config.config["token"] == "bearer_token_456"

    def test_auth_config_oauth2(self):
        """Test OAuth2 authentication configuration."""
        config = AuthConfig(
            auth_type=AuthType.OAUTH2,
            config={
                "client_id": "client123",
                "client_secret": "secret456",
                "scope": "read_market_data"
            }
        )
        
        assert config.auth_type == AuthType.OAUTH2
        assert config.config["client_id"] == "client123"
        assert config.config["scope"] == "read_market_data"


class TestRateLimitConfig:
    """Test rate limit configuration."""

    def test_rate_limit_config_basic(self):
        """Test basic rate limit configuration."""
        config = RateLimitConfig(
            requests_per_minute=100,
            requests_per_hour=1000,
            burst_limit=10
        )
        
        assert config.requests_per_minute == 100
        assert config.requests_per_hour == 1000
        assert config.burst_limit == 10

    def test_rate_limit_config_unlimited(self):
        """Test unlimited rate limit configuration."""
        config = RateLimitConfig(
            requests_per_minute=None,
            requests_per_hour=None,
            burst_limit=None
        )
        
        assert config.requests_per_minute is None
        assert config.requests_per_hour is None
        assert config.burst_limit is None


class TestProviderCapability:
    """Test provider capability."""

    def test_provider_capability_creation(self):
        """Test provider capability creation."""
        capability = ProviderCapability(
            asset_types=[AssetType.STOCK, AssetType.ETF],
            markets=[MarketType.CN, MarketType.US],
            timeframes=[TimeFrame.DAY_1, TimeFrame.MINUTE_1],
            supports_real_time=True,
            supports_historical=True,
            max_symbols_per_request=100,
            min_date=datetime(2000, 1, 1),
            max_date=datetime(2024, 12, 31)
        )
        
        assert AssetType.STOCK in capability.asset_types
        assert MarketType.CN in capability.markets
        assert TimeFrame.DAY_1 in capability.timeframes
        assert capability.supports_real_time is True
        assert capability.supports_historical is True
        assert capability.max_symbols_per_request == 100

    def test_provider_capability_validation(self):
        """Test provider capability validation."""
        # Valid capability
        capability = ProviderCapability(
            asset_types=[AssetType.STOCK],
            markets=[MarketType.CN],
            timeframes=[TimeFrame.DAY_1]
        )
        assert capability is not None

        # Empty asset types should raise validation error
        with pytest.raises(ValueError):
            ProviderCapability(
                asset_types=[],
                markets=[MarketType.CN],
                timeframes=[TimeFrame.DAY_1]
            )


class TestDataProvider:
    """Test data provider abstract base class."""

    def test_abstract_methods(self):
        """Test that DataProvider has required abstract methods."""
        with pytest.raises(TypeError):
            # Cannot instantiate abstract class
            DataProvider()

    def test_concrete_provider_implementation(self):
        """Test concrete provider implementation."""
        
        class MockProvider(DataProvider):
            """Mock provider for testing."""
            
            def __init__(self):
                super().__init__(
                    name="mock_provider",
                    display_name="Mock Provider",
                    capability=ProviderCapability(
                        asset_types=[AssetType.STOCK],
                        markets=[MarketType.CN],
                        timeframes=[TimeFrame.DAY_1]
                    ),
                    auth_config=AuthConfig(
                        auth_type=AuthType.API_KEY,
                        config={"api_key": "test"}
                    ),
                    rate_limit=RateLimitConfig(
                        requests_per_minute=100,
                        requests_per_hour=1000
                    )
                )
            
            async def fetch_data(self, query: DataQuery) -> DataResponse:
                """Mock data fetching."""
                return DataResponse(
                    data=[
                        DataPoint(
                            symbol=query.symbols[0],
                            timestamp=datetime.now(),
                            close=Decimal("10.50")
                        )
                    ],
                    metadata=ResponseMetadata(total_records=1),
                    provider=ProviderInfo(name="mock", display_name="Mock"),
                    cached=False
                )
            
            async def check_health(self) -> Dict[str, Any]:
                """Mock health check."""
                return {"status": "healthy", "response_time_ms": 100}
        
        provider = MockProvider()
        assert provider.name == "mock_provider"
        assert provider.display_name == "Mock Provider"
        assert provider.capability.asset_types == [AssetType.STOCK]

    def test_can_handle_query(self):
        """Test query capability checking."""
        
        class TestProvider(DataProvider):
            def __init__(self):
                super().__init__(
                    name="test",
                    display_name="Test",
                    capability=ProviderCapability(
                        asset_types=[AssetType.STOCK],
                        markets=[MarketType.CN],
                        timeframes=[TimeFrame.DAY_1]
                    ),
                    auth_config=AuthConfig(
                        auth_type=AuthType.API_KEY,
                        config={"api_key": "test"}
                    )
                )
            
            async def fetch_data(self, query: DataQuery) -> DataResponse:
                return DataResponse(data=[], metadata=ResponseMetadata(), provider=ProviderInfo(name="test", display_name="Test"))
            
            async def check_health(self) -> Dict[str, Any]:
                return {"status": "healthy"}
        
        provider = TestProvider()
        
        # Query it can handle
        query = DataQuery(
            asset_type=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1
        )
        assert provider.can_handle_query(query) is True
        
        # Query it cannot handle (wrong asset type)
        query = DataQuery(
            asset_type=AssetType.CRYPTO,
            market=MarketType.CN,
            symbols=["BTC"]
        )
        assert provider.can_handle_query(query) is False
        
        # Query it cannot handle (wrong market)
        query = DataQuery(
            asset_type=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        assert provider.can_handle_query(query) is False

    def test_validate_query_with_limits(self):
        """Test query validation with symbol limits."""
        
        class LimitedProvider(DataProvider):
            def __init__(self):
                super().__init__(
                    name="limited",
                    display_name="Limited",
                    capability=ProviderCapability(
                        asset_types=[AssetType.STOCK],
                        markets=[MarketType.CN],
                        timeframes=[TimeFrame.DAY_1],
                        max_symbols_per_request=2
                    ),
                    auth_config=AuthConfig(
                        auth_type=AuthType.API_KEY,
                        config={"api_key": "test"}
                    )
                )
            
            async def fetch_data(self, query: DataQuery) -> DataResponse:
                return DataResponse(data=[], metadata=ResponseMetadata(), provider=ProviderInfo(name="test", display_name="Test"))
            
            async def check_health(self) -> Dict[str, Any]:
                return {"status": "healthy"}
        
        provider = LimitedProvider()
        
        # Valid query within limits
        query = DataQuery(
            asset_type=AssetType.STOCK,
            symbols=["000001", "600519"]
        )
        assert provider.can_handle_query(query) is True
        
        # Invalid query exceeding limits
        query = DataQuery(
            asset_type=AssetType.STOCK,
            symbols=["000001", "600519", "000002", "600000"]
        )
        assert provider.can_handle_query(query) is False


class TestProviderRegistry:
    """Test provider registry."""

    def test_registry_creation(self):
        """Test registry creation."""
        registry = ProviderRegistry()
        assert len(registry.providers) == 0

    def test_register_provider(self):
        """Test provider registration."""
        
        class TestProvider(DataProvider):
            def __init__(self):
                super().__init__(
                    name="test",
                    display_name="Test",
                    capability=ProviderCapability(
                        asset_types=[AssetType.STOCK],
                        markets=[MarketType.CN],
                        timeframes=[TimeFrame.DAY_1]
                    ),
                    auth_config=AuthConfig(
                        auth_type=AuthType.API_KEY,
                        config={"api_key": "test"}
                    )
                )
            
            async def fetch_data(self, query: DataQuery) -> DataResponse:
                return DataResponse(data=[], metadata=ResponseMetadata(), provider=ProviderInfo(name="test", display_name="Test"))
            
            async def check_health(self) -> Dict[str, Any]:
                return {"status": "healthy"}
        
        registry = ProviderRegistry()
        provider = TestProvider()
        
        registry.register(provider)
        assert len(registry.providers) == 1
        assert registry.providers["test"] == provider

    def test_get_provider(self):
        """Test getting provider by name."""
        
        class TestProvider(DataProvider):
            def __init__(self):
                super().__init__(
                    name="test_provider",
                    display_name="Test Provider",
                    capability=ProviderCapability(
                        asset_types=[AssetType.STOCK],
                        markets=[MarketType.CN],
                        timeframes=[TimeFrame.DAY_1]
                    ),
                    auth_config=AuthConfig(
                        auth_type=AuthType.API_KEY,
                        config={"api_key": "test"}
                    )
                )
            
            async def fetch_data(self, query: DataQuery) -> DataResponse:
                return DataResponse(data=[], metadata=ResponseMetadata(), provider=ProviderInfo(name="test", display_name="Test"))
            
            async def check_health(self) -> Dict[str, Any]:
                return {"status": "healthy"}
        
        registry = ProviderRegistry()
        provider = TestProvider()
        registry.register(provider)
        
        retrieved = registry.get("test_provider")
        assert retrieved == provider
        
        # Test non-existent provider
        assert registry.get("nonexistent") is None

    def test_find_suitable_providers(self):
        """Test finding suitable providers for a query."""
        
        class CNStockProvider(DataProvider):
            def __init__(self):
                super().__init__(
                    name="cn_stocks",
                    display_name="CN Stocks",
                    capability=ProviderCapability(
                        asset_types=[AssetType.STOCK],
                        markets=[MarketType.CN],
                        timeframes=[TimeFrame.DAY_1]
                    ),
                    auth_config=AuthConfig(
                        auth_type=AuthType.API_KEY,
                        config={"api_key": "test"}
                    )
                )
            
            async def fetch_data(self, query: DataQuery) -> DataResponse:
                return DataResponse(data=[], metadata=ResponseMetadata(), provider=ProviderInfo(name="test", display_name="Test"))
            
            async def check_health(self) -> Dict[str, Any]:
                return {"status": "healthy"}
        
        class USStockProvider(DataProvider):
            def __init__(self):
                super().__init__(
                    name="us_stocks",
                    display_name="US Stocks",
                    capability=ProviderCapability(
                        asset_types=[AssetType.STOCK],
                        markets=[MarketType.US],
                        timeframes=[TimeFrame.DAY_1]
                    ),
                    auth_config=AuthConfig(
                        auth_type=AuthType.API_KEY,
                        config={"api_key": "test"}
                    )
                )
            
            async def fetch_data(self, query: DataQuery) -> DataResponse:
                return DataResponse(data=[], metadata=ResponseMetadata(), provider=ProviderInfo(name="test", display_name="Test"))
            
            async def check_health(self) -> Dict[str, Any]:
                return {"status": "healthy"}
        
        registry = ProviderRegistry()
        cn_provider = CNStockProvider()
        us_provider = USStockProvider()
        
        registry.register(cn_provider)
        registry.register(us_provider)
        
        # Query for CN stocks
        cn_query = DataQuery(
            asset_type=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"]
        )
        
        suitable = registry.find_suitable_providers(cn_query)
        assert len(suitable) == 1
        assert suitable[0] == cn_provider
        
        # Query for US stocks
        us_query = DataQuery(
            asset_type=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"]
        )
        
        suitable = registry.find_suitable_providers(us_query)
        assert len(suitable) == 1
        assert suitable[0] == us_provider

    def test_list_providers(self):
        """Test listing all providers."""
        
        class Provider1(DataProvider):
            def __init__(self):
                super().__init__(
                    name="provider1",
                    display_name="Provider 1",
                    capability=ProviderCapability(
                        asset_types=[AssetType.STOCK],
                        markets=[MarketType.CN],
                        timeframes=[TimeFrame.DAY_1]
                    ),
                    auth_config=AuthConfig(
                        auth_type=AuthType.API_KEY,
                        config={"api_key": "test"}
                    )
                )
            
            async def fetch_data(self, query: DataQuery) -> DataResponse:
                return DataResponse(data=[], metadata=ResponseMetadata(), provider=ProviderInfo(name="test", display_name="Test"))
            
            async def check_health(self) -> Dict[str, Any]:
                return {"status": "healthy"}
        
        class Provider2(DataProvider):
            def __init__(self):
                super().__init__(
                    name="provider2",
                    display_name="Provider 2",
                    capability=ProviderCapability(
                        asset_types=[AssetType.CRYPTO],
                        markets=[MarketType.US],
                        timeframes=[TimeFrame.MINUTE_1]
                    ),
                    auth_config=AuthConfig(
                        auth_type=AuthType.BEARER_TOKEN,
                        config={"token": "test"}
                    )
                )
            
            async def fetch_data(self, query: DataQuery) -> DataResponse:
                return DataResponse(data=[], metadata=ResponseMetadata(), provider=ProviderInfo(name="test", display_name="Test"))
            
            async def check_health(self) -> Dict[str, Any]:
                return {"status": "healthy"}
        
        registry = ProviderRegistry()
        registry.register(Provider1())
        registry.register(Provider2())
        
        providers = registry.list_providers()
        assert len(providers) == 2
        assert "provider1" in providers
        assert "provider2" in providers