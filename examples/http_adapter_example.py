"""
Example demonstrating the HTTP adapter framework usage.

This example shows how to create a custom HTTP-based data provider
using the vprism HTTP adapter framework.
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

import httpx

from vprism.core.http_adapter import (
    HttpConfig,
    HttpDataProvider,
    RetryConfig,
    create_http_config,
    create_retry_config,
)
from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    MarketType,
    TimeFrame,
)
from vprism.core.provider_abstraction import (
    AuthConfig,
    AuthType,
    ProviderCapability,
    RateLimitConfig,
)


class ExampleHttpProvider(HttpDataProvider):
    """
    Example HTTP data provider implementation.
    
    This demonstrates how to create a custom provider using the
    HTTP adapter framework with authentication, rate limiting,
    and error handling.
    """

    def __init__(self):
        """Initialize the example provider."""
        # Configure HTTP settings
        http_config = create_http_config(
            base_url="https://api.example.com/v1",
            timeout=30.0,
            user_agent="vprism-example/1.0.0",
        )

        # Configure authentication (API key example)
        auth_config = AuthConfig(
            auth_type=AuthType.API_KEY,
            credentials={"api_key": "your-api-key-here"}
        )

        # Configure rate limiting
        rate_limit = RateLimitConfig(
            requests_per_minute=60,
            requests_per_hour=1000,
            concurrent_requests=5,
        )

        # Configure retry behavior
        retry_config = create_retry_config(
            max_retries=3,
            backoff_factor=2.0,
        )

        super().__init__(
            provider_name="example_http",
            http_config=http_config,
            auth_config=auth_config,
            rate_limit=rate_limit,
            retry_config=retry_config,
        )

    @property
    def name(self) -> str:
        """Provider name identifier."""
        return "example_http"

    def _discover_capability(self) -> ProviderCapability:
        """Discover and return provider capabilities."""
        return ProviderCapability(
            supported_assets={AssetType.STOCK, AssetType.ETF},
            supported_markets={MarketType.US, MarketType.CN},
            supported_timeframes={
                TimeFrame.MINUTE_1,
                TimeFrame.MINUTE_5,
                TimeFrame.HOUR_1,
                TimeFrame.DAY_1,
            },
            max_symbols_per_request=100,
            supports_real_time=True,
            supports_historical=True,
            data_delay_seconds=0,
            max_history_days=365,
        )

    def _build_request_url(self, query: DataQuery) -> str:
        """Build request URL for the given query."""
        # Example URL construction
        asset_path = query.asset.value
        return f"/data/{asset_path}"

    def _build_request_params(self, query: DataQuery) -> Dict[str, Any]:
        """Build request parameters for the given query."""
        params = {}

        # Add symbols
        if query.symbols:
            params["symbols"] = ",".join(query.symbols)

        # Add timeframe
        if query.timeframe:
            params["interval"] = query.timeframe.value

        # Add date range
        if query.start:
            params["start"] = query.start.isoformat()
        if query.end:
            params["end"] = query.end.isoformat()

        # Add market
        if query.market:
            params["market"] = query.market.value

        return params

    async def _parse_response(
        self, response: httpx.Response, query: DataQuery
    ) -> List[DataPoint]:
        """Parse HTTP response into data points."""
        # Example JSON response parsing
        try:
            data = response.json()
            data_points = []

            # Assume response format: {"data": [{"symbol": "AAPL", "timestamp": "...", ...}]}
            for item in data.get("data", []):
                data_point = DataPoint(
                    symbol=item["symbol"],
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    open=Decimal(str(item.get("open", 0))),
                    high=Decimal(str(item.get("high", 0))),
                    low=Decimal(str(item.get("low", 0))),
                    close=Decimal(str(item.get("close", 0))),
                    volume=Decimal(str(item.get("volume", 0))),
                    amount=Decimal(str(item.get("amount", 0))),
                    extra_fields=item.get("extra", {}),
                )
                data_points.append(data_point)

            return data_points

        except Exception as e:
            # Handle parsing errors
            raise ValueError(f"Failed to parse response: {e}")


async def main():
    """Demonstrate the HTTP adapter framework usage."""
    print("HTTP Adapter Framework Example")
    print("=" * 40)

    # Create provider instance
    provider = ExampleHttpProvider()

    # Display provider capabilities
    capability = provider.capability
    print(f"Provider: {provider.name}")
    print(f"Supported assets: {capability.supported_assets}")
    print(f"Supported markets: {capability.supported_markets}")
    print(f"Max symbols per request: {capability.max_symbols_per_request}")
    print(f"Supports real-time: {capability.supports_real_time}")
    print()

    # Create a sample query (using recent dates)
    from datetime import timedelta
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days
    
    query = DataQuery(
        asset=AssetType.STOCK,
        market=MarketType.US,
        symbols=["AAPL", "GOOGL"],
        timeframe=TimeFrame.DAY_1,
        start=start_date,
        end=end_date,
    )

    print(f"Sample query: {query.asset.value} data for {query.symbols}")
    print(f"Can handle query: {provider.can_handle_query(query)}")
    print()

    # Test authentication (this would normally connect to a real API)
    print("Testing authentication...")
    try:
        # Note: This will fail with a real API call since we're using example.com
        # In a real implementation, you would use actual API endpoints
        auth_result = await provider._authenticate()
        print(f"Authentication result: {auth_result}")
    except Exception as e:
        print(f"Authentication test failed (expected): {e}")

    print()

    # Test health check
    print("Testing health check...")
    try:
        health_result = await provider.health_check()
        print(f"Health check result: {health_result}")
    except Exception as e:
        print(f"Health check failed (expected): {e}")

    print()

    # Demonstrate configuration
    print("HTTP Configuration:")
    print(f"  Base URL: {provider.http_config.base_url}")
    print(f"  Timeout: {provider.http_config.timeout}s")
    print(f"  User Agent: {provider.http_config.user_agent}")
    print()

    print("Rate Limiting:")
    print(f"  Requests per minute: {provider.rate_limit.requests_per_minute}")
    print(f"  Requests per hour: {provider.rate_limit.requests_per_hour}")
    print(f"  Concurrent requests: {provider.rate_limit.concurrent_requests}")
    print()

    print("Retry Configuration:")
    print(f"  Max retries: {provider.retry_config.max_retries}")
    print(f"  Backoff factor: {provider.retry_config.backoff_factor}")
    print(f"  Retry on status: {provider.retry_config.retry_on_status}")
    print()

    # Clean up
    await provider.close()
    print("Provider closed successfully.")


if __name__ == "__main__":
    asyncio.run(main())