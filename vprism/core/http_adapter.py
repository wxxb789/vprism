"""
HTTP adapter framework for data provider implementations.

This module provides the base HTTP client functionality for data providers,
including authentication, rate limiting, retry mechanisms, and response handling.
Designed following TDD principles with comprehensive error handling.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import httpx

from vprism.core.exceptions import (
    AuthenticationException,
    ProviderException,
    RateLimitException,
)
from vprism.core.models import DataPoint, DataQuery, DataResponse
from vprism.core.provider_abstraction import (
    AuthConfig,
    AuthType,
    EnhancedDataProvider,
    ProviderCapability,
    RateLimitConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class HttpConfig:
    """Configuration for HTTP client behavior."""

    base_url: str
    timeout: float = 30.0
    max_redirects: int = 5
    verify_ssl: bool = True
    user_agent: str = "vprism/1.0.0"
    headers: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Validate HTTP configuration."""
        if not self.base_url:
            raise ValueError("base_url cannot be empty")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.max_redirects < 0:
            raise ValueError("max_redirects must be non-negative")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    backoff_factor: float = 2.0
    retry_on_status: List[int] = field(default_factory=lambda: [429, 502, 503, 504])
    retry_on_exceptions: List[type] = field(
        default_factory=lambda: [httpx.TimeoutException, httpx.ConnectError]
    )

    def __post_init__(self):
        """Validate retry configuration."""
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.backoff_factor <= 0:
            raise ValueError("backoff_factor must be positive")


class HttpClient:
    """
    Enhanced HTTP client with authentication, rate limiting, and retry support.

    Provides a unified interface for making HTTP requests to data provider APIs
    with built-in error handling, authentication, and performance optimization.
    """

    def __init__(
        self,
        http_config: HttpConfig,
        auth_config: AuthConfig,
        rate_limit: RateLimitConfig,
        retry_config: Optional[RetryConfig] = None,
    ):
        """Initialize HTTP client with configuration."""
        self.http_config = http_config
        self.auth_config = auth_config
        self.rate_limit = rate_limit
        self.retry_config = retry_config or RetryConfig()

        self._client: Optional[httpx.AsyncClient] = None
        self._request_history: List[datetime] = []
        self._semaphore = asyncio.Semaphore(rate_limit.concurrent_requests)

    async def __aenter__(self) -> "HttpClient":
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            # Build headers
            headers = {
                "User-Agent": self.http_config.user_agent,
                **self.http_config.headers,
                **self.auth_config.get_auth_headers(),
            }

            # Create client with configuration
            self._client = httpx.AsyncClient(
                base_url=self.http_config.base_url,
                timeout=httpx.Timeout(self.http_config.timeout),
                follow_redirects=True,
                max_redirects=self.http_config.max_redirects,
                verify=self.http_config.verify_ssl,
                headers=headers,
            )

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _record_request(self) -> None:
        """Record a request for rate limiting purposes."""
        now = datetime.now()
        self._request_history.append(now)

        # Keep only recent history (last hour)
        cutoff = now - timedelta(hours=1)
        self._request_history = [req for req in self._request_history if req > cutoff]

    def _check_rate_limit(self) -> bool:
        """Check if rate limit would be exceeded."""
        return not self.rate_limit.is_rate_limit_exceeded(self._request_history)

    async def _wait_for_rate_limit(self) -> None:
        """Wait if rate limit would be exceeded."""
        if not self._check_rate_limit():
            delay = self.rate_limit.calculate_min_delay()
            logger.debug(f"Rate limit reached, waiting {delay} seconds")
            await asyncio.sleep(delay)

    async def _execute_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute HTTP request with rate limiting."""
        await self._ensure_client()

        async with self._semaphore:
            await self._wait_for_rate_limit()
            self._record_request()

            response = await self._client.request(method, url, **kwargs)
            return response

    async def _request_with_retry(
        self, method: str, url: str, **kwargs
    ) -> httpx.Response:
        """Execute HTTP request with retry logic."""
        last_exception = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                response = await self._execute_request(method, url, **kwargs)

                # Check if we should retry based on status code
                if response.status_code in self.retry_config.retry_on_status:
                    if attempt < self.retry_config.max_retries:
                        delay = self.retry_config.backoff_factor**attempt
                        logger.warning(
                            f"Request failed with status {response.status_code}, "
                            f"retrying in {delay} seconds (attempt {attempt + 1})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Last attempt, raise exception
                        if response.status_code == 429:
                            raise RateLimitException(
                                provider="http_client",
                                details={"status_code": response.status_code},
                            )
                        else:
                            raise ProviderException(
                                f"HTTP request failed: {response.status_code}",
                                provider="http_client",
                                error_code="HTTP_ERROR",
                                details={"status_code": response.status_code},
                            )

                # Success or non-retryable error
                return response

            except Exception as e:
                last_exception = e

                # Check if we should retry based on exception type
                should_retry = any(
                    isinstance(e, exc_type)
                    for exc_type in self.retry_config.retry_on_exceptions
                )

                if should_retry and attempt < self.retry_config.max_retries:
                    delay = self.retry_config.backoff_factor**attempt
                    logger.warning(
                        f"Request failed with {type(e).__name__}: {e}, "
                        f"retrying in {delay} seconds (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Last attempt or non-retryable error
                    raise

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Execute GET request."""
        return await self._request_with_retry("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        """Execute POST request."""
        return await self._request_with_retry("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> httpx.Response:
        """Execute PUT request."""
        return await self._request_with_retry("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """Execute DELETE request."""
        return await self._request_with_retry("DELETE", url, **kwargs)

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute request with specified method."""
        return await self._request_with_retry(method, url, **kwargs)


class HttpDataProvider(EnhancedDataProvider):
    """
    Base class for HTTP-based data providers.

    Extends EnhancedDataProvider with HTTP client functionality,
    providing a foundation for implementing REST API-based data sources.
    """

    def __init__(
        self,
        provider_name: str,
        http_config: HttpConfig,
        auth_config: AuthConfig,
        rate_limit: RateLimitConfig,
        retry_config: Optional[RetryConfig] = None,
    ):
        """Initialize HTTP data provider."""
        super().__init__(provider_name, auth_config, rate_limit)
        self.http_config = http_config
        self.retry_config = retry_config or RetryConfig()
        self._http_client: Optional[HttpClient] = None

    @property
    def http_client(self) -> HttpClient:
        """Get HTTP client instance (lazy initialization)."""
        if self._http_client is None:
            self._http_client = HttpClient(
                self.http_config,
                self.auth_config,
                self.rate_limit,
                self.retry_config,
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._http_client:
            await self._http_client.close()
            self._http_client = None

    async def __aenter__(self) -> "HttpDataProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    @abstractmethod
    async def _parse_response(
        self, response: httpx.Response, query: DataQuery
    ) -> List[DataPoint]:
        """Parse HTTP response into data points."""
        pass

    @abstractmethod
    def _build_request_url(self, query: DataQuery) -> str:
        """Build request URL for the given query."""
        pass

    @abstractmethod
    def _build_request_params(self, query: DataQuery) -> Dict[str, Any]:
        """Build request parameters for the given query."""
        pass

    async def _authenticate(self) -> bool:
        """Perform authentication with the provider."""
        try:
            # For most HTTP providers, authentication is handled via headers
            # This method can be overridden for providers requiring special auth flows
            if self.auth_config.auth_type == AuthType.NONE:
                return True

            # Test authentication by making a simple request
            async with self.http_client as client:
                # Try to make a simple request to test auth
                # This is a basic implementation - providers should override as needed
                try:
                    response = await client.get("/")
                    return response.status_code != 401
                except Exception as e:
                    logger.warning(f"Authentication test failed: {e}")
                    return False

        except Exception as e:
            logger.error(f"Authentication failed for provider {self.name}: {e}")
            return False

    async def health_check(self) -> bool:
        """Check if the provider is healthy and available."""
        try:
            async with self.http_client as client:
                # Make a simple request to check connectivity
                response = await client.get("/")
                return response.status_code < 500
        except Exception as e:
            logger.warning(f"Health check failed for provider {self.name}: {e}")
            return False

    async def get_data(self, query: DataQuery) -> DataResponse:
        """Retrieve data via HTTP request."""
        if not self.can_handle_query(query):
            raise ProviderException(
                f"Provider {self.name} cannot handle query",
                provider=self.name,
                error_code="UNSUPPORTED_QUERY",
                details={"query": query.model_dump()},
            )

        try:
            start_time = datetime.now()

            # Build request
            url = self._build_request_url(query)
            params = self._build_request_params(query)

            # Execute request
            async with self.http_client as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                # Parse response
                data_points = await self._parse_response(response, query)

                # Calculate execution time
                execution_time = (datetime.now() - start_time).total_seconds() * 1000

                # Build response
                from vprism.core.models import ResponseMetadata, ProviderInfo

                metadata = ResponseMetadata(
                    query_time=start_time,
                    execution_time_ms=execution_time,
                    record_count=len(data_points),
                    cache_hit=False,
                )

                provider_info = ProviderInfo(
                    name=self.name,
                    version=None,
                    url=self.http_config.base_url,
                    rate_limit=self.rate_limit.requests_per_minute,
                )

                return DataResponse(
                    data=data_points,
                    metadata=metadata,
                    source=provider_info,
                    query=query,
                )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationException(
                    provider=self.name, details={"status_code": e.response.status_code}
                )
            elif e.response.status_code == 429:
                raise RateLimitException(
                    provider=self.name, details={"status_code": e.response.status_code}
                )
            else:
                raise ProviderException(
                    f"HTTP error from provider {self.name}: {e.response.status_code}",
                    provider=self.name,
                    error_code="HTTP_ERROR",
                    details={"status_code": e.response.status_code},
                )
        except Exception as e:
            raise ProviderException(
                f"Error retrieving data from provider {self.name}: {str(e)}",
                provider=self.name,
                error_code="PROVIDER_ERROR",
                details={"error_type": type(e).__name__},
            )

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """Stream data via HTTP (default implementation using polling)."""
        # Default implementation for providers that don't support native streaming
        # Override this method for providers with WebSocket or SSE support

        if not self.capability.supports_real_time:
            raise ProviderException(
                f"Provider {self.name} does not support real-time streaming",
                provider=self.name,
                error_code="STREAMING_NOT_SUPPORTED",
            )

        # Simple polling-based streaming
        while True:
            try:
                response = await self.get_data(query)
                for data_point in response.data:
                    yield data_point

                # Wait before next poll
                await asyncio.sleep(1.0)  # 1 second polling interval

            except Exception as e:
                logger.error(f"Streaming error from provider {self.name}: {e}")
                break


def create_http_config(
    base_url: str, timeout: float = 30.0, user_agent: str = "vprism/1.0.0", **kwargs
) -> HttpConfig:
    """Factory function to create HTTP configuration."""
    return HttpConfig(
        base_url=base_url, timeout=timeout, user_agent=user_agent, **kwargs
    )


def create_retry_config(
    max_retries: int = 3, backoff_factor: float = 2.0, **kwargs
) -> RetryConfig:
    """Factory function to create retry configuration."""
    return RetryConfig(max_retries=max_retries, backoff_factor=backoff_factor, **kwargs)
