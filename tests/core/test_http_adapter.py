"""
Tests for HTTP adapter framework.

This module contains comprehensive tests for the HTTP client and provider
adapter framework, including authentication, rate limiting, retry mechanisms,
and error handling. Following TDD principles with 90% coverage target.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from vprism.core.exceptions import (
    AuthenticationException,
    ProviderException,
    RateLimitException,
)
from vprism.core.http_adapter import (
    HttpClient,
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
    DataResponse,
    MarketType,
    TimeFrame,
)
from vprism.core.provider_abstraction import (
    AuthConfig,
    AuthType,
    ProviderCapability,
    RateLimitConfig,
)


class TestHttpConfig:
    """Test HttpConfig data class."""

    def test_http_config_creation(self):
        """Test creating HttpConfig with all parameters."""
        config = HttpConfig(
            base_url="https://api.example.com",
            timeout=30.0,
            max_redirects=5,
            verify_ssl=True,
            user_agent="test-agent/1.0",
            headers={"Custom-Header": "value"},
        )

        assert config.base_url == "https://api.example.com"
        assert config.timeout == 30.0
        assert config.max_redirects == 5
        assert config.verify_ssl is True
        assert config.user_agent == "test-agent/1.0"
        assert config.headers["Custom-Header"] == "value"

    def test_http_config_defaults(self):
        """Test HttpConfig with default values."""
        config = HttpConfig(base_url="https://api.example.com")

        assert config.base_url == "https://api.example.com"
        assert config.timeout == 30.0
        assert config.max_redirects == 5
        assert config.verify_ssl is True
        assert config.user_agent == "vprism/1.0.0"
        assert config.headers == {}

    def test_http_config_validation_empty_url(self):
        """Test HttpConfig validation fails with empty base_url."""
        with pytest.raises(ValueError, match="base_url cannot be empty"):
            HttpConfig(base_url="")

    def test_http_config_validation_negative_timeout(self):
        """Test HttpConfig validation fails with negative timeout."""
        with pytest.raises(ValueError, match="timeout must be positive"):
            HttpConfig(base_url="https://api.example.com", timeout=-1.0)

    def test_http_config_validation_negative_redirects(self):
        """Test HttpConfig validation fails with negative max_redirects."""
        with pytest.raises(ValueError, match="max_redirects must be non-negative"):
            HttpConfig(base_url="https://api.example.com", max_redirects=-1)


class TestRetryConfig:
    """Test RetryConfig data class."""

    def test_retry_config_creation(self):
        """Test creating RetryConfig with all parameters."""
        config = RetryConfig(
            max_retries=5,
            backoff_factor=1.5,
            retry_on_status=[429, 502],
            retry_on_exceptions=[httpx.TimeoutException],
        )

        assert config.max_retries == 5
        assert config.backoff_factor == 1.5
        assert config.retry_on_status == [429, 502]
        assert config.retry_on_exceptions == [httpx.TimeoutException]

    def test_retry_config_defaults(self):
        """Test RetryConfig with default values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.backoff_factor == 2.0
        assert 429 in config.retry_on_status
        assert 502 in config.retry_on_status
        assert httpx.TimeoutException in config.retry_on_exceptions

    def test_retry_config_validation_negative_retries(self):
        """Test RetryConfig validation fails with negative max_retries."""
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            RetryConfig(max_retries=-1)

    def test_retry_config_validation_zero_backoff(self):
        """Test RetryConfig validation fails with zero backoff_factor."""
        with pytest.raises(ValueError, match="backoff_factor must be positive"):
            RetryConfig(backoff_factor=0.0)


class TestHttpClient:
    """Test HttpClient class."""

    def test_http_client_initialization(self):
        """Test HttpClient initialization."""
        http_config = HttpConfig(base_url="https://api.example.com")
        auth_config = AuthConfig(AuthType.NONE, {})
        rate_limit = RateLimitConfig(60, 3600)

        client = HttpClient(http_config, auth_config, rate_limit)

        assert client.http_config == http_config
        assert client.auth_config == auth_config
        assert client.rate_limit == rate_limit
        assert client._client is None

    @pytest.mark.asyncio
    async def test_http_client_context_manager(self):
        """Test HttpClient as async context manager."""
        http_config = HttpConfig(base_url="https://api.example.com")
        auth_config = AuthConfig(AuthType.NONE, {})
        rate_limit = RateLimitConfig(60, 3600)

        client = HttpClient(http_config, auth_config, rate_limit)

        async with client as c:
            assert c is client
            assert client._client is not None

        # Client should be closed after context exit
        assert client._client is None

    @pytest.mark.asyncio
    async def test_http_client_ensure_client(self):
        """Test HTTP client initialization."""
        http_config = HttpConfig(
            base_url="https://api.example.com",
            user_agent="test-agent",
            headers={"Custom": "header"},
        )
        auth_config = AuthConfig(
            AuthType.API_KEY, credentials={"api_key": "test_key"}
        )
        rate_limit = RateLimitConfig(60, 3600)

        client = HttpClient(http_config, auth_config, rate_limit)

        await client._ensure_client()

        assert client._client is not None
        assert isinstance(client._client, httpx.AsyncClient)

        # Check that headers are properly set
        expected_headers = {
            "User-Agent": "test-agent",
            "Custom": "header",
            "X-API-Key": "test_key",
        }
        
        for key, value in expected_headers.items():
            assert client._client.headers.get(key) == value

        await client.close()

    def test_http_client_rate_limit_check(self):
        """Test rate limit checking."""
        http_config = HttpConfig(base_url="https://api.example.com")
        auth_config = AuthConfig(AuthType.NONE, {})
        rate_limit = RateLimitConfig(requests_per_minute=10, requests_per_hour=100)

        client = HttpClient(http_config, auth_config, rate_limit)

        # Empty history should pass
        assert client._check_rate_limit() is True

        # Add requests within limit
        now = datetime.now()
        client._request_history = [now - timedelta(seconds=i) for i in range(5)]
        assert client._check_rate_limit() is True

        # Add requests exceeding limit
        client._request_history = [now - timedelta(seconds=i) for i in range(15)]
        assert client._check_rate_limit() is False

    def test_http_client_record_request(self):
        """Test request recording for rate limiting."""
        http_config = HttpConfig(base_url="https://api.example.com")
        auth_config = AuthConfig(AuthType.NONE, {})
        rate_limit = RateLimitConfig(60, 3600)

        client = HttpClient(http_config, auth_config, rate_limit)

        initial_count = len(client._request_history)
        client._record_request()

        assert len(client._request_history) == initial_count + 1
        assert isinstance(client._request_history[-1], datetime)

    @pytest.mark.asyncio
    async def test_http_client_wait_for_rate_limit(self):
        """Test waiting for rate limit."""
        http_config = HttpConfig(base_url="https://api.example.com")
        auth_config = AuthConfig(AuthType.NONE, {})
        rate_limit = RateLimitConfig(requests_per_minute=60, requests_per_hour=3600)

        client = HttpClient(http_config, auth_config, rate_limit)

        # Mock rate limit exceeded
        now = datetime.now()
        client._request_history = [now - timedelta(seconds=i) for i in range(70)]

        start_time = datetime.now()
        await client._wait_for_rate_limit()
        end_time = datetime.now()

        # Should have waited at least the minimum delay
        elapsed = (end_time - start_time).total_seconds()
        assert elapsed >= 0.9  # Allow some tolerance for timing

    @pytest.mark.asyncio
    async def test_http_client_request_methods(self):
        """Test HTTP request methods."""
        http_config = HttpConfig(base_url="https://httpbin.org")
        auth_config = AuthConfig(AuthType.NONE, {})
        rate_limit = RateLimitConfig(60, 3600)
        retry_config = RetryConfig(max_retries=1)

        client = HttpClient(http_config, auth_config, rate_limit, retry_config)

        # Mock the actual HTTP client to avoid real requests
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.request.return_value = mock_response

        client._client = mock_client

        # Test different HTTP methods
        await client.get("/get")
        mock_client.request.assert_called_with("GET", "/get")

        await client.post("/post", json={"key": "value"})
        mock_client.request.assert_called_with("POST", "/post", json={"key": "value"})

        await client.put("/put")
        mock_client.request.assert_called_with("PUT", "/put")

        await client.delete("/delete")
        mock_client.request.assert_called_with("DELETE", "/delete")

    @pytest.mark.asyncio
    async def test_http_client_retry_on_status_code(self):
        """Test retry mechanism on specific status codes."""
        http_config = HttpConfig(base_url="https://api.example.com")
        auth_config = AuthConfig(AuthType.NONE, {})
        rate_limit = RateLimitConfig(60, 3600)
        retry_config = RetryConfig(max_retries=2, backoff_factor=1.1)

        client = HttpClient(http_config, auth_config, rate_limit, retry_config)

        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 502  # Should trigger retry
        mock_client.request.return_value = mock_response

        client._client = mock_client

        # Should retry and eventually raise exception
        with pytest.raises(ProviderException):
            await client.get("/test")

        # Should have made multiple attempts
        assert mock_client.request.call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_http_client_retry_on_exception(self):
        """Test retry mechanism on exceptions."""
        http_config = HttpConfig(base_url="https://api.example.com")
        auth_config = AuthConfig(AuthType.NONE, {})
        rate_limit = RateLimitConfig(60, 3600)
        retry_config = RetryConfig(max_retries=2, backoff_factor=1.1)

        client = HttpClient(http_config, auth_config, rate_limit, retry_config)

        # Mock HTTP client to raise timeout exception
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.TimeoutException("Timeout")

        client._client = mock_client

        # Should retry and eventually raise exception
        with pytest.raises(httpx.TimeoutException):
            await client.get("/test")

        # Should have made multiple attempts
        assert mock_client.request.call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_http_client_rate_limit_exception(self):
        """Test rate limit exception handling."""
        http_config = HttpConfig(base_url="https://api.example.com")
        auth_config = AuthConfig(AuthType.NONE, {})
        rate_limit = RateLimitConfig(60, 3600)
        retry_config = RetryConfig(max_retries=1)

        client = HttpClient(http_config, auth_config, rate_limit, retry_config)

        # Mock HTTP client to return 429
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_client.request.return_value = mock_response

        client._client = mock_client

        # Should raise RateLimitException
        with pytest.raises(RateLimitException):
            await client.get("/test")


class TestHttpDataProvider:
    """Test HttpDataProvider base class."""

    def create_test_provider(self, **kwargs):
        """Create a test HTTP data provider."""
        
        class TestHttpProvider(HttpDataProvider):
            def __init__(self, **provider_kwargs):
                http_config = HttpConfig(base_url="https://api.example.com")
                auth_config = AuthConfig(AuthType.NONE, {})
                rate_limit = RateLimitConfig(60, 3600)
                
                super().__init__(
                    "test_provider", http_config, auth_config, rate_limit
                )

            @property
            def name(self) -> str:
                return "test_provider"

            def _discover_capability(self) -> ProviderCapability:
                return ProviderCapability(
                    supported_assets={AssetType.STOCK},
                    supported_markets={MarketType.US},
                    supported_timeframes={TimeFrame.DAY_1},
                    max_symbols_per_request=10,
                    supports_historical=True,
                )

            async def _parse_response(self, response, query):
                # Mock parsing - return empty list
                return []

            def _build_request_url(self, query):
                return "/data"

            def _build_request_params(self, query):
                return {"symbol": ",".join(query.symbols or [])}

        return TestHttpProvider(**kwargs)

    def test_http_data_provider_initialization(self):
        """Test HttpDataProvider initialization."""
        provider = self.create_test_provider()

        assert provider.name == "test_provider"
        assert provider.http_config.base_url == "https://api.example.com"
        assert provider._http_client is None

    def test_http_data_provider_http_client_property(self):
        """Test HTTP client lazy initialization."""
        provider = self.create_test_provider()

        # First access should create client
        client1 = provider.http_client
        assert client1 is not None
        assert isinstance(client1, HttpClient)

        # Second access should return same client
        client2 = provider.http_client
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_http_data_provider_context_manager(self):
        """Test HttpDataProvider as async context manager."""
        provider = self.create_test_provider()

        async with provider as p:
            assert p is provider

        # Should be able to close without error
        await provider.close()

    @pytest.mark.asyncio
    async def test_http_data_provider_authentication_none(self):
        """Test authentication with no auth required."""
        provider = self.create_test_provider()

        # Should succeed with no authentication
        result = await provider._authenticate()
        assert result is True

    @pytest.mark.asyncio
    async def test_http_data_provider_health_check(self):
        """Test health check functionality."""
        provider = self.create_test_provider()

        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = mock_response

        provider._http_client = mock_client

        result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_http_data_provider_health_check_failure(self):
        """Test health check with server error."""
        provider = self.create_test_provider()

        # Mock HTTP client to return server error
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = mock_response

        provider._http_client = mock_client

        result = await provider.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_http_data_provider_get_data_success(self):
        """Test successful data retrieval."""
        provider = self.create_test_provider()

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
            timeframe=TimeFrame.DAY_1,
        )

        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = mock_response

        provider._http_client = mock_client

        # Mock parse_response to return test data
        test_data_point = MagicMock(spec=DataPoint)
        provider._parse_response = AsyncMock(return_value=[test_data_point])

        response = await provider.get_data(query)

        assert isinstance(response, DataResponse)
        assert len(response.data) == 1
        assert response.data[0] is test_data_point
        assert response.metadata.record_count == 1
        assert response.source.name == "test_provider"

    @pytest.mark.asyncio
    async def test_http_data_provider_get_data_unsupported_query(self):
        """Test get_data with unsupported query."""
        provider = self.create_test_provider()

        # Query for unsupported asset type
        query = DataQuery(
            asset=AssetType.BOND,  # Provider only supports STOCK
            market=MarketType.US,
            symbols=["BOND1"],
        )

        with pytest.raises(ProviderException, match="cannot handle query"):
            await provider.get_data(query)

    @pytest.mark.asyncio
    async def test_http_data_provider_get_data_auth_error(self):
        """Test get_data with authentication error."""
        provider = self.create_test_provider()

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
        )

        # Mock HTTP client to raise 401 error
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        http_error = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.side_effect = http_error

        provider._http_client = mock_client

        with pytest.raises(AuthenticationException):
            await provider.get_data(query)

    @pytest.mark.asyncio
    async def test_http_data_provider_get_data_rate_limit_error(self):
        """Test get_data with rate limit error."""
        provider = self.create_test_provider()

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
        )

        # Mock HTTP client to raise 429 error
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        http_error = httpx.HTTPStatusError(
            "Too Many Requests", request=MagicMock(), response=mock_response
        )
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.side_effect = http_error

        provider._http_client = mock_client

        with pytest.raises(RateLimitException):
            await provider.get_data(query)

    @pytest.mark.asyncio
    async def test_http_data_provider_stream_data_not_supported(self):
        """Test stream_data when not supported."""
        provider = self.create_test_provider()

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
        )

        # Provider doesn't support real-time streaming
        with pytest.raises(ProviderException, match="does not support real-time streaming"):
            async for _ in provider.stream_data(query):
                pass

    @pytest.mark.asyncio
    async def test_http_data_provider_stream_data_polling(self):
        """Test stream_data with polling implementation."""
        
        class StreamingTestProvider(HttpDataProvider):
            def __init__(self):
                http_config = HttpConfig(base_url="https://api.example.com")
                auth_config = AuthConfig(AuthType.NONE, {})
                rate_limit = RateLimitConfig(60, 3600)
                
                super().__init__(
                    "streaming_test", http_config, auth_config, rate_limit
                )

            @property
            def name(self) -> str:
                return "streaming_test"

            def _discover_capability(self) -> ProviderCapability:
                return ProviderCapability(
                    supported_assets={AssetType.STOCK},
                    supported_markets={MarketType.US},
                    supported_timeframes={TimeFrame.DAY_1},
                    max_symbols_per_request=10,
                    supports_real_time=True,  # Enable streaming
                )

            async def _parse_response(self, response, query):
                return []

            def _build_request_url(self, query):
                return "/data"

            def _build_request_params(self, query):
                return {}

        provider = StreamingTestProvider()

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
        )

        # Mock get_data to return test data
        test_data_point = MagicMock(spec=DataPoint)
        mock_response = MagicMock(spec=DataResponse)
        mock_response.data = [test_data_point]
        
        provider.get_data = AsyncMock(return_value=mock_response)

        # Test streaming (should yield data points)
        count = 0
        async for data_point in provider.stream_data(query):
            assert data_point is test_data_point
            count += 1
            if count >= 2:  # Test a few iterations
                break

        assert count == 2


class TestFactoryFunctions:
    """Test factory functions."""

    def test_create_http_config(self):
        """Test create_http_config factory function."""
        config = create_http_config(
            base_url="https://api.example.com",
            timeout=60.0,
            user_agent="custom-agent",
        )

        assert isinstance(config, HttpConfig)
        assert config.base_url == "https://api.example.com"
        assert config.timeout == 60.0
        assert config.user_agent == "custom-agent"

    def test_create_retry_config(self):
        """Test create_retry_config factory function."""
        config = create_retry_config(
            max_retries=5,
            backoff_factor=1.5,
        )

        assert isinstance(config, RetryConfig)
        assert config.max_retries == 5
        assert config.backoff_factor == 1.5


class TestIntegration:
    """Integration tests for HTTP adapter framework."""

    @pytest.mark.asyncio
    async def test_full_http_provider_workflow(self):
        """Test complete HTTP provider workflow."""
        
        class FullTestProvider(HttpDataProvider):
            def __init__(self):
                http_config = HttpConfig(
                    base_url="https://api.example.com",
                    timeout=10.0,
                )
                auth_config = AuthConfig(
                    AuthType.API_KEY,
                    credentials={"api_key": "test_key"},
                )
                rate_limit = RateLimitConfig(60, 3600)
                retry_config = RetryConfig(max_retries=1)
                
                super().__init__(
                    "full_test", http_config, auth_config, rate_limit, retry_config
                )

            @property
            def name(self) -> str:
                return "full_test"

            def _discover_capability(self) -> ProviderCapability:
                return ProviderCapability(
                    supported_assets={AssetType.STOCK, AssetType.ETF},
                    supported_markets={MarketType.US, MarketType.CN},
                    supported_timeframes={TimeFrame.DAY_1, TimeFrame.HOUR_1},
                    max_symbols_per_request=100,
                    supports_historical=True,
                )

            async def _parse_response(self, response, query):
                # Mock parsing logic
                data_points = []
                for symbol in query.symbols or ["DEFAULT"]:
                    point = MagicMock(spec=DataPoint)
                    point.symbol = symbol
                    point.timestamp = datetime.now()
                    data_points.append(point)
                return data_points

            def _build_request_url(self, query):
                return f"/data/{query.asset.value}"

            def _build_request_params(self, query):
                params = {}
                if query.symbols:
                    params["symbols"] = ",".join(query.symbols)
                if query.timeframe:
                    params["interval"] = query.timeframe.value
                return params

        provider = FullTestProvider()

        # Test capability discovery
        capability = provider.capability
        assert AssetType.STOCK in capability.supported_assets
        assert MarketType.US in capability.supported_markets

        # Test query handling
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL", "GOOGL"],
            timeframe=TimeFrame.DAY_1,
        )

        assert provider.can_handle_query(query)

        # Mock HTTP client for actual data retrieval
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = mock_response

        provider._http_client = mock_client

        # Test data retrieval
        response = await provider.get_data(query)

        assert isinstance(response, DataResponse)
        assert len(response.data) == 2  # Two symbols
        assert response.data[0].symbol == "AAPL"
        assert response.data[1].symbol == "GOOGL"
        assert response.source.name == "full_test"

        # Verify HTTP client was called correctly
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/data/stock"  # URL
        assert "symbols" in call_args[1]["params"]  # Parameters
        assert call_args[1]["params"]["symbols"] == "AAPL,GOOGL"

        # Test cleanup
        await provider.close()