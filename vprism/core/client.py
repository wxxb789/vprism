"""
Core client implementation for vprism.

This module provides the main client interface for accessing financial data,
supporting both synchronous and asynchronous operations.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from vprism.core.exceptions import VPrismException
from vprism.core.models import AssetType, DataQuery, DataResponse, MarketType, TimeFrame


class VPrismClient:
    """
    Main client for accessing vprism financial data.

    Provides both synchronous and asynchronous interfaces for querying
    financial data from multiple providers through a unified API.
    """

    def __init__(self, config: dict[str, Any] | None = None, **kwargs: Any) -> None:
        """
        Initialize VPrismClient.

        Args:
            config: Optional configuration dictionary
            **kwargs: Additional configuration parameters
        """
        self.config = (config or {}).copy()  # Create a copy to avoid mutating original
        self.config.update(kwargs)
        self._initialized = False
        self._data_service: Any | None = None  # Will be injected later

    async def __aenter__(self) -> VPrismClient:
        """Async context manager entry."""
        await self._ensure_initialized()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._cleanup()

    async def _ensure_initialized(self) -> None:
        """Ensure client is properly initialized."""
        if not self._initialized:
            # This will be implemented when we have the data service
            # For now, just mark as initialized
            self._initialized = True

    async def _cleanup(self) -> None:
        """Clean up resources."""
        # This will be implemented when we have resources to clean up
        pass

    async def get(
        self,
        asset: AssetType,
        market: MarketType | None = None,
        symbols: list[str] | None = None,
        provider: str | None = None,
        timeframe: TimeFrame | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> DataResponse:
        """
        Asynchronously retrieve financial data.

        Args:
            asset: Type of asset to query
            market: Market to query (optional)
            symbols: Specific symbols to query (optional)
            provider: Preferred data provider (optional)
            timeframe: Data timeframe (optional)
            start: Start date/time (optional)
            end: End date/time (optional)
            limit: Maximum number of records (optional)
            **kwargs: Additional query parameters

        Returns:
            DataResponse containing the requested data

        Raises:
            VPrismException: When query fails
        """
        await self._ensure_initialized()

        # Create query object
        query = DataQuery(
            asset=asset,
            market=market,
            symbols=symbols,
            provider=provider,
            timeframe=timeframe,
            start=None,  # TODO: Parse start string to datetime
            end=None,  # TODO: Parse end string to datetime
            limit=limit,
            fields=None,
            filters=kwargs,
        )

        # TODO: This will be implemented when we have the data service
        # For now, raise a not implemented error
        raise VPrismException(
            message="Data service not yet implemented",
            error_code="NOT_IMPLEMENTED",
            details={"query": query.model_dump()},
        )

    def get_sync(
        self,
        asset: AssetType,
        market: MarketType | None = None,
        symbols: list[str] | None = None,
        provider: str | None = None,
        timeframe: TimeFrame | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> DataResponse:
        """
        Synchronously retrieve financial data.

        This is a convenience wrapper around the async get method.

        Args:
            asset: Type of asset to query
            market: Market to query (optional)
            symbols: Specific symbols to query (optional)
            provider: Preferred data provider (optional)
            timeframe: Data timeframe (optional)
            start: Start date/time (optional)
            end: End date/time (optional)
            limit: Maximum number of records (optional)
            **kwargs: Additional query parameters

        Returns:
            DataResponse containing the requested data

        Raises:
            VPrismException: When query fails
        """
        return asyncio.run(
            self.get(
                asset=asset,
                market=market,
                symbols=symbols,
                provider=provider,
                timeframe=timeframe,
                start=start,
                end=end,
                limit=limit,
                **kwargs,
            )
        )

    async def stream(
        self,
        asset: AssetType,
        market: MarketType | None = None,
        symbols: list[str] | None = None,
        provider: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[DataResponse]:
        """
        Stream real-time financial data.

        Args:
            asset: Type of asset to stream
            market: Market to stream (optional)
            symbols: Specific symbols to stream (optional)
            provider: Preferred data provider (optional)
            **kwargs: Additional stream parameters

        Yields:
            DataResponse: Real-time data updates

        Raises:
            VPrismException: When streaming fails
        """
        await self._ensure_initialized()

        # Create query object
        query = DataQuery(
            asset=asset,
            market=market,
            symbols=symbols,
            provider=provider,
            timeframe=None,
            start=None,
            end=None,
            limit=None,
            fields=None,
            filters=kwargs,
        )

        # TODO: This will be implemented when we have the streaming service
        # For now, raise a not implemented error
        raise VPrismException(
            message="Streaming service not yet implemented",
            error_code="NOT_IMPLEMENTED",
            details={"query": query.model_dump()},
        )

        # This is unreachable but shows the intended interface
        yield  # type: ignore[unreachable]  # pragma: no cover

    def configure(self, **kwargs: Any) -> None:
        """
        Update client configuration.

        Args:
            **kwargs: Configuration parameters to update
        """
        self.config.update(kwargs)
        # Reset initialization to force reconfiguration
        self._initialized = False
