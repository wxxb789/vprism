"""
Mock data providers for testing and development.

This module provides comprehensive mock implementations of data providers
that can be used for testing, development, and demonstration purposes.
These mocks simulate various real-world scenarios and edge cases.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

from vprism.core.exceptions import (
    ProviderException,
    RateLimitException,
    ValidationException,
)
from vprism.core.interfaces import DataProvider
from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    MarketType,
    ProviderInfo,
    ResponseMetadata,
    TimeFrame,
)


class MockDataProvider(DataProvider):
    """
    Comprehensive mock data provider for testing.

    This mock provider can simulate various scenarios including:
    - Successful data retrieval
    - Rate limiting
    - Provider failures
    - Health check failures
    - Different asset type support
    """

    def __init__(
        self,
        name: str,
        supported_assets: set[AssetType] | None = None,
        supported_markets: set[MarketType] | None = None,
        can_handle: bool = True,
        is_healthy: bool = True,
        rate_limit: int = 1000,
        simulate_delay: bool = False,
        failure_rate: float = 0.0,
        version: str = "1.0.0",
        cost: str = "free",
    ):
        """
        Initialize mock data provider.

        Args:
            name: Provider name
            supported_assets: Set of supported asset types
            supported_markets: Set of supported markets
            can_handle: Whether provider can handle queries
            is_healthy: Whether provider is healthy
            rate_limit: Rate limit per minute
            simulate_delay: Whether to simulate network delays
            failure_rate: Probability of random failures (0.0-1.0)
            version: Provider version
            cost: Cost tier
        """
        self._name = name
        self._supported_assets = supported_assets or {AssetType.STOCK}
        self._supported_markets = supported_markets or {MarketType.US, MarketType.CN}
        self._can_handle = can_handle
        self._is_healthy = is_healthy
        self._rate_limit = rate_limit
        self._simulate_delay = simulate_delay
        self._failure_rate = failure_rate
        self._request_count = 0
        self._last_reset = datetime.now()

        self._info = ProviderInfo(
            name=name,
            version=version,
            url=f"https://api.{name.lower().replace('_', '-')}.com",
            rate_limit=rate_limit,
            cost=cost,
        )

    @property
    def name(self) -> str:
        """Provider name identifier."""
        return self._name

    @property
    def info(self) -> ProviderInfo:
        """Provider information and metadata."""
        return self._info

    @property
    def supported_assets(self) -> set[AssetType]:
        """Set of asset types supported by this provider."""
        return self._supported_assets.copy()

    async def get_data(self, query: DataQuery) -> DataResponse:
        """
        Retrieve data based on the provided query.

        Args:
            query: The data query specification

        Returns:
            DataResponse containing the requested data

        Raises:
            ProviderException: When provider-specific errors occur
            ValidationException: When query validation fails
            RateLimitException: When rate limit is exceeded
        """
        await self._check_preconditions(query)

        if self._simulate_delay:
            await asyncio.sleep(random.uniform(0.1, 0.5))

        # Generate mock data
        data_points = self._generate_mock_data(query)

        metadata = ResponseMetadata(
            execution_time_ms=random.uniform(50, 200),
            record_count=len(data_points),
            cache_hit=False,
            data_quality_score=random.uniform(0.8, 1.0),
        )

        return DataResponse(
            data=data_points,
            metadata=metadata,
            source=self._info,
            query=query,
        )

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """
        Stream real-time data based on the provided query.

        Args:
            query: The data query specification

        Yields:
            DataPoint: Individual data points as they become available

        Raises:
            ProviderException: When provider-specific errors occur
            ValidationException: When query validation fails
        """
        await self._check_preconditions(query)

        # Simulate streaming data
        symbols = query.symbols or ["MOCK001", "MOCK002"]

        for i in range(10):  # Stream 10 data points
            if self._simulate_delay:
                await asyncio.sleep(random.uniform(0.1, 1.0))

            for symbol in symbols:
                yield self._generate_single_data_point(symbol)

    async def health_check(self) -> bool:
        """
        Check if the provider is healthy and available.

        Returns:
            bool: True if provider is healthy, False otherwise
        """
        if self._simulate_delay:
            await asyncio.sleep(random.uniform(0.01, 0.1))

        # Simulate occasional health check failures
        if random.random() < (1 - self._failure_rate):
            return self._is_healthy
        else:
            return False

    def can_handle_query(self, query: DataQuery) -> bool:
        """
        Check if this provider can handle the given query.

        Args:
            query: The data query to evaluate

        Returns:
            bool: True if provider can handle the query
        """
        if not self._can_handle:
            return False

        # Check asset type support
        if query.asset not in self._supported_assets:
            return False

        # Check market support
        if query.market and query.market not in self._supported_markets:
            return False

        return True

    async def _check_preconditions(self, query: DataQuery) -> None:
        """Check preconditions before processing query."""
        # Check rate limiting
        await self._check_rate_limit()

        # Simulate random failures
        if random.random() < self._failure_rate:
            raise ProviderException(
                f"Random failure in provider {self._name}",
                provider=self._name,
                error_code="PROVIDER_FAILURE",
                details={"query": query.cache_key()},
            )

        # Validate query
        if not self.can_handle_query(query):
            raise ValidationException(
                f"Provider {self._name} cannot handle this query",
                details={
                    "provider": self._name,
                    "supported_assets": [a.value for a in self._supported_assets],
                    "supported_markets": [m.value for m in self._supported_markets],
                    "query_asset": query.asset.value,
                    "query_market": query.market.value if query.market else None,
                },
            )

    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting."""
        now = datetime.now()

        # Reset counter every minute
        if (now - self._last_reset).total_seconds() >= 60:
            self._request_count = 0
            self._last_reset = now

        self._request_count += 1

        if self._request_count > self._rate_limit:
            retry_after = int(
                (self._last_reset + timedelta(minutes=1) - now).total_seconds()
            )
            raise RateLimitException(
                provider=self._name,
                retry_after=retry_after,
                details={
                    "rate_limit": self._rate_limit,
                    "current_count": self._request_count,
                    "reset_time": (self._last_reset + timedelta(minutes=1)).isoformat(),
                },
            )

    def _generate_mock_data(self, query: DataQuery) -> list[DataPoint]:
        """Generate mock data points based on query."""
        symbols = query.symbols or ["MOCK001"]
        limit = query.limit or 100

        data_points = []
        base_time = query.start or (datetime.now() - timedelta(days=30))

        for i in range(min(limit, 1000)):  # Cap at 1000 points
            for symbol in symbols:
                timestamp = base_time + timedelta(days=i)
                if query.end and timestamp > query.end:
                    break

                # Ensure timestamp is in the past
                if timestamp > datetime.now():
                    timestamp = datetime.now() - timedelta(
                        minutes=random.randint(1, 60)
                    )

                data_points.append(self._generate_single_data_point(symbol, timestamp))

        return data_points

    def _generate_single_data_point(
        self, symbol: str, timestamp: datetime | None = None
    ) -> DataPoint:
        """Generate a single mock data point."""
        if timestamp is None:
            # Use a past timestamp to avoid validation errors
            timestamp = datetime.now() - timedelta(minutes=random.randint(1, 60))

        base_price = Decimal("100.00")
        volatility = Decimal("0.02")  # 2% volatility

        # Generate realistic OHLCV data
        open_price = base_price + Decimal(str(random.uniform(-5, 5)))
        high_price = open_price + Decimal(str(random.uniform(0, 3)))
        low_price = open_price - Decimal(str(random.uniform(0, 3)))
        close_price = open_price + Decimal(str(random.uniform(-2, 2)))
        volume = Decimal(str(random.randint(100000, 10000000)))
        amount = close_price * volume

        return DataPoint(
            symbol=symbol,
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            amount=amount,
            extra_fields={
                "provider": self._name,
                "data_quality": random.uniform(0.8, 1.0),
                "source_timestamp": timestamp.isoformat(),
            },
        )


class AlwaysFailingProvider(MockDataProvider):
    """Mock provider that always fails - useful for testing error handling."""

    def __init__(self, name: str = "always_failing"):
        super().__init__(name, is_healthy=False, failure_rate=1.0)

    async def get_data(self, query: DataQuery) -> DataResponse:
        raise ProviderException(
            f"Provider {self._name} always fails",
            provider=self._name,
            error_code="PROVIDER_ALWAYS_FAILS",
        )

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        raise ProviderException(
            f"Provider {self._name} always fails",
            provider=self._name,
            error_code="PROVIDER_ALWAYS_FAILS",
        )
        yield  # This will never be reached, but needed for type checking

    async def health_check(self) -> bool:
        return False


class RateLimitedProvider(MockDataProvider):
    """Mock provider with very low rate limits - useful for testing rate limiting."""

    def __init__(self, name: str = "rate_limited", rate_limit: int = 5):
        super().__init__(name, rate_limit=rate_limit)


class SlowProvider(MockDataProvider):
    """Mock provider with slow responses - useful for testing timeouts."""

    def __init__(self, name: str = "slow_provider", delay_seconds: float = 2.0):
        super().__init__(name, simulate_delay=True)
        self._delay_seconds = delay_seconds

    async def get_data(self, query: DataQuery) -> DataResponse:
        await asyncio.sleep(self._delay_seconds)
        return await super().get_data(query)

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        await asyncio.sleep(self._delay_seconds)
        async for point in super().stream_data(query):
            yield point

    async def health_check(self) -> bool:
        await asyncio.sleep(self._delay_seconds)
        return await super().health_check()


class SpecializedProvider(MockDataProvider):
    """Mock provider specialized for specific asset types."""

    def __init__(
        self,
        name: str,
        specialized_asset: AssetType,
        specialized_market: MarketType | None = None,
    ):
        super().__init__(
            name,
            supported_assets={specialized_asset},
            supported_markets={specialized_market} if specialized_market else None,
        )
        self._specialized_asset = specialized_asset
        self._specialized_market = specialized_market


# Pre-configured provider instances for common testing scenarios
MOCK_STOCK_PROVIDER = MockDataProvider(
    "mock_stock_provider",
    supported_assets={AssetType.STOCK},
    supported_markets={MarketType.US, MarketType.CN},
)

MOCK_CRYPTO_PROVIDER = MockDataProvider(
    "mock_crypto_provider",
    supported_assets={AssetType.CRYPTO},
    supported_markets={MarketType.GLOBAL},
)

MOCK_BOND_PROVIDER = MockDataProvider(
    "mock_bond_provider",
    supported_assets={AssetType.BOND},
    supported_markets={MarketType.US, MarketType.EU},
)

MOCK_MULTI_ASSET_PROVIDER = MockDataProvider(
    "mock_multi_asset_provider",
    supported_assets={AssetType.STOCK, AssetType.ETF, AssetType.FUND},
    supported_markets={MarketType.US, MarketType.CN, MarketType.HK},
)


def create_test_provider_suite() -> dict[str, DataProvider]:
    """
    Create a comprehensive suite of test providers.

    Returns:
        Dictionary mapping provider names to provider instances
    """
    return {
        "healthy_stock": MOCK_STOCK_PROVIDER,
        "healthy_crypto": MOCK_CRYPTO_PROVIDER,
        "healthy_bond": MOCK_BOND_PROVIDER,
        "multi_asset": MOCK_MULTI_ASSET_PROVIDER,
        "always_failing": AlwaysFailingProvider(),
        "rate_limited": RateLimitedProvider(),
        "slow_provider": SlowProvider(),
        "cn_stocks": SpecializedProvider("cn_stocks", AssetType.STOCK, MarketType.CN),
        "us_options": SpecializedProvider(
            "us_options", AssetType.OPTIONS, MarketType.US
        ),
    }
