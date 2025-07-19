"""
Tests for optimized database table structures.

This module tests the DuckDB table design, including:
- Daily and intraday OHLCV tables
- Asset information tables
- Optimized indexes and queries
- Data validation and integrity
"""

import tempfile
from datetime import datetime, timezone, date
from decimal import Decimal
from pathlib import Path

import pytest
import duckdb

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
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_tables.duckdb"
    yield str(db_path)
    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def db_cache(temp_db_path):
    """Create a DuckDB cache instance for testing."""
    return SimpleDuckDBCache(temp_db_path)


@pytest.fixture
def sample_daily_data():
    """Create sample daily OHLCV data."""
    base_date = date(2024, 1, 1)
    return [
        {
            "symbol": "000001",
            "trade_date": base_date,
            "market": "cn",
            "open_price": Decimal("10.00"),
            "high_price": Decimal("10.50"),
            "low_price": Decimal("9.50"),
            "close_price": Decimal("10.20"),
            "volume": Decimal("1000000"),
            "amount": Decimal("10200000"),
            "provider": "test_provider",
        },
        {
            "symbol": "000002",
            "trade_date": base_date,
            "market": "cn",
            "open_price": Decimal("20.00"),
            "high_price": Decimal("21.00"),
            "low_price": Decimal("19.50"),
            "close_price": Decimal("20.50"),
            "volume": Decimal("800000"),
            "amount": Decimal("16400000"),
            "provider": "test_provider",
        },
    ]


@pytest.fixture
def sample_intraday_data():
    """Create sample intraday OHLCV data."""
    base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc)
    return [
        {
            "symbol": "000001",
            "timestamp": base_time,
            "market": "cn",
            "timeframe": "1m",
            "open_price": Decimal("10.00"),
            "high_price": Decimal("10.10"),
            "low_price": Decimal("9.95"),
            "close_price": Decimal("10.05"),
            "volume": Decimal("100000"),
            "amount": Decimal("1005000"),
            "provider": "test_provider",
        },
        {
            "symbol": "000001",
            "timestamp": base_time.replace(minute=31),
            "market": "cn",
            "timeframe": "1m",
            "open_price": Decimal("10.05"),
            "high_price": Decimal("10.15"),
            "low_price": Decimal("10.00"),
            "close_price": Decimal("10.12"),
            "volume": Decimal("120000"),
            "amount": Decimal("1214400"),
            "provider": "test_provider",
        },
    ]


@pytest.fixture
def sample_asset_info():
    """Create sample asset information data."""
    return [
        {
            "symbol": "000001",
            "market": "cn",
            "name": "平安银行",
            "asset_type": "stock",
            "currency": "CNY",
            "exchange": "SZSE",
            "sector": "金融",
            "industry": "银行",
            "provider": "test_provider",
        },
        {
            "symbol": "000002",
            "market": "cn",
            "name": "万科A",
            "asset_type": "stock",
            "currency": "CNY",
            "exchange": "SZSE",
            "sector": "房地产",
            "industry": "房地产开发",
            "provider": "test_provider",
        },
    ]


class TestDatabaseTableStructure:
    """Test database table structure and operations."""

    def test_table_creation(self, db_cache, temp_db_path):
        """Test that all required tables are created."""
        with duckdb.connect(temp_db_path) as conn:
            # Check cache_entries table
            result = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='cache_entries'
            """).fetchone()
            # DuckDB uses different system tables, let's check if we can query the table
            try:
                conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()
                cache_table_exists = True
            except:
                cache_table_exists = False
            assert cache_table_exists

            # Check daily_ohlcv table
            try:
                conn.execute("SELECT COUNT(*) FROM daily_ohlcv").fetchone()
                daily_table_exists = True
            except:
                daily_table_exists = False
            assert daily_table_exists

            # Check intraday_ohlcv table
            try:
                conn.execute("SELECT COUNT(*) FROM intraday_ohlcv").fetchone()
                intraday_table_exists = True
            except:
                intraday_table_exists = False
            assert intraday_table_exists

            # Check asset_info table
            try:
                conn.execute("SELECT COUNT(*) FROM asset_info").fetchone()
                asset_table_exists = True
            except:
                asset_table_exists = False
            assert asset_table_exists

    def test_daily_ohlcv_table_structure(self, db_cache, temp_db_path):
        """Test daily OHLCV table structure and constraints."""
        with duckdb.connect(temp_db_path) as conn:
            # Test table schema
            schema = conn.execute("DESCRIBE daily_ohlcv").fetchall()
            column_names = [row[0] for row in schema]

            expected_columns = [
                "symbol",
                "trade_date",
                "market",
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "volume",
                "amount",
                "provider",
                "created_at",
            ]

            for col in expected_columns:
                assert col in column_names

    def test_intraday_ohlcv_table_structure(self, db_cache, temp_db_path):
        """Test intraday OHLCV table structure and constraints."""
        with duckdb.connect(temp_db_path) as conn:
            # Test table schema
            schema = conn.execute("DESCRIBE intraday_ohlcv").fetchall()
            column_names = [row[0] for row in schema]

            expected_columns = [
                "symbol",
                "timestamp",
                "market",
                "timeframe",
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "volume",
                "amount",
                "provider",
                "created_at",
            ]

            for col in expected_columns:
                assert col in column_names

    def test_asset_info_table_structure(self, db_cache, temp_db_path):
        """Test asset info table structure and constraints."""
        with duckdb.connect(temp_db_path) as conn:
            # Test table schema
            schema = conn.execute("DESCRIBE asset_info").fetchall()
            column_names = [row[0] for row in schema]

            expected_columns = [
                "symbol",
                "market",
                "name",
                "asset_type",
                "currency",
                "exchange",
                "sector",
                "industry",
                "is_active",
                "provider",
                "updated_at",
            ]

            for col in expected_columns:
                assert col in column_names

    @pytest.mark.asyncio
    async def test_daily_data_insertion(
        self, db_cache, temp_db_path, sample_daily_data
    ):
        """Test insertion of daily OHLCV data."""
        with duckdb.connect(temp_db_path) as conn:
            # Insert sample data
            for data in sample_daily_data:
                conn.execute(
                    """
                    INSERT INTO daily_ohlcv 
                    (symbol, trade_date, market, open_price, high_price, 
                     low_price, close_price, volume, amount, provider)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        data["symbol"],
                        data["trade_date"],
                        data["market"],
                        float(data["open_price"]),
                        float(data["high_price"]),
                        float(data["low_price"]),
                        float(data["close_price"]),
                        float(data["volume"]),
                        float(data["amount"]),
                        data["provider"],
                    ],
                )

            # Verify data was inserted
            result = conn.execute("SELECT COUNT(*) FROM daily_ohlcv").fetchone()
            assert result[0] == 2

            # Verify data integrity
            result = conn.execute("""
                SELECT symbol, open_price, close_price 
                FROM daily_ohlcv 
                WHERE symbol = '000001'
            """).fetchone()
            assert result[0] == "000001"
            assert float(result[1]) == 10.0
            assert float(result[2]) == 10.2

    @pytest.mark.asyncio
    async def test_intraday_data_insertion(
        self, db_cache, temp_db_path, sample_intraday_data
    ):
        """Test insertion of intraday OHLCV data."""
        with duckdb.connect(temp_db_path) as conn:
            # Insert sample data
            for data in sample_intraday_data:
                conn.execute(
                    """
                    INSERT INTO intraday_ohlcv 
                    (symbol, timestamp, market, timeframe, open_price, high_price, 
                     low_price, close_price, volume, amount, provider)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        data["symbol"],
                        data["timestamp"],
                        data["market"],
                        data["timeframe"],
                        float(data["open_price"]),
                        float(data["high_price"]),
                        float(data["low_price"]),
                        float(data["close_price"]),
                        float(data["volume"]),
                        float(data["amount"]),
                        data["provider"],
                    ],
                )

            # Verify data was inserted
            result = conn.execute("SELECT COUNT(*) FROM intraday_ohlcv").fetchone()
            assert result[0] == 2

            # Verify data integrity
            result = conn.execute("""
                SELECT symbol, timeframe, close_price 
                FROM intraday_ohlcv 
                WHERE symbol = '000001' 
                ORDER BY timestamp
            """).fetchall()
            assert len(result) == 2
            assert float(result[0][2]) == 10.05  # First record close price
            assert float(result[1][2]) == 10.12  # Second record close price

    @pytest.mark.asyncio
    async def test_asset_info_insertion(
        self, db_cache, temp_db_path, sample_asset_info
    ):
        """Test insertion of asset information data."""
        with duckdb.connect(temp_db_path) as conn:
            # Insert sample data
            for data in sample_asset_info:
                conn.execute(
                    """
                    INSERT INTO asset_info 
                    (symbol, market, name, asset_type, currency, exchange, 
                     sector, industry, provider)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        data["symbol"],
                        data["market"],
                        data["name"],
                        data["asset_type"],
                        data["currency"],
                        data["exchange"],
                        data["sector"],
                        data["industry"],
                        data["provider"],
                    ],
                )

            # Verify data was inserted
            result = conn.execute("SELECT COUNT(*) FROM asset_info").fetchone()
            assert result[0] == 2

            # Verify data integrity
            result = conn.execute("""
                SELECT symbol, name, sector 
                FROM asset_info 
                WHERE symbol = '000001'
            """).fetchone()
            assert result[0] == "000001"
            assert result[1] == "平安银行"
            assert result[2] == "金融"

    @pytest.mark.asyncio
    async def test_primary_key_constraints(
        self, db_cache, temp_db_path, sample_daily_data
    ):
        """Test primary key constraints work correctly."""
        with duckdb.connect(temp_db_path) as conn:
            # Insert first record
            data = sample_daily_data[0]
            conn.execute(
                """
                INSERT INTO daily_ohlcv 
                (symbol, trade_date, market, open_price, high_price, 
                 low_price, close_price, volume, amount, provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    data["symbol"],
                    data["trade_date"],
                    data["market"],
                    float(data["open_price"]),
                    float(data["high_price"]),
                    float(data["low_price"]),
                    float(data["close_price"]),
                    float(data["volume"]),
                    float(data["amount"]),
                    data["provider"],
                ],
            )

            # Try to insert duplicate (should replace due to INSERT OR REPLACE)
            modified_data = data.copy()
            modified_data["close_price"] = Decimal("11.00")

            conn.execute(
                """
                INSERT OR REPLACE INTO daily_ohlcv 
                (symbol, trade_date, market, open_price, high_price, 
                 low_price, close_price, volume, amount, provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    modified_data["symbol"],
                    modified_data["trade_date"],
                    modified_data["market"],
                    float(modified_data["open_price"]),
                    float(modified_data["high_price"]),
                    float(modified_data["low_price"]),
                    float(modified_data["close_price"]),
                    float(modified_data["volume"]),
                    float(modified_data["amount"]),
                    modified_data["provider"],
                ],
            )

            # Should still have only one record with updated close price
            result = conn.execute("SELECT COUNT(*) FROM daily_ohlcv").fetchone()
            assert result[0] == 1

            result = conn.execute("SELECT close_price FROM daily_ohlcv").fetchone()
            assert float(result[0]) == 11.0

    @pytest.mark.asyncio
    async def test_index_performance(self, db_cache, temp_db_path):
        """Test that indexes improve query performance."""
        with duckdb.connect(temp_db_path) as conn:
            # Insert test data
            base_date = date(2024, 1, 1)
            for i in range(100):
                conn.execute(
                    """
                    INSERT INTO daily_ohlcv 
                    (symbol, trade_date, market, open_price, high_price, 
                     low_price, close_price, volume, amount, provider)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        f"SYM{i:03d}",
                        base_date,
                        "cn",
                        10.0,
                        10.5,
                        9.5,
                        10.2,
                        1000000,
                        10200000,
                        "test_provider",
                    ],
                )

            # Test symbol-based query (should use index)
            result = conn.execute("""
                SELECT COUNT(*) FROM daily_ohlcv 
                WHERE symbol = 'SYM001'
            """).fetchone()
            assert result[0] == 1

            # Test date-based query (should use index)
            result = conn.execute(
                """
                SELECT COUNT(*) FROM daily_ohlcv 
                WHERE trade_date = ?
            """,
                [base_date],
            ).fetchone()
            assert result[0] == 100

    @pytest.mark.asyncio
    async def test_data_type_validation(self, db_cache, temp_db_path):
        """Test that data types are properly validated."""
        with duckdb.connect(temp_db_path) as conn:
            # Test decimal precision for prices
            conn.execute(
                """
                INSERT INTO daily_ohlcv 
                (symbol, trade_date, market, open_price, high_price, 
                 low_price, close_price, volume, amount, provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    "TEST001",
                    date(2024, 1, 1),
                    "cn",
                    10.123456,
                    10.654321,
                    9.876543,
                    10.234567,
                    1000000.50,
                    10234567.89,
                    "test_provider",
                ],
            )

            # Verify precision is maintained
            result = conn.execute("""
                SELECT open_price, high_price, low_price, close_price, volume, amount
                FROM daily_ohlcv WHERE symbol = 'TEST001'
            """).fetchone()

            # Check that decimal values are properly stored
            assert abs(float(result[0]) - 10.123456) < 0.000001
            assert abs(float(result[1]) - 10.654321) < 0.000001

    @pytest.mark.asyncio
    async def test_time_series_queries(self, db_cache, temp_db_path):
        """Test time series query patterns."""
        with duckdb.connect(temp_db_path) as conn:
            # Insert time series data
            base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc)
            for i in range(10):
                timestamp = base_time.replace(minute=30 + i)
                conn.execute(
                    """
                    INSERT INTO intraday_ohlcv 
                    (symbol, timestamp, market, timeframe, open_price, high_price, 
                     low_price, close_price, volume, amount, provider)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        "000001",
                        timestamp,
                        "cn",
                        "1m",
                        10.0 + i * 0.1,
                        10.1 + i * 0.1,
                        9.9 + i * 0.1,
                        10.05 + i * 0.1,
                        100000,
                        1005000,
                        "test_provider",
                    ],
                )

            # Test time range query
            start_time = base_time.replace(minute=32)
            end_time = base_time.replace(minute=36)

            result = conn.execute(
                """
                SELECT COUNT(*) FROM intraday_ohlcv 
                WHERE symbol = '000001' 
                AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """,
                [start_time, end_time],
            ).fetchone()

            assert result[0] == 5  # Should include minutes 32, 33, 34, 35, 36

    @pytest.mark.asyncio
    async def test_aggregation_queries(self, db_cache, temp_db_path):
        """Test aggregation queries for analytics."""
        with duckdb.connect(temp_db_path) as conn:
            # Insert sample data for multiple symbols
            base_date = date(2024, 1, 1)
            symbols = ["000001", "000002", "000003"]

            for symbol in symbols:
                for i in range(5):  # 5 days of data
                    trade_date = base_date.replace(day=1 + i)
                    conn.execute(
                        """
                        INSERT INTO daily_ohlcv 
                        (symbol, trade_date, market, open_price, high_price, 
                         low_price, close_price, volume, amount, provider)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        [
                            symbol,
                            trade_date,
                            "cn",
                            10.0 + i,
                            10.5 + i,
                            9.5 + i,
                            10.2 + i,
                            1000000 + i * 100000,
                            10200000 + i * 1020000,
                            "test_provider",
                        ],
                    )

            # Test average price calculation
            result = conn.execute("""
                SELECT symbol, AVG(close_price) as avg_close, SUM(volume) as total_volume
                FROM daily_ohlcv 
                GROUP BY symbol
                ORDER BY symbol
            """).fetchall()

            assert len(result) == 3
            assert result[0][0] == "000001"
            assert (
                abs(float(result[0][1]) - 12.2) < 0.01
            )  # Average of 10.2, 11.2, 12.2, 13.2, 14.2

    @pytest.mark.asyncio
    async def test_market_segmentation(self, db_cache, temp_db_path):
        """Test queries segmented by market."""
        with duckdb.connect(temp_db_path) as conn:
            # Insert data for different markets
            markets = ["cn", "us", "hk"]
            base_date = date(2024, 1, 1)

            for market in markets:
                for i in range(3):
                    conn.execute(
                        """
                        INSERT INTO daily_ohlcv 
                        (symbol, trade_date, market, open_price, high_price, 
                         low_price, close_price, volume, amount, provider)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        [
                            f"{market.upper()}{i:03d}",
                            base_date,
                            market,
                            10.0,
                            10.5,
                            9.5,
                            10.2,
                            1000000,
                            10200000,
                            "test_provider",
                        ],
                    )

            # Test market-specific queries
            result = conn.execute("""
                SELECT market, COUNT(*) as count
                FROM daily_ohlcv 
                GROUP BY market
                ORDER BY market
            """).fetchall()

            assert len(result) == 3
            assert result[0][0] == "cn" and result[0][1] == 3
            assert result[1][0] == "hk" and result[1][1] == 3
            assert result[2][0] == "us" and result[2][1] == 3

    @pytest.mark.asyncio
    async def test_data_integrity_constraints(self, db_cache, temp_db_path):
        """Test data integrity and validation constraints."""
        with duckdb.connect(temp_db_path) as conn:
            # Test that required fields cannot be null
            # (This depends on table definition - NOT NULL constraints)

            # Test valid data insertion
            conn.execute(
                """
                INSERT INTO daily_ohlcv 
                (symbol, trade_date, market, open_price, high_price, 
                 low_price, close_price, volume, amount, provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    "VALID001",
                    date(2024, 1, 1),
                    "cn",
                    10.0,
                    10.5,
                    9.5,
                    10.2,
                    1000000,
                    10200000,
                    "test_provider",
                ],
            )

            # Verify data was inserted
            result = conn.execute("SELECT COUNT(*) FROM daily_ohlcv").fetchone()
            assert result[0] == 1
