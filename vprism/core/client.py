"""
Core client implementation for vprism.

This module provides the main client interface for accessing financial data,
supporting both synchronous and asynchronous operations.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from vprism.core.data_service import DataService
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
        self._data_service: DataService | None = None

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
            # Initialize the data service
            self._data_service = DataService()
            self._initialized = True

    async def _cleanup(self) -> None:
        """Clean up resources."""
        # Clean up data service resources if needed
        if self._data_service:
            # Data service doesn't currently need cleanup, but we can add it later
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

        # Parse date strings to datetime objects
        start_dt = self._parse_date_string(start) if start else None
        end_dt = self._parse_date_string(end) if end else None

        # Create query object
        query = DataQuery(
            asset=asset,
            market=market,
            symbols=symbols,
            provider=provider,
            timeframe=timeframe,
            start=start_dt,
            end=end_dt,
            limit=limit,
            fields=None,
            filters=kwargs,
        )

        # Execute query through data service
        if not self._data_service:
            raise VPrismException(
                message="Data service not initialized",
                error_code="INITIALIZATION_ERROR",
            )

        return await self._data_service.get_data(query)

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
        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            # If we're in an event loop, we can't use asyncio.run()
            # This is mainly for testing scenarios
            raise VPrismException(
                message="Synchronous method cannot be called from within an async context. Use the async get() method instead.",
                error_code="SYNC_IN_ASYNC_CONTEXT",
                details={"suggestion": "Use await client.get(...) instead of client.get_sync(...)"},
            )
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
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

        # Create query object for streaming
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

        # For now, streaming is not fully implemented
        # We'll provide a basic implementation that yields a single response
        if not self._data_service:
            raise VPrismException(
                message="Data service not initialized",
                error_code="INITIALIZATION_ERROR",
            )

        # Get data once and yield it (basic streaming simulation)
        response = await self._data_service.get_data(query)
        yield response

        # TODO: Implement real streaming with WebSocket or Server-Sent Events
        # This is a placeholder implementation

    def configure(self, **kwargs: Any) -> None:
        """
        Update client configuration.

        Args:
            **kwargs: Configuration parameters to update
        """
        self.config.update(kwargs)
        # Reset initialization to force reconfiguration
        self._initialized = False

    def _parse_date_string(self, date_str: str) -> datetime:
        """
        Parse date string to datetime object.

        Supports various date formats:
        - ISO format: "2024-01-01T00:00:00Z"
        - Date only: "2024-01-01"
        - Date with time: "2024-01-01 10:30:00"

        Args:
            date_str: Date string to parse

        Returns:
            Parsed datetime object

        Raises:
            VPrismException: When date string cannot be parsed
        """
        if not date_str:
            raise VPrismException(
                message="Date string cannot be empty",
                error_code="INVALID_DATE_FORMAT",
            )

        # Try different date formats
        formats = [
            "%Y-%m-%d",  # 2024-01-01
            "%Y-%m-%dT%H:%M:%S",  # 2024-01-01T10:30:00
            "%Y-%m-%dT%H:%M:%SZ",  # 2024-01-01T10:30:00Z
            "%Y-%m-%d %H:%M:%S",  # 2024-01-01 10:30:00
            "%Y/%m/%d",  # 2024/01/01
            "%Y/%m/%d %H:%M:%S",  # 2024/01/01 10:30:00
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # If no format worked, raise an error
        raise VPrismException(
            message=f"Unable to parse date string: {date_str}",
            error_code="INVALID_DATE_FORMAT",
            details={
                "date_string": date_str,
                "supported_formats": formats,
            },
        )
