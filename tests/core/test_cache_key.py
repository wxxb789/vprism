"""
Tests for CacheKey class.

This module tests the cache key generation and TTL calculation logic,
ensuring deterministic key generation and appropriate TTL strategies.
"""

import hashlib
from datetime import datetime, timedelta

import pytest

from vprism.core.cache import CacheKey
from vprism.core.models import AssetType, DataQuery, MarketType, TimeFrame


class TestCacheKey:
    """Test cases for CacheKey class."""

    def test_cache_key_generation_basic(self):
        """Test basic cache key generation."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
        )

        cache_key = CacheKey(query)

        # Key should be deterministic
        assert isinstance(cache_key.key, str)
        assert len(cache_key.key) == 16  # SHA256 truncated to 16 chars

        # Same query should generate same key
        cache_key2 = CacheKey(query)
        assert cache_key.key == cache_key2.key

    def test_cache_key_generation_with_symbols_order(self):
        """Test that symbol order doesn't affect cache key."""
        query1 = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001", "000002", "000003"],
        )
        query2 = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000003", "000001", "000002"],
        )

        cache_key1 = CacheKey(query1)
        cache_key2 = CacheKey(query2)

        # Keys should be identical regardless of symbol order
        assert cache_key1.key == cache_key2.key

    def test_cache_key_generation_with_dates(self):
        """Test cache key generation with date ranges."""
        start_date = datetime(2024, 1, 1, 10, 0, 0)
        end_date = datetime(2024, 1, 31, 15, 30, 0)

        query = DataQuery(
            asset=AssetType.STOCK,
            start=start_date,
            end=end_date,
        )

        cache_key = CacheKey(query)

        # Key should include date information
        assert isinstance(cache_key.key, str)

        # Different dates should generate different keys
        query2 = DataQuery(
            asset=AssetType.STOCK,
            start=start_date + timedelta(days=1),
            end=end_date,
        )
        cache_key2 = CacheKey(query2)

        assert cache_key.key != cache_key2.key

    def test_cache_key_generation_minimal_query(self):
        """Test cache key generation with minimal query."""
        query = DataQuery(asset=AssetType.STOCK)
        cache_key = CacheKey(query)

        assert isinstance(cache_key.key, str)
        assert len(cache_key.key) == 16

    def test_ttl_calculation_tick_data(self):
        """Test TTL calculation for tick data."""
        query = DataQuery(
            asset=AssetType.STOCK,
            timeframe=TimeFrame.TICK,
        )

        cache_key = CacheKey(query)

        assert cache_key.ttl == 5  # 5 seconds for tick data

    def test_ttl_calculation_minute_data(self):
        """Test TTL calculation for minute data."""
        query = DataQuery(
            asset=AssetType.STOCK,
            timeframe=TimeFrame.MINUTE_1,
        )

        cache_key = CacheKey(query)

        assert cache_key.ttl == 60  # 1 minute for 1-minute data

    def test_ttl_calculation_5minute_data(self):
        """Test TTL calculation for 5-minute data."""
        query = DataQuery(
            asset=AssetType.STOCK,
            timeframe=TimeFrame.MINUTE_5,
        )

        cache_key = CacheKey(query)

        assert cache_key.ttl == 300  # 5 minutes for 5-minute data

    def test_ttl_calculation_daily_data(self):
        """Test TTL calculation for daily data."""
        query = DataQuery(
            asset=AssetType.STOCK,
            timeframe=TimeFrame.DAY_1,
        )

        cache_key = CacheKey(query)

        assert cache_key.ttl == 3600  # 1 hour for daily data

    def test_ttl_calculation_weekly_data(self):
        """Test TTL calculation for weekly data."""
        query = DataQuery(
            asset=AssetType.STOCK,
            timeframe=TimeFrame.WEEK_1,
        )

        cache_key = CacheKey(query)

        assert cache_key.ttl == 86400  # 1 day for weekly data

    def test_ttl_calculation_no_timeframe(self):
        """Test TTL calculation when no timeframe is specified."""
        query = DataQuery(asset=AssetType.STOCK)

        cache_key = CacheKey(query)

        assert cache_key.ttl == 300  # 5 minutes default

    def test_ttl_calculation_unknown_timeframe(self):
        """Test TTL calculation for unknown timeframe."""
        query = DataQuery(
            asset=AssetType.STOCK,
            timeframe=TimeFrame.QUARTER_1,  # Not in TTL map
        )

        cache_key = CacheKey(query)

        assert cache_key.ttl == 300  # 5 minutes default

    def test_cache_key_with_provider(self):
        """Test cache key generation with specific provider."""
        query1 = DataQuery(
            asset=AssetType.STOCK,
            provider="tushare",
        )
        query2 = DataQuery(
            asset=AssetType.STOCK,
            provider="yahoo",
        )

        cache_key1 = CacheKey(query1)
        cache_key2 = CacheKey(query2)

        # Different providers should generate different keys
        assert cache_key1.key != cache_key2.key

    def test_cache_key_deterministic_across_instances(self):
        """Test that cache keys are deterministic across different instances."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001", "000002"],
            timeframe=TimeFrame.DAY_1,
            provider="tushare",
        )

        # Generate keys multiple times
        keys = [CacheKey(query).key for _ in range(10)]

        # All keys should be identical
        assert len(set(keys)) == 1

    def test_cache_key_content_validation(self):
        """Test that cache key properly encodes query content."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
            provider="tushare",
        )

        cache_key = CacheKey(query)

        # Manually generate expected key content
        parts = [
            "asset:stock",
            "market:cn",
            "symbols:000001",
            "provider:tushare",
            "timeframe:1d",
            "",  # start
            "",  # end
            "",  # limit
        ]
        content = "|".join(filter(None, parts))
        expected_key = hashlib.sha256(content.encode()).hexdigest()[:16]

        assert cache_key.key == expected_key
