"""
Tests for ThreadSafeInMemoryCache class.

This module tests the L1 in-memory cache implementation,
focusing on thread safety, LRU behavior, and expiration.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from vprism.core.cache import ThreadSafeInMemoryCache
from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    MarketType,
    ProviderInfo,
    ResponseMetadata,
)


@pytest.fixture
def sample_data_response():
    """Create a sample DataResponse for testing."""
    data_point = DataPoint(
        symbol="000001",
        timestamp=datetime.now(timezone.utc),
        open=10.0,
        high=10.5,
        low=9.5,
        close=10.2,
        volume=1000000,
    )

    metadata = ResponseMetadata(
        execution_time_ms=100.0,
        record_count=1,
    )

    provider_info = ProviderInfo(
        name="test_provider",
        version="1.0.0",
    )

    query = DataQuery(asset=AssetType.STOCK, symbols=["000001"])

    return DataResponse(
        data=[data_point],
        metadata=metadata,
        source=provider_info,
        query=query,
    )


class TestThreadSafeInMemoryCache:
    """Test cases for ThreadSafeInMemoryCache."""

    @pytest.mark.asyncio
    async def test_cache_basic_operations(self, sample_data_response):
        """Test basic cache get/set operations."""
        cache = ThreadSafeInMemoryCache(max_size=10)

        # Initially empty
        result = await cache.get("test_key")
        assert result is None

        # Set and get
        await cache.set("test_key", sample_data_response)
        result = await cache.get("test_key")
        assert result is not None
        assert result.data[0].symbol == "000001"

    @pytest.mark.asyncio
    async def test_cache_expiration(self, sample_data_response):
        """Test cache expiration functionality."""
        cache = ThreadSafeInMemoryCache(max_size=10)

        # Set with short TTL
        await cache.set("test_key", sample_data_response, ttl=1)

        # Should be available immediately
        result = await cache.get("test_key")
        assert result is not None

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Should be expired
        result = await cache.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self, sample_data_response):
        """Test LRU eviction when cache is full."""
        cache = ThreadSafeInMemoryCache(max_size=3)

        # Fill cache to capacity
        await cache.set("key1", sample_data_response)
        await cache.set("key2", sample_data_response)
        await cache.set("key3", sample_data_response)

        # All keys should be present
        assert await cache.get("key1") is not None
        assert await cache.get("key2") is not None
        assert await cache.get("key3") is not None

        # Access key1 to make it most recently used
        await cache.get("key1")

        # Add new key, should evict key2 (least recently used)
        await cache.set("key4", sample_data_response)

        # key2 should be evicted, others should remain
        assert await cache.get("key1") is not None
        assert await cache.get("key2") is None
        assert await cache.get("key3") is not None
        assert await cache.get("key4") is not None

    @pytest.mark.asyncio
    async def test_cache_update_existing_key(self, sample_data_response):
        """Test updating an existing cache key."""
        cache = ThreadSafeInMemoryCache(max_size=10)

        # Set initial value
        await cache.set("test_key", sample_data_response)

        # Create modified response
        modified_response = sample_data_response.model_copy()
        modified_response.data[0].close = 15.0

        # Update the key
        await cache.set("test_key", modified_response)

        # Should get updated value
        result = await cache.get("test_key")
        assert result is not None
        assert result.data[0].close == 15.0

    @pytest.mark.asyncio
    async def test_cache_concurrent_access(self, sample_data_response):
        """Test concurrent access to cache."""
        cache = ThreadSafeInMemoryCache(max_size=100)

        async def set_data(key_suffix: int):
            """Set data with unique key."""
            await cache.set(f"key_{key_suffix}", sample_data_response)

        async def get_data(key_suffix: int):
            """Get data with unique key."""
            return await cache.get(f"key_{key_suffix}")

        # Concurrent sets
        await asyncio.gather(*[set_data(i) for i in range(50)])

        # Concurrent gets
        results = await asyncio.gather(*[get_data(i) for i in range(50)])

        # All results should be present
        assert all(result is not None for result in results)
        assert len(results) == 50

    @pytest.mark.asyncio
    async def test_cache_mixed_concurrent_operations(self, sample_data_response):
        """Test mixed concurrent operations (get/set)."""
        cache = ThreadSafeInMemoryCache(max_size=50)

        async def mixed_operations(worker_id: int):
            """Perform mixed get/set operations."""
            for i in range(10):
                key = f"worker_{worker_id}_key_{i}"
                await cache.set(key, sample_data_response)
                result = await cache.get(key)
                assert result is not None

        # Run multiple workers concurrently
        await asyncio.gather(*[mixed_operations(i) for i in range(5)])

    @pytest.mark.asyncio
    async def test_cache_expiration_cleanup(self, sample_data_response):
        """Test that expired entries are properly cleaned up."""
        cache = ThreadSafeInMemoryCache(max_size=10)

        # Set multiple keys with different TTLs
        await cache.set("short_ttl", sample_data_response, ttl=1)
        await cache.set("long_ttl", sample_data_response, ttl=10)
        await cache.set("no_ttl", sample_data_response)

        # Wait for short TTL to expire
        await asyncio.sleep(1.1)

        # Access expired key to trigger cleanup
        result = await cache.get("short_ttl")
        assert result is None

        # Other keys should still be present
        assert await cache.get("long_ttl") is not None
        assert await cache.get("no_ttl") is not None

        # Check internal state
        assert "short_ttl" not in cache.cache
        assert "short_ttl" not in cache.expiry

    @pytest.mark.asyncio
    async def test_cache_zero_max_size(self, sample_data_response):
        """Test cache behavior with zero max size."""
        cache = ThreadSafeInMemoryCache(max_size=0)

        # Should not store anything
        await cache.set("test_key", sample_data_response)
        result = await cache.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_lru_order_preservation(self, sample_data_response):
        """Test that LRU order is properly maintained."""
        cache = ThreadSafeInMemoryCache(max_size=3)

        # Add items in order
        await cache.set("key1", sample_data_response)
        await cache.set("key2", sample_data_response)
        await cache.set("key3", sample_data_response)

        # Access key1 (should move to end)
        await cache.get("key1")

        # Access key2 (should move to end)
        await cache.get("key2")

        # Add new key, should evict key3 (now least recently used)
        await cache.set("key4", sample_data_response)

        # Verify eviction
        assert await cache.get("key1") is not None
        assert await cache.get("key2") is not None
        assert await cache.get("key3") is None
        assert await cache.get("key4") is not None

    @pytest.mark.asyncio
    async def test_cache_ttl_none_handling(self, sample_data_response):
        """Test cache behavior when TTL is None."""
        cache = ThreadSafeInMemoryCache(max_size=10)

        # Set without TTL
        await cache.set("test_key", sample_data_response, ttl=None)

        # Should be available
        result = await cache.get("test_key")
        assert result is not None

        # Should not have expiry set
        assert "test_key" not in cache.expiry

    @pytest.mark.asyncio
    async def test_cache_performance_characteristics(self, sample_data_response):
        """Test cache performance characteristics."""
        cache = ThreadSafeInMemoryCache(max_size=1000)

        # Measure set performance
        start_time = asyncio.get_event_loop().time()
        for i in range(100):
            await cache.set(f"key_{i}", sample_data_response)
        set_time = asyncio.get_event_loop().time() - start_time

        # Measure get performance
        start_time = asyncio.get_event_loop().time()
        for i in range(100):
            await cache.get(f"key_{i}")
        get_time = asyncio.get_event_loop().time() - start_time

        # Operations should be reasonably fast
        assert set_time < 1.0  # 100 sets in less than 1 second
        assert get_time < 0.5  # 100 gets in less than 0.5 seconds
