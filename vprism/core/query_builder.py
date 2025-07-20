"""
Query builder for vprism financial data platform.

This module implements the QueryBuilder class that provides a fluent,
chainable API for constructing complex data queries. It supports the
builder pattern for more readable and flexible query construction.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from vprism.core.models import AssetType, DataQuery, MarketType, TimeFrame


class QueryBuilder:
    """
    Fluent query builder for constructing DataQuery objects.

    Provides a chainable API for building complex queries:

    Example:
        query = (vprism.query()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001", "000002"])
            .timeframe(TimeFrame.DAY_1)
            .date_range("2024-01-01", "2024-12-31")
            .provider("tushare")
            .limit(100)
            .build())
    """

    def __init__(self):
        """Initialize QueryBuilder with default values."""
        self._asset: AssetType | None = None
        self._market: MarketType | None = None
        self._symbols: list[str] | None = None
        self._provider: str | None = None
        self._timeframe: TimeFrame | None = None
        self._start: datetime | None = None
        self._end: datetime | None = None
        self._limit: int | None = None
        self._fields: list[str] | None = None
        self._filters: dict[str, Any] = {}

    def asset(self, asset: AssetType) -> QueryBuilder:
        """
        Set the asset type for the query.

        Args:
            asset: Type of asset to query

        Returns:
            QueryBuilder instance for chaining
        """
        self._asset = asset
        return self

    def market(self, market: MarketType) -> QueryBuilder:
        """
        Set the market for the query.

        Args:
            market: Market to query

        Returns:
            QueryBuilder instance for chaining
        """
        self._market = market
        return self

    def symbols(self, symbols: list[str]) -> QueryBuilder:
        """
        Set the symbols for the query.

        Args:
            symbols: List of symbols to query

        Returns:
            QueryBuilder instance for chaining
        """
        self._symbols = symbols.copy() if symbols else None
        return self

    def symbol(self, symbol: str) -> QueryBuilder:
        """
        Add a single symbol to the query.

        Args:
            symbol: Symbol to add

        Returns:
            QueryBuilder instance for chaining
        """
        if self._symbols is None:
            self._symbols = []
        self._symbols.append(symbol)
        return self

    def provider(self, provider: str) -> QueryBuilder:
        """
        Set the preferred data provider.

        Args:
            provider: Provider name

        Returns:
            QueryBuilder instance for chaining
        """
        self._provider = provider
        return self

    def timeframe(self, timeframe: TimeFrame) -> QueryBuilder:
        """
        Set the data timeframe.

        Args:
            timeframe: Data timeframe

        Returns:
            QueryBuilder instance for chaining
        """
        self._timeframe = timeframe
        return self

    def start(self, start: datetime | str) -> QueryBuilder:
        """
        Set the start date/time for the query.

        Args:
            start: Start date/time (datetime object or string)

        Returns:
            QueryBuilder instance for chaining
        """
        if isinstance(start, str):
            self._start = self._parse_date_string(start)
        else:
            self._start = start
        return self

    def end(self, end: datetime | str) -> QueryBuilder:
        """
        Set the end date/time for the query.

        Args:
            end: End date/time (datetime object or string)

        Returns:
            QueryBuilder instance for chaining
        """
        if isinstance(end, str):
            self._end = self._parse_date_string(end)
        else:
            self._end = end
        return self

    def date_range(self, start: datetime | str, end: datetime | str) -> QueryBuilder:
        """
        Set both start and end dates for the query.

        Args:
            start: Start date/time (datetime object or string)
            end: End date/time (datetime object or string)

        Returns:
            QueryBuilder instance for chaining
        """
        return self.start(start).end(end)

    def limit(self, limit: int) -> QueryBuilder:
        """
        Set the maximum number of records to return.

        Args:
            limit: Maximum number of records

        Returns:
            QueryBuilder instance for chaining
        """
        self._limit = limit
        return self

    def fields(self, fields: list[str]) -> QueryBuilder:
        """
        Set specific fields to return.

        Args:
            fields: List of field names

        Returns:
            QueryBuilder instance for chaining
        """
        self._fields = fields.copy() if fields else None
        return self

    def field(self, field: str) -> QueryBuilder:
        """
        Add a single field to return.

        Args:
            field: Field name to add

        Returns:
            QueryBuilder instance for chaining
        """
        if self._fields is None:
            self._fields = []
        self._fields.append(field)
        return self

    def filter(self, key: str, value: Any) -> QueryBuilder:
        """
        Add a custom filter to the query.

        Args:
            key: Filter key
            value: Filter value

        Returns:
            QueryBuilder instance for chaining
        """
        self._filters[key] = value
        return self

    def filters(self, filters: dict[str, Any]) -> QueryBuilder:
        """
        Set multiple custom filters.

        Args:
            filters: Dictionary of filters

        Returns:
            QueryBuilder instance for chaining
        """
        self._filters.update(filters)
        return self

    def build(self) -> DataQuery:
        """
        Build the final DataQuery object.

        Returns:
            Constructed DataQuery object

        Raises:
            ValueError: If required fields are missing
        """
        if self._asset is None:
            raise ValueError("Asset type is required")

        return DataQuery(
            asset=self._asset,
            market=self._market,
            symbols=self._symbols,
            provider=self._provider,
            timeframe=self._timeframe,
            start=self._start,
            end=self._end,
            limit=self._limit,
            fields=self._fields,
            filters=self._filters,
        )

    def _parse_date_string(self, date_str: str) -> datetime:
        """
        Parse date string to datetime object.

        Args:
            date_str: Date string to parse

        Returns:
            Parsed datetime object

        Raises:
            ValueError: When date string cannot be parsed
        """
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
        raise ValueError(f"Unable to parse date string: {date_str}")

    def reset(self) -> QueryBuilder:
        """
        Reset the builder to initial state.

        Returns:
            QueryBuilder instance for chaining
        """
        self._asset = None
        self._market = None
        self._symbols = None
        self._provider = None
        self._timeframe = None
        self._start = None
        self._end = None
        self._limit = None
        self._fields = None
        self._filters = {}
        return self

    def copy(self) -> QueryBuilder:
        """
        Create a copy of the current builder state.

        Returns:
            New QueryBuilder instance with same state
        """
        new_builder = QueryBuilder()
        new_builder._asset = self._asset
        new_builder._market = self._market
        new_builder._symbols = self._symbols.copy() if self._symbols else None
        new_builder._provider = self._provider
        new_builder._timeframe = self._timeframe
        new_builder._start = self._start
        new_builder._end = self._end
        new_builder._limit = self._limit
        new_builder._fields = self._fields.copy() if self._fields else None
        new_builder._filters = self._filters.copy()
        return new_builder

    def __repr__(self) -> str:
        """String representation of the builder state."""
        parts = []
        if self._asset:
            parts.append(f"asset={self._asset.value}")
        if self._market:
            parts.append(f"market={self._market.value}")
        if self._symbols:
            parts.append(f"symbols={self._symbols}")
        if self._provider:
            parts.append(f"provider={self._provider}")
        if self._timeframe:
            parts.append(f"timeframe={self._timeframe.value}")
        if self._start:
            parts.append(f"start={self._start.isoformat()}")
        if self._end:
            parts.append(f"end={self._end.isoformat()}")
        if self._limit:
            parts.append(f"limit={self._limit}")
        if self._fields:
            parts.append(f"fields={self._fields}")
        if self._filters:
            parts.append(f"filters={self._filters}")

        return f"QueryBuilder({', '.join(parts)})"
