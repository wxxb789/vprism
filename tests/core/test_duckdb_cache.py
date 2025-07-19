"""
Tests for SimpleDuckDBCache class.

This module tests the L2 DuckDB-based cache implementation,
focusing on persistence, query optimization, and data integrity.
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vprism.core.cache import SimpleDuckDBCache
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
        amount=10200000,
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


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc)

    return [
        DataPoint(
            symbol="000001",
            timestamp=base_time,
            open=10.0,
            high=10.5,
            low=9.5,
            close=10.2,
            volume=1000000,
            amount=10200000,
        ),
        DataPoint(
            symbol="000001",
            timestamp=base_time.replace(hour=10),
            open=10.2,
            high=10.8,
            low=10.0,
            close=10.6,
            volume=1200000,
            amount=12720000,
        ),
        DataPoint(
            symbol="000002",
            timestamp=base_time,
            open=20.0,
            high=21.0,
            low=19.5,
            close=20.5,
            volume=800000,
            amount=16400000,
        ),
    ]


class TestSimpleDuckDBCache:
    """Test cases for SimpleDuckDBCache."""

    @pytest.mark.asyncio
    async def test_cache_initialization(self, temp_db_path):
        """Test cache initialization and table creation."""
        cache = SimpleDuckDBCache(temp_db_path)

        # Database file should be created
        assert Path(temp_db_path).exists()

        # Tables should be created (test by attempting to query them)
        # This will be tested implicitly by other operations

    @pytest.mark.asyncio
    async def test_cache_basic_operations(self, temp_db_path, sample_data_response):
        """Test basic cache get/set operations."""
        cache = SimpleDuckDBCache(temp_db_path)

        # Initially empty
        result = await cache.get("test_key")
        assert result is None

        # Set and get
        await cache.set("test_key", sample_data_response)
        result = await cache.get("test_key")
        assert result is not None
        assert result.data[0].symbol == "000001"

    @pytest.mark.asyncio
    async def test_cache_expiration(self, temp_db_path, sample_data_response):
        """Test cache expiration functionality."""
        cache = SimpleDuckDBCache(temp_db_path)

        # Set with short TTL
        await cache.set("test_key", sample_data_response, ttl=1)

        # Should be available immediately
        result = await cache.get("test_key")
        assert result is not None

        # Simulate expiration by manually updating the database
        # (In real implementation, expired entries would be filtered out)
        import asyncio

        await asyncio.sleep(1.1)

        # Should handle expiration (implementation dependent)
        # This test will be refined based on actual implementation

    @pytest.mark.asyncio
    async def test_ohlcv_data_storage(self, temp_db_path, sample_ohlcv_data):
        """Test storage and retrieval of OHLCV data."""
        cache = SimpleDuckDBCache(temp_db_path)

        # Create query for daily data
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001", "000002"],
            timeframe=TimeFrame.DAY_1,
        )

        # Create response with OHLCV data
        response = DataResponse(
            data=sample_ohlcv_data,
            metadata=ResponseMetadata(
                execution_time_ms=150.0,
                record_count=len(sample_ohlcv_data),
            ),
            source=ProviderInfo(name="test_provider"),
            query=query,
        )

        # Store data
        await cache.set("ohlcv_key", response)

        # Retrieve data
        result = await cache.get("ohlcv_key")
        assert result is not None
        assert len(result.data) == 3
        assert result.data[0].symbol == "000001"
        assert result.data[2].symbol == "000002"

    @pytest.mark.asyncio
    async def test_intraday_data_storage(self, temp_db_path):
        """Test storage of intraday (minute-level) data."""
        cache = SimpleDuckDBCache(temp_db_path)

        # Create minute-level data
        base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc)
        intraday_data = [
            DataPoint(
                symbol="000001",
                timestamp=base_time,
                open=10.0,
                high=10.1,
                low=9.9,
                close=10.05,
                volume=100000,
            ),
            DataPoint(
                symbol="000001",
                timestamp=base_time.replace(minute=31),
                open=10.05,
                high=10.15,
                low=10.0,
                close=10.12,
                volume=120000,
            ),
        ]

        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001"],
            timeframe=TimeFrame.MINUTE_1,
        )

        response = DataResponse(
            data=intraday_data,
            metadata=ResponseMetadata(
                execution_time_ms=80.0,
                record_count=2,
            ),
            source=ProviderInfo(name="test_provider"),
            query=query,
        )

        # Store and retrieve
        await cache.set("intraday_key", response)
        result = await cache.get("intraday_key")

        assert result is not None
        assert len(result.data) == 2
        assert result.data[0].timestamp.minute == 30
        assert result.data[1].timestamp.minute == 31

    @pytest.mark.asyncio
    async def test_asset_info_storage(self, temp_db_path):
        """Test storage of asset information."""
        cache = SimpleDuckDBCache(temp_db_path)

        # This test will be implemented based on the actual asset info storage logic
        # For now, we'll test basic functionality

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
        )

        # Create response with asset metadata
        data_point = DataPoint(
            symbol="000001",
            timestamp=datetime.now(timezone.utc),
            open=10.0,
            close=10.2,
        )
        data_point.extra_fields = {
            "name": "平安银行",
            "exchange": "SZSE",
            "sector": "金融",
        }

        response = DataResponse(
            data=[data_point],
            metadata=ResponseMetadata(
                execution_time_ms=50.0,
                record_count=1,
            ),
            source=ProviderInfo(name="test_provider"),
            query=query,
        )

        await cache.set("asset_info_key", response)
        result = await cache.get("asset_info_key")

        assert result is not None
        assert result.data[0].extra_fields["name"] == "平安银行"

    @pytest.mark.asyncio
    async def test_cache_key_parsing(self, temp_db_path):
        """Test cache key parsing for different query types."""
        cache = SimpleDuckDBCache(temp_db_path)

        # Test different query types
        stock_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            timeframe=TimeFrame.DAY_1,
        )

        bond_query = DataQuery(
            asset=AssetType.BOND,
            market=MarketType.CN,
            timeframe=TimeFrame.DAY_1,
        )

        # The cache should be able to handle different query types
        # This will be tested through the actual get/set operations

        # Create sample responses
        stock_response = DataResponse(
            data=[DataPoint(symbol="000001", timestamp=datetime.now(timezone.utc))],
            metadata=ResponseMetadata(execution_time_ms=100.0, record_count=1),
            source=ProviderInfo(name="test_provider"),
            query=stock_query,
        )

        bond_response = DataResponse(
            data=[DataPoint(symbol="123456", timestamp=datetime.now(timezone.utc))],
            metadata=ResponseMetadata(execution_time_ms=100.0, record_count=1),
            source=ProviderInfo(name="test_provider"),
            query=bond_query,
        )

        # Store different types
        await cache.set("stock_key", stock_response)
        await cache.set("bond_key", bond_response)

        # Retrieve and verify
        stock_result = await cache.get("stock_key")
        bond_result = await cache.get("bond_key")

        assert stock_result is not None
        assert bond_result is not None
        assert stock_result.data[0].symbol == "000001"
        assert bond_result.data[0].symbol == "123456"

    @pytest.mark.asyncio
    async def test_cache_persistence(self, temp_db_path, sample_data_response):
        """Test that cache data persists across instances."""
        # First instance
        cache1 = SimpleDuckDBCache(temp_db_path)
        await cache1.set("persist_key", sample_data_response)

        # Second instance (simulating restart)
        cache2 = SimpleDuckDBCache(temp_db_path)
        result = await cache2.get("persist_key")

        assert result is not None
        assert result.data[0].symbol == "000001"

    @pytest.mark.asyncio
    async def test_cache_multiple_symbols(self, temp_db_path):
        """Test caching data for multiple symbols."""
        cache = SimpleDuckDBCache(temp_db_path)

        # Create multi-symbol data
        multi_symbol_data = [
            DataPoint(
                symbol="000001",
                timestamp=datetime.now(timezone.utc),
                close=10.0,
            ),
            DataPoint(
                symbol="000002",
                timestamp=datetime.now(timezone.utc),
                close=20.0,
            ),
            DataPoint(
                symbol="000003",
                timestamp=datetime.now(timezone.utc),
                close=30.0,
            ),
        ]

        query = DataQuery(
            asset=AssetType.STOCK,
            symbols=["000001", "000002", "000003"],
        )

        response = DataResponse(
            data=multi_symbol_data,
            metadata=ResponseMetadata(
                execution_time_ms=200.0,
                record_count=3,
            ),
            source=ProviderInfo(name="test_provider"),
            query=query,
        )

        await cache.set("multi_symbol_key", response)
        result = await cache.get("multi_symbol_key")

        assert result is not None
        assert len(result.data) == 3
        symbols = {point.symbol for point in result.data}
        assert symbols == {"000001", "000002", "000003"}

    @pytest.mark.asyncio
    async def test_cache_error_handling(self, temp_db_path):
        """Test cache error handling for invalid operations."""
        cache = SimpleDuckDBCache(temp_db_path)

        # Test getting non-existent key
        result = await cache.get("non_existent_key")
        assert result is None

        # Test setting with invalid data (this should be handled gracefully)
        # The actual error handling will depend on implementation details
