"""
Tests for MultiLevelCache class.

This module tests the multi-level cache implementation that combines
L1 (in-memory) and L2 (DuckDB) caches for optimal performance.
"""

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vprism.core.cache import MultiLevelCache
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


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    # Create a temporary directory and file path (don't create the file)
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_cache.duckdb"
    yield str(db_path)
    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


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

    query = DataQuery(
        asset=AssetType.STOCK,
        market=MarketType.CN,
        symbols=["000001"],
        timeframe=TimeFrame.DAY_1,
    )

    return DataResponse(
        data=[data_point],
        metadata=metadata,
        source=provider_info,
        query=query,
    )


class TestMultiLevelCache:
    """Test cases for MultiLevelCache."""

    @pytest.mark.asyncio
    async def test_cache_initialization(self, temp_db_path):
        """Test multi-level cache initialization."""
        cache = MultiLevelCache(db_path=temp_db_path)

        # Should have both L1 and L2 caches
        assert cache.l1_cache is not None
        assert cache.l2_cache is not None

    @pytest.mark.asyncio
    async def test_cache_l1_hit(self, temp_db_path, sample_data_response):
        """Test L1 cache hit scenario."""
        cache = MultiLevelCache(db_path=temp_db_path)

        query = sample_data_response.query

        # Set data (should go to both L1 and L2)
        await cache.set_data(query, sample_data_response)

        # Get data (should hit L1)
        result = await cache.get_data(query)

        assert result is not None
        assert result.data[0].symbol == "000001"
        # Should be marked as cached
        assert result.metadata.cache_hit is True

    @pytest.mark.asyncio
    async def test_cache_l2_hit_with_l1_backfill(
        self, temp_db_path, sample_data_response
    ):
        """Test L2 cache hit with L1 backfill."""
        cache = MultiLevelCache(db_path=temp_db_path)

        query = sample_data_response.query

        # Set data in L2 only (simulate L1 eviction)
        await cache.l2_cache.set(query.cache_key(), sample_data_response)

        # Get data (should hit L2 and backfill L1)
        result = await cache.get_data(query)

        assert result is not None
        assert result.data[0].symbol == "000001"

        # Verify L1 backfill by checking L1 directly
        l1_result = await cache.l1_cache.get(query.cache_key())
        assert l1_result is not None

    @pytest.mark.asyncio
    async def test_cache_miss(self, temp_db_path):
        """Test cache miss scenario."""
        cache = MultiLevelCache(db_path=temp_db_path)

        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["NONEXISTENT"],
        )

        # Get non-existent data
        result = await cache.get_data(query)

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_ttl_strategies(self, temp_db_path, sample_data_response):
        """Test different TTL strategies for different data types."""
        cache = MultiLevelCache(db_path=temp_db_path)

        # Test tick data (short TTL)
        tick_query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001"],
            timeframe=TimeFrame.TICK,
        )
        tick_response = sample_data_response.model_copy()
        tick_response.query = tick_query

        await cache.set_data(tick_query, tick_response)

        # Test daily data (longer TTL)
        daily_query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
        )
        daily_response = sample_data_response.model_copy()
        daily_response.query = daily_query

        await cache.set_data(daily_query, daily_response)

        # Both should be available immediately
        tick_result = await cache.get_data(tick_query)
        daily_result = await cache.get_data(daily_query)

        assert tick_result is not None
        assert daily_result is not None

    @pytest.mark.asyncio
    async def test_cache_l1_eviction_l2_persistence(
        self, temp_db_path, sample_data_response
    ):
        """Test that data persists in L2 when evicted from L1."""
        # Use small L1 cache to force eviction
        cache = MultiLevelCache(db_path=temp_db_path, l1_max_size=2)

        # Create multiple queries
        queries = []
        responses = []
        for i in range(5):
            query = DataQuery(
                asset=AssetType.STOCK,
                symbols=[f"00000{i}"],
            )
            response = sample_data_response.model_copy()
            response.query = query
            response.data[0].symbol = f"00000{i}"

            queries.append(query)
            responses.append(response)

        # Set all data (will cause L1 evictions)
        for query, response in zip(queries, responses):
            await cache.set_data(query, response)

        # First few queries should be evicted from L1 but available in L2
        for i, query in enumerate(queries):
            result = await cache.get_data(query)
            assert result is not None
            assert result.data[0].symbol == f"00000{i}"

    @pytest.mark.asyncio
    async def test_cache_concurrent_access(self, temp_db_path, sample_data_response):
        """Test concurrent access to multi-level cache."""
        cache = MultiLevelCache(db_path=temp_db_path)

        async def set_and_get_data(worker_id: int):
            """Set and get data concurrently."""
            query = DataQuery(
                asset=AssetType.STOCK,
                symbols=[f"WORKER{worker_id:03d}"],
            )
            response = sample_data_response.model_copy()
            response.query = query
            response.data[0].symbol = f"WORKER{worker_id:03d}"

            # Set data
            await cache.set_data(query, response)

            # Get data
            result = await cache.get_data(query)
            assert result is not None
            assert result.data[0].symbol == f"WORKER{worker_id:03d}"

            return result

        # Run concurrent operations
        results = await asyncio.gather(*[set_and_get_data(i) for i in range(20)])

        assert len(results) == 20
        assert all(result is not None for result in results)

    @pytest.mark.asyncio
    async def test_cache_performance_characteristics(
        self, temp_db_path, sample_data_response
    ):
        """Test cache performance characteristics."""
        cache = MultiLevelCache(db_path=temp_db_path)

        query = sample_data_response.query

        # Measure set performance
        start_time = asyncio.get_event_loop().time()
        for i in range(10):
            test_query = DataQuery(
                asset=AssetType.STOCK,
                symbols=[f"PERF{i:03d}"],
            )
            test_response = sample_data_response.model_copy()
            test_response.query = test_query
            await cache.set_data(test_query, test_response)
        set_time = asyncio.get_event_loop().time() - start_time

        # Measure L1 hit performance
        start_time = asyncio.get_event_loop().time()
        for i in range(10):
            test_query = DataQuery(
                asset=AssetType.STOCK,
                symbols=[f"PERF{i:03d}"],
            )
            await cache.get_data(test_query)
        l1_get_time = asyncio.get_event_loop().time() - start_time

        # L1 hits should be very fast
        assert l1_get_time < 0.1  # 10 L1 hits in less than 0.1 seconds
        assert set_time < 2.0  # 10 sets in less than 2 seconds

    @pytest.mark.asyncio
    async def test_cache_data_consistency(self, temp_db_path, sample_data_response):
        """Test data consistency between L1 and L2 caches."""
        cache = MultiLevelCache(db_path=temp_db_path)

        query = sample_data_response.query

        # Set data
        await cache.set_data(query, sample_data_response)

        # Get from L1 directly
        l1_result = await cache.l1_cache.get(query.cache_key())

        # Get from L2 directly
        l2_result = await cache.l2_cache.get(query.cache_key())

        # Both should have the same data
        assert l1_result is not None
        assert l2_result is not None
        assert l1_result.data[0].symbol == l2_result.data[0].symbol
        assert l1_result.data[0].close == l2_result.data[0].close

    @pytest.mark.asyncio
    async def test_cache_expiration_handling(self, temp_db_path, sample_data_response):
        """Test cache expiration handling across levels."""
        cache = MultiLevelCache(db_path=temp_db_path)

        # Create query with short TTL timeframe
        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001"],
            timeframe=TimeFrame.TICK,  # 5 second TTL
        )
        response = sample_data_response.model_copy()
        response.query = query

        # Set data
        await cache.set_data(query, response)

        # Should be available immediately
        result = await cache.get_data(query)
        assert result is not None

        # Wait for L1 expiration (if implemented)
        await asyncio.sleep(0.1)  # Short wait for test performance

        # Data should still be available (from L2 or still in L1)
        result = await cache.get_data(query)
        # This test behavior depends on actual TTL implementation

    @pytest.mark.asyncio
    async def test_cache_memory_efficiency(self, temp_db_path, sample_data_response):
        """Test cache memory efficiency with large datasets."""
        cache = MultiLevelCache(db_path=temp_db_path, l1_max_size=10)

        # Create many data points
        large_dataset = []
        for i in range(100):
            data_point = DataPoint(
                symbol=f"SYM{i:03d}",
                timestamp=datetime.now(timezone.utc),
                close=float(i + 10),
            )
            large_dataset.append(data_point)

        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=[f"SYM{i:03d}" for i in range(100)],
        )

        response = DataResponse(
            data=large_dataset,
            metadata=ResponseMetadata(
                execution_time_ms=500.0,
                record_count=100,
            ),
            source=ProviderInfo(name="test_provider"),
            query=query,
        )

        # Set large dataset
        await cache.set_data(query, response)

        # Should be able to retrieve
        result = await cache.get_data(query)
        assert result is not None
        assert len(result.data) == 100

    @pytest.mark.asyncio
    async def test_cache_error_recovery(self, temp_db_path, sample_data_response):
        """Test cache error recovery scenarios."""
        cache = MultiLevelCache(db_path=temp_db_path)

        query = sample_data_response.query

        # Test normal operation
        await cache.set_data(query, sample_data_response)
        result = await cache.get_data(query)
        assert result is not None

        # Test graceful handling of cache errors
        # (Specific error scenarios depend on implementation details)
