"""
Tests for DataRepository implementation.

This module tests the repository pattern for data storage,
including data persistence, retrieval, batch operations,
and data compression/incremental updates.
"""

import tempfile
from datetime import datetime, timezone, date
from decimal import Decimal
from pathlib import Path

import pytest

from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    MarketType,
    TimeFrame,
)
from vprism.core.repository import DuckDBDataRepository


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_repository.duckdb"
    yield str(db_path)
    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def repository(temp_db_path):
    """Create a DuckDB repository instance for testing."""
    return DuckDBDataRepository(temp_db_path)


@pytest.fixture
def sample_data_points():
    """Create sample data points for testing."""
    base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc)
    return [
        DataPoint(
            symbol="000001",
            timestamp=base_time,
            open=Decimal("10.00"),
            high=Decimal("10.50"),
            low=Decimal("9.50"),
            close=Decimal("10.20"),
            volume=Decimal("1000000"),
            amount=Decimal("10200000"),
        ),
        DataPoint(
            symbol="000001",
            timestamp=base_time.replace(hour=10),
            open=Decimal("10.20"),
            high=Decimal("10.80"),
            low=Decimal("10.00"),
            close=Decimal("10.60"),
            volume=Decimal("1200000"),
            amount=Decimal("12720000"),
        ),
        DataPoint(
            symbol="000002",
            timestamp=base_time,
            open=Decimal("20.00"),
            high=Decimal("21.00"),
            low=Decimal("19.50"),
            close=Decimal("20.50"),
            volume=Decimal("800000"),
            amount=Decimal("16400000"),
        ),
    ]


@pytest.fixture
def sample_daily_data_points():
    """Create sample daily data points for testing."""
    base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        DataPoint(
            symbol="000001",
            timestamp=base_date,
            open=Decimal("10.00"),
            high=Decimal("10.50"),
            low=Decimal("9.50"),
            close=Decimal("10.20"),
            volume=Decimal("1000000"),
            amount=Decimal("10200000"),
        ),
        DataPoint(
            symbol="000001",
            timestamp=base_date.replace(day=2),
            open=Decimal("10.20"),
            high=Decimal("10.80"),
            low=Decimal("10.00"),
            close=Decimal("10.60"),
            volume=Decimal("1200000"),
            amount=Decimal("12720000"),
        ),
        DataPoint(
            symbol="000002",
            timestamp=base_date,
            open=Decimal("20.00"),
            high=Decimal("21.00"),
            low=Decimal("19.50"),
            close=Decimal("20.50"),
            volume=Decimal("800000"),
            amount=Decimal("16400000"),
        ),
    ]


class TestDuckDBDataRepository:
    """Test cases for DuckDB data repository implementation."""

    @pytest.mark.asyncio
    async def test_repository_initialization(self, repository, temp_db_path):
        """Test repository initialization and database setup."""
        # Repository should be initialized
        assert repository is not None
        assert repository.db_path == temp_db_path

        # Database file should be created
        assert Path(temp_db_path).exists()

    @pytest.mark.asyncio
    async def test_store_data_basic(self, repository, sample_data_points):
        """Test basic data storage functionality."""
        # Store data points
        await repository.store_data(sample_data_points)

        # Verify data was stored
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001", "000002"],
        )

        retrieved_data = await repository.retrieve_data(query)

        assert len(retrieved_data) == 3

        # Check that we have data for both symbols
        symbols = {point.symbol for point in retrieved_data}
        assert "000001" in symbols
        assert "000002" in symbols

    @pytest.mark.asyncio
    async def test_store_data_daily_vs_intraday(
        self, repository, sample_daily_data_points, sample_data_points
    ):
        """Test that daily and intraday data are stored in appropriate tables."""
        # Store daily data (timestamps at midnight)
        await repository.store_data(sample_daily_data_points)

        # Store intraday data (timestamps with specific times)
        await repository.store_data(sample_data_points)

        # Query daily data
        daily_query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
        )
        daily_data = await repository.retrieve_data(daily_query)

        # Query intraday data
        intraday_query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001"],
            timeframe=TimeFrame.MINUTE_1,
        )
        intraday_data = await repository.retrieve_data(intraday_query)

        # Should have different amounts of data
        assert len(daily_data) >= 2  # At least 2 daily records for 000001
        assert len(intraday_data) >= 2  # At least 2 intraday records for 000001

    @pytest.mark.asyncio
    async def test_retrieve_data_by_symbol(self, repository, sample_data_points):
        """Test data retrieval filtered by symbol."""
        # Store data
        await repository.store_data(sample_data_points)

        # Query specific symbol
        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001"],
        )

        retrieved_data = await repository.retrieve_data(query)

        # Should only get data for 000001
        assert len(retrieved_data) == 2
        assert all(point.symbol == "000001" for point in retrieved_data)

    @pytest.mark.asyncio
    async def test_retrieve_data_by_date_range(self, repository, sample_data_points):
        """Test data retrieval filtered by date range."""
        # Store data
        await repository.store_data(sample_data_points)

        # Query with date range
        start_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 9, 45, 0, tzinfo=timezone.utc)

        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001"],
            start=start_time,
            end=end_time,
        )

        retrieved_data = await repository.retrieve_data(query)

        # Should only get data within the time range
        assert len(retrieved_data) == 1  # Only the 9:30 record
        assert retrieved_data[0].timestamp.hour == 9
        assert retrieved_data[0].timestamp.minute == 30

    @pytest.mark.asyncio
    async def test_retrieve_data_by_market(self, repository, sample_data_points):
        """Test data retrieval filtered by market."""
        # Store data
        await repository.store_data(sample_data_points)

        # Query specific market
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
        )

        retrieved_data = await repository.retrieve_data(query)

        # Should get all data (all samples are CN market)
        assert len(retrieved_data) == 3

    @pytest.mark.asyncio
    async def test_retrieve_data_with_limit(self, repository, sample_data_points):
        """Test data retrieval with limit."""
        # Store data
        await repository.store_data(sample_data_points)

        # Query with limit
        query = DataQuery(
            asset=AssetType.STOCK,
            limit=2,
        )

        retrieved_data = await repository.retrieve_data(query)

        # Should only get limited number of records
        assert len(retrieved_data) == 2

    @pytest.mark.asyncio
    async def test_retrieve_data_empty_result(self, repository):
        """Test data retrieval with no matching records."""
        # Query non-existent data
        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["NONEXISTENT"],
        )

        retrieved_data = await repository.retrieve_data(query)

        # Should return empty list
        assert len(retrieved_data) == 0

    @pytest.mark.asyncio
    async def test_delete_data_by_symbol(self, repository, sample_data_points):
        """Test data deletion by symbol."""
        # Store data
        await repository.store_data(sample_data_points)

        # Delete data for specific symbol
        delete_query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001"],
        )

        deleted_count = await repository.delete_data(delete_query)

        # Should have deleted 2 records for 000001
        assert deleted_count == 2

        # Verify data was deleted
        retrieve_query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001"],
        )

        remaining_data = await repository.retrieve_data(retrieve_query)
        assert len(remaining_data) == 0

        # Verify other data still exists
        other_query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000002"],
        )

        other_data = await repository.retrieve_data(other_query)
        assert len(other_data) == 1

    @pytest.mark.asyncio
    async def test_delete_data_by_date_range(self, repository, sample_data_points):
        """Test data deletion by date range."""
        # Store data
        await repository.store_data(sample_data_points)

        # Delete data within specific date range
        start_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 9, 45, 0, tzinfo=timezone.utc)

        delete_query = DataQuery(
            asset=AssetType.STOCK,
            start=start_time,
            end=end_time,
        )

        deleted_count = await repository.delete_data(delete_query)

        # Should have deleted records within the time range
        assert deleted_count >= 1

        # Verify remaining data is outside the range
        retrieve_query = DataQuery(asset=AssetType.STOCK)
        remaining_data = await repository.retrieve_data(retrieve_query)

        for point in remaining_data:
            assert point.timestamp < start_time or point.timestamp > end_time

    @pytest.mark.asyncio
    async def test_batch_operations(self, repository):
        """Test batch data operations for performance."""
        # Create large batch of data
        batch_size = 100
        batch_data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc)

        for i in range(batch_size):
            data_point = DataPoint(
                symbol=f"SYM{i:03d}",
                timestamp=base_time.replace(minute=30 + i % 60, hour=9 + i // 60),
                open=Decimal("10.00") + Decimal(str(i * 0.01)),
                high=Decimal("10.50") + Decimal(str(i * 0.01)),
                low=Decimal("9.50") + Decimal(str(i * 0.01)),
                close=Decimal("10.20") + Decimal(str(i * 0.01)),
                volume=Decimal("1000000"),
            )
            batch_data.append(data_point)

        # Store batch data
        await repository.store_data(batch_data)

        # Verify all data was stored
        query = DataQuery(asset=AssetType.STOCK)
        retrieved_data = await repository.retrieve_data(query)

        assert len(retrieved_data) == batch_size

    @pytest.mark.asyncio
    async def test_data_upsert_behavior(self, repository, sample_data_points):
        """Test data upsert (insert or update) behavior."""
        # Store initial data
        await repository.store_data(sample_data_points)

        # Modify one data point and store again
        modified_point = sample_data_points[0].model_copy()
        modified_point.close = Decimal("11.00")  # Changed close price

        await repository.store_data([modified_point])

        # Retrieve data
        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001"],
        )

        retrieved_data = await repository.retrieve_data(query)

        # Should still have same number of records (upsert, not insert)
        assert len(retrieved_data) == 2

        # Find the modified record
        modified_record = next(
            (
                point
                for point in retrieved_data
                if point.timestamp == modified_point.timestamp
            ),
            None,
        )

        assert modified_record is not None
        assert modified_record.close == Decimal("11.00")

    @pytest.mark.asyncio
    async def test_data_compression_storage(self, repository):
        """Test data compression for storage efficiency."""
        # Create data with repetitive patterns (good for compression)
        compressed_data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc)

        for i in range(50):
            # Create repetitive data pattern
            data_point = DataPoint(
                symbol="COMPRESS_TEST",
                timestamp=base_time.replace(minute=30 + i),
                open=Decimal("10.00"),  # Same values
                high=Decimal("10.50"),
                low=Decimal("9.50"),
                close=Decimal("10.20"),
                volume=Decimal("1000000"),
            )
            compressed_data.append(data_point)

        # Store compressed data
        await repository.store_data(compressed_data)

        # Retrieve and verify
        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["COMPRESS_TEST"],
        )

        retrieved_data = await repository.retrieve_data(query)

        assert len(retrieved_data) == 50
        # Verify data integrity after compression
        assert all(point.open == Decimal("10.00") for point in retrieved_data)

    @pytest.mark.asyncio
    async def test_incremental_updates(self, repository, sample_data_points):
        """Test incremental data updates."""
        # Store initial data
        await repository.store_data(sample_data_points[:2])  # First 2 points

        # Add incremental data
        await repository.store_data([sample_data_points[2]])  # Third point

        # Verify all data is present
        query = DataQuery(asset=AssetType.STOCK)
        retrieved_data = await repository.retrieve_data(query)

        assert len(retrieved_data) == 3

        # Verify incremental data is correct
        symbols = {point.symbol for point in retrieved_data}
        assert symbols == {"000001", "000002"}

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, repository):
        """Test concurrent data operations."""
        import asyncio

        async def store_batch(batch_id: int):
            """Store a batch of data concurrently."""
            batch_data = []
            base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc)

            for i in range(10):
                data_point = DataPoint(
                    symbol=f"BATCH{batch_id}_SYM{i:02d}",
                    timestamp=base_time.replace(minute=30 + i),
                    open=Decimal("10.00"),
                    high=Decimal("10.50"),
                    low=Decimal("9.50"),
                    close=Decimal("10.20"),
                    volume=Decimal("1000000"),
                )
                batch_data.append(data_point)

            await repository.store_data(batch_data)
            return len(batch_data)

        # Run concurrent operations
        tasks = [store_batch(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # Verify all batches were stored
        total_expected = sum(results)

        query = DataQuery(asset=AssetType.STOCK)
        retrieved_data = await repository.retrieve_data(query)

        assert len(retrieved_data) == total_expected

    @pytest.mark.asyncio
    async def test_data_integrity_validation(self, repository):
        """Test data integrity validation during storage."""
        # Create data with potential integrity issues
        integrity_data = [
            DataPoint(
                symbol="INTEGRITY_TEST",
                timestamp=datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc),
                open=Decimal("10.00"),
                high=Decimal("9.00"),  # High < Open (potential issue)
                low=Decimal("11.00"),  # Low > Open (potential issue)
                close=Decimal("10.20"),
                volume=Decimal("1000000"),
            ),
        ]

        # Store data (should handle gracefully)
        await repository.store_data(integrity_data)

        # Verify data was stored despite integrity issues
        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["INTEGRITY_TEST"],
        )

        retrieved_data = await repository.retrieve_data(query)
        assert len(retrieved_data) == 1

    @pytest.mark.asyncio
    async def test_performance_characteristics(self, repository):
        """Test repository performance characteristics."""
        import time

        # Create performance test data
        perf_data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc)

        for i in range(1000):  # 1000 records
            data_point = DataPoint(
                symbol=f"PERF{i:04d}",
                timestamp=base_time.replace(minute=30 + i % 60, hour=9 + i // 60),
                open=Decimal("10.00"),
                high=Decimal("10.50"),
                low=Decimal("9.50"),
                close=Decimal("10.20"),
                volume=Decimal("1000000"),
            )
            perf_data.append(data_point)

        # Measure storage performance
        start_time = time.time()
        await repository.store_data(perf_data)
        storage_time = time.time() - start_time

        # Measure retrieval performance
        query = DataQuery(asset=AssetType.STOCK)
        start_time = time.time()
        retrieved_data = await repository.retrieve_data(query)
        retrieval_time = time.time() - start_time

        # Performance assertions (adjust based on requirements)
        assert storage_time < 10.0  # Should store 1000 records in less than 10 seconds
        assert (
            retrieval_time < 5.0
        )  # Should retrieve 1000 records in less than 5 seconds
        assert len(retrieved_data) == 1000

    @pytest.mark.asyncio
    async def test_error_handling(self, repository):
        """Test error handling in repository operations."""
        # Test with invalid data
        invalid_data = [
            DataPoint(
                symbol="",  # Empty symbol
                timestamp=datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc),
                open=Decimal("10.00"),
                close=Decimal("10.20"),
            ),
        ]

        # Should handle gracefully (may store or reject based on implementation)
        try:
            await repository.store_data(invalid_data)
        except Exception as e:
            # If it raises an exception, it should be a meaningful one
            assert str(e)  # Should have error message

        # Test with invalid query
        invalid_query = DataQuery(
            asset=AssetType.STOCK,
            start=datetime(2024, 12, 31, tzinfo=timezone.utc),
            end=datetime(2024, 1, 1, tzinfo=timezone.utc),  # End before start
        )

        # Should handle gracefully
        result = await repository.retrieve_data(invalid_query)
        assert isinstance(result, list)  # Should return empty list or valid data
