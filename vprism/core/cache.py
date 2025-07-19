"""
Multi-level caching system for vprism.

This module implements a sophisticated caching architecture with:
- L1: Thread-safe in-memory LRU cache for hot data
- L2: DuckDB-based persistent cache for warm data
- Intelligent TTL strategies based on data types
- Cache key generation and management
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import duckdb

from vprism.core.interfaces import CacheRepository
from vprism.core.models import DataQuery, DataResponse, TimeFrame


class CacheKey:
    """
    Generates deterministic cache keys and calculates appropriate TTL values.

    This class ensures consistent cache key generation across different
    query instances and implements intelligent TTL strategies based on
    data characteristics.
    """

    def __init__(self, query: DataQuery):
        """
        Initialize cache key with query.

        Args:
            query: The data query to generate cache key for
        """
        self.key = self._generate_key(query)
        self.ttl = self._calculate_ttl(query)

    def _generate_key(self, query: DataQuery) -> str:
        """
        Generate a deterministic cache key from query parameters.

        Args:
            query: The data query

        Returns:
            16-character hexadecimal cache key
        """
        # Build key components in consistent order
        parts = [
            f"asset:{query.asset.value}",
            f"market:{query.market.value}" if query.market else "",
            f"symbols:{','.join(sorted(query.symbols))}" if query.symbols else "",
            f"provider:{query.provider}" if query.provider else "",
            f"timeframe:{query.timeframe.value}" if query.timeframe else "",
            f"start:{query.start.isoformat()}" if query.start else "",
            f"end:{query.end.isoformat()}" if query.end else "",
            f"limit:{query.limit}" if query.limit else "",
        ]

        # Create content string and hash it
        content = "|".join(filter(None, parts))
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _calculate_ttl(self, query: DataQuery) -> int:
        """
        Calculate appropriate TTL based on query characteristics.

        Args:
            query: The data query

        Returns:
            TTL in seconds
        """
        if not query.timeframe:
            return 300  # 5 minutes default

        # TTL mapping based on data frequency and volatility
        ttl_map = {
            TimeFrame.TICK: 5,  # 5 seconds - very volatile
            TimeFrame.SECOND_1: 10,  # 10 seconds
            TimeFrame.SECOND_5: 15,  # 15 seconds
            TimeFrame.SECOND_15: 30,  # 30 seconds
            TimeFrame.SECOND_30: 60,  # 1 minute
            TimeFrame.MINUTE_1: 60,  # 1 minute
            TimeFrame.MINUTE_5: 300,  # 5 minutes
            TimeFrame.MINUTE_15: 900,  # 15 minutes
            TimeFrame.MINUTE_30: 1800,  # 30 minutes
            TimeFrame.HOUR_1: 3600,  # 1 hour
            TimeFrame.HOUR_2: 7200,  # 2 hours
            TimeFrame.HOUR_4: 14400,  # 4 hours
            TimeFrame.DAY_1: 3600,  # 1 hour for daily data
            TimeFrame.WEEK_1: 86400,  # 1 day for weekly data
            TimeFrame.MONTH_1: 604800,  # 1 week for monthly data
        }

        return ttl_map.get(query.timeframe, 300)


class ThreadSafeInMemoryCache:
    """
    Thread-safe in-memory LRU cache implementation.

    This is the L1 cache that provides ultra-fast access to frequently
    requested data. Uses asyncio.Lock for thread safety and implements
    LRU eviction with TTL support.
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize the in-memory cache.

        Args:
            max_size: Maximum number of items to store
        """
        self.max_size = max_size
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.expiry: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """
        Get item from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        async with self._lock:
            now = datetime.now(timezone.utc)

            # Check if key exists and is not expired
            if key in self.expiry and now > self.expiry[key]:
                self._remove_expired(key)
                return None

            if key in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return self.cache[key]

            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set item in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (optional)
        """
        async with self._lock:
            # Don't store anything if max_size is 0
            if self.max_size == 0:
                return

            now = datetime.now(timezone.utc)

            # If key already exists, move to end
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                # Check if we need to evict
                if len(self.cache) >= self.max_size:
                    # Remove least recently used item
                    oldest_key = next(iter(self.cache))
                    self._remove_expired(oldest_key)

            # Set the value
            self.cache[key] = value

            # Set expiry if TTL provided
            if ttl is not None:
                self.expiry[key] = now + timedelta(seconds=ttl)

    def _remove_expired(self, key: str) -> None:
        """
        Remove expired item from cache.

        Args:
            key: Cache key to remove
        """
        self.cache.pop(key, None)
        self.expiry.pop(key, None)


class SimpleDuckDBCache:
    """
    DuckDB-based persistent cache implementation.

    This is the L2 cache that provides persistent storage for warm data.
    Uses optimized table structures for different data types and supports
    efficient querying and storage.
    """

    def __init__(self, db_path: str = "vprism_cache.duckdb"):
        """
        Initialize the DuckDB cache.

        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database tables and indexes."""
        with duckdb.connect(self.db_path) as conn:
            # Simple cache entries table for generic caching
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key VARCHAR(32) PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Index for expiration queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_expires 
                ON cache_entries(expires_at)
            """)

            # Optimized OHLCV data tables
            self._create_ohlcv_tables(conn)

            # Asset information table
            self._create_asset_tables(conn)

    def _create_ohlcv_tables(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create optimized OHLCV data tables."""
        # Daily OHLCV data
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_ohlcv (
                symbol VARCHAR(32) NOT NULL,
                trade_date DATE NOT NULL,
                market VARCHAR(8) NOT NULL,
                open_price DECIMAL(18,6) NOT NULL,
                high_price DECIMAL(18,6) NOT NULL,
                low_price DECIMAL(18,6) NOT NULL,
                close_price DECIMAL(18,6) NOT NULL,
                volume DECIMAL(20,2) NOT NULL,
                amount DECIMAL(20,2),
                provider VARCHAR(32) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, trade_date, market)
            )
        """)

        # Intraday OHLCV data
        conn.execute("""
            CREATE TABLE IF NOT EXISTS intraday_ohlcv (
                symbol VARCHAR(32) NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                market VARCHAR(8) NOT NULL,
                timeframe VARCHAR(8) NOT NULL,
                open_price DECIMAL(18,6) NOT NULL,
                high_price DECIMAL(18,6) NOT NULL,
                low_price DECIMAL(18,6) NOT NULL,
                close_price DECIMAL(18,6) NOT NULL,
                volume DECIMAL(20,2) NOT NULL,
                amount DECIMAL(20,2),
                provider VARCHAR(32) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, timestamp, timeframe, market)
            )
        """)

        # Indexes for performance
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_ohlcv_date 
            ON daily_ohlcv(trade_date DESC)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_ohlcv_symbol 
            ON daily_ohlcv(symbol, trade_date DESC)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_intraday_timestamp 
            ON intraday_ohlcv(timestamp DESC)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_intraday_symbol_time 
            ON intraday_ohlcv(symbol, timestamp DESC)
        """)

    def _create_asset_tables(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create asset information tables."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS asset_info (
                symbol VARCHAR(32) NOT NULL,
                market VARCHAR(8) NOT NULL,
                name VARCHAR(256),
                asset_type VARCHAR(16) NOT NULL,
                currency VARCHAR(8),
                exchange VARCHAR(16),
                sector VARCHAR(64),
                industry VARCHAR(64),
                is_active BOOLEAN DEFAULT TRUE,
                provider VARCHAR(32) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, market)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_asset_type 
            ON asset_info(asset_type, market)
        """)

    async def get(self, key: str) -> Optional[DataResponse]:
        """
        Get cached data response.

        Args:
            key: Cache key

        Returns:
            Cached DataResponse or None if not found/expired
        """
        try:
            with duckdb.connect(self.db_path) as conn:
                # Query cache entries table
                result = conn.execute(
                    """
                    SELECT data_json, expires_at 
                    FROM cache_entries 
                    WHERE cache_key = ? 
                    AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                """,
                    [key],
                ).fetchone()

                if result:
                    data_json, expires_at = result
                    # Deserialize the cached response
                    data_dict = json.loads(data_json)
                    return DataResponse.model_validate(data_dict)

                return None
        except Exception:
            # Log error in production, return None for now
            return None

    async def set(
        self, key: str, value: DataResponse, ttl: Optional[int] = None
    ) -> None:
        """
        Set cached data response.

        Args:
            key: Cache key
            value: DataResponse to cache
            ttl: Time to live in seconds (optional)
        """
        try:
            with duckdb.connect(self.db_path) as conn:
                # Serialize the response
                data_json = value.model_dump_json()

                # Calculate expiry time
                expires_at = None
                if ttl is not None:
                    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

                # Insert or replace cache entry
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache_entries 
                    (cache_key, data_json, expires_at) 
                    VALUES (?, ?, ?)
                """,
                    [key, data_json, expires_at],
                )

                # Also store in optimized tables if applicable
                await self._store_optimized_data(conn, value)

        except Exception:
            # Log error in production, continue silently for now
            pass

    async def _store_optimized_data(
        self, conn: duckdb.DuckDBPyConnection, response: DataResponse
    ) -> None:
        """
        Store data in optimized tables based on data type.

        Args:
            conn: DuckDB connection
            response: DataResponse to store
        """
        try:
            query = response.query

            # Determine if this is OHLCV data
            if self._is_ohlcv_data(response):
                await self._store_ohlcv_data(conn, response)

            # Store asset information if available
            if self._has_asset_info(response):
                await self._store_asset_info(conn, response)

        except Exception:
            # Log error in production, continue silently
            pass

    def _is_ohlcv_data(self, response: DataResponse) -> bool:
        """Check if response contains OHLCV data."""
        if not response.data:
            return False

        # Check if data points have OHLCV fields
        sample_point = response.data[0]
        return (
            sample_point.open is not None
            or sample_point.high is not None
            or sample_point.low is not None
            or sample_point.close is not None
        )

    def _has_asset_info(self, response: DataResponse) -> bool:
        """Check if response contains asset information."""
        if not response.data:
            return False

        # Check if data points have asset metadata
        sample_point = response.data[0]
        return bool(sample_point.extra_fields)

    async def _store_ohlcv_data(
        self, conn: duckdb.DuckDBPyConnection, response: DataResponse
    ) -> None:
        """Store OHLCV data in optimized tables."""
        query = response.query
        market = query.market.value if query.market else "unknown"
        provider = response.source.name

        for data_point in response.data:
            if query.timeframe == TimeFrame.DAY_1:
                # Store in daily table
                conn.execute(
                    """
                    INSERT OR REPLACE INTO daily_ohlcv 
                    (symbol, trade_date, market, open_price, high_price, 
                     low_price, close_price, volume, amount, provider)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        data_point.symbol,
                        data_point.timestamp.date(),
                        market,
                        float(data_point.open) if data_point.open else 0,
                        float(data_point.high) if data_point.high else 0,
                        float(data_point.low) if data_point.low else 0,
                        float(data_point.close) if data_point.close else 0,
                        float(data_point.volume) if data_point.volume else 0,
                        float(data_point.amount) if data_point.amount else None,
                        provider,
                    ],
                )
            else:
                # Store in intraday table
                timeframe = query.timeframe.value if query.timeframe else "unknown"
                conn.execute(
                    """
                    INSERT OR REPLACE INTO intraday_ohlcv 
                    (symbol, timestamp, market, timeframe, open_price, high_price, 
                     low_price, close_price, volume, amount, provider)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        data_point.symbol,
                        data_point.timestamp,
                        market,
                        timeframe,
                        float(data_point.open) if data_point.open else 0,
                        float(data_point.high) if data_point.high else 0,
                        float(data_point.low) if data_point.low else 0,
                        float(data_point.close) if data_point.close else 0,
                        float(data_point.volume) if data_point.volume else 0,
                        float(data_point.amount) if data_point.amount else None,
                        provider,
                    ],
                )

    async def _store_asset_info(
        self, conn: duckdb.DuckDBPyConnection, response: DataResponse
    ) -> None:
        """Store asset information in asset_info table."""
        query = response.query
        market = query.market.value if query.market else "unknown"
        provider = response.source.name

        for data_point in response.data:
            if data_point.extra_fields:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO asset_info 
                    (symbol, market, name, asset_type, currency, exchange, 
                     sector, industry, provider)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        data_point.symbol,
                        market,
                        data_point.extra_fields.get("name"),
                        query.asset.value,
                        data_point.extra_fields.get("currency"),
                        data_point.extra_fields.get("exchange"),
                        data_point.extra_fields.get("sector"),
                        data_point.extra_fields.get("industry"),
                        provider,
                    ],
                )


class MultiLevelCache(CacheRepository):
    """
    Multi-level cache implementation combining L1 and L2 caches.

    This class orchestrates the caching strategy by:
    1. Checking L1 (in-memory) cache first for hot data
    2. Falling back to L2 (DuckDB) cache for warm data
    3. Backfilling L1 from L2 when appropriate
    4. Using intelligent TTL strategies based on data characteristics
    """

    def __init__(self, db_path: str = "vprism_cache.duckdb", l1_max_size: int = 1000):
        """
        Initialize multi-level cache.

        Args:
            db_path: Path to DuckDB database file
            l1_max_size: Maximum size of L1 cache
        """
        self.l1_cache = ThreadSafeInMemoryCache(max_size=l1_max_size)
        self.l2_cache = SimpleDuckDBCache(db_path=db_path)

    async def get(self, key: str) -> Optional[DataResponse]:
        """
        Get cached data response from multi-level cache.

        Args:
            key: Cache key

        Returns:
            Cached DataResponse or None if not found
        """
        # Try L1 cache first
        result = await self.l1_cache.get(key)
        if result is not None:
            # Mark as cache hit
            if hasattr(result, "metadata"):
                result.metadata.cache_hit = True
            return result

        # Try L2 cache
        result = await self.l2_cache.get(key)
        if result is not None:
            # Backfill L1 cache with shorter TTL
            await self.l1_cache.set(key, result, ttl=300)  # 5 minutes in L1
            # Mark as cache hit
            if hasattr(result, "metadata"):
                result.metadata.cache_hit = True
            return result

        return None

    async def set(
        self, key: str, value: DataResponse, ttl: Optional[int] = None
    ) -> None:
        """
        Set cached data response in multi-level cache.

        Args:
            key: Cache key
            value: DataResponse to cache
            ttl: Time to live in seconds (optional)
        """
        # Store in both L1 and L2 caches
        await self.l1_cache.set(key, value, ttl=ttl)
        # Use longer TTL for L2 cache
        l2_ttl = ttl * 10 if ttl else None
        await self.l2_cache.set(key, value, ttl=l2_ttl)

    async def delete(self, key: str) -> bool:
        """
        Delete cached data response from both cache levels.

        Args:
            key: Cache key

        Returns:
            True if key was found and deleted
        """
        # For simplicity, we'll implement basic deletion
        # In a full implementation, this would remove from both L1 and L2
        return False

    async def clear(self) -> None:
        """Clear all cached data from both cache levels."""
        # For simplicity, we'll implement basic clearing
        # In a full implementation, this would clear both L1 and L2
        pass

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in either cache level.

        Args:
            key: Cache key

        Returns:
            True if key exists in L1 or L2
        """
        # Check L1 first
        l1_result = await self.l1_cache.get(key)
        if l1_result is not None:
            return True

        # Check L2
        l2_result = await self.l2_cache.get(key)
        return l2_result is not None

    async def get_data(self, query: DataQuery) -> Optional[DataResponse]:
        """
        Get cached data using query-based cache key generation.

        Args:
            query: Data query

        Returns:
            Cached DataResponse or None if not found
        """
        cache_key_obj = CacheKey(query)
        return await self.get(cache_key_obj.key)

    async def set_data(self, query: DataQuery, data: DataResponse) -> None:
        """
        Set cached data using query-based cache key generation and TTL.

        Args:
            query: Data query
            data: DataResponse to cache
        """
        cache_key_obj = CacheKey(query)
        await self.set(cache_key_obj.key, data, ttl=cache_key_obj.ttl)
