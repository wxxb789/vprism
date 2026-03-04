"""Test unified database schema (6 tables with proper types and constraints)."""

import duckdb
import pytest

from vprism.core.data.storage.schema import (
    TABLE_NAMES,
    DatabaseSchema,
    create_all_tables,
    drop_all_tables,
)


class TestDatabaseSchema:
    """Test new 6-table schema design."""

    @pytest.fixture
    def schema(self) -> DatabaseSchema:
        """Create in-memory schema."""
        s = DatabaseSchema(":memory:")
        yield s
        s.close()

    def test_all_six_tables_exist(self, schema: DatabaseSchema) -> None:
        """Verify exactly 6 tables are created."""
        tables = schema.conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_type = 'BASE TABLE'").fetchall()
        table_names = sorted(t[0] for t in tables)

        expected = sorted(TABLE_NAMES)
        assert table_names == expected

    # ── assets table ────────────────────────────────────────────────────────

    def test_insert_and_query_asset(self, schema: DatabaseSchema) -> None:
        """Test assets table insert and query."""
        schema.conn.execute("""
            INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz)
            VALUES ('AAPL', 'us', 'Apple Inc.', 'stock', 'USD', 'America/New_York')
        """)

        result = schema.conn.execute("SELECT symbol, name, currency, exchange_tz FROM assets WHERE symbol = 'AAPL'").fetchone()

        assert result is not None
        assert result[0] == "AAPL"
        assert result[1] == "Apple Inc."
        assert result[2] == "USD"
        assert result[3] == "America/New_York"

    def test_assets_composite_pk(self, schema: DatabaseSchema) -> None:
        """Test composite primary key (symbol, market) on assets."""
        schema.conn.execute("""
            INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz)
            VALUES ('000001', 'cn', 'Ping An Bank', 'stock', 'CNY', 'Asia/Shanghai')
        """)

        # Same symbol, different market should work
        schema.conn.execute("""
            INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz)
            VALUES ('000001', 'hk', 'Some HK Stock', 'stock', 'HKD', 'Asia/Hong_Kong')
        """)

        count = schema.conn.execute("SELECT COUNT(*) FROM assets WHERE symbol = '000001'").fetchone()
        assert count[0] == 2

        # Duplicate (symbol, market) should fail
        with pytest.raises(duckdb.Error):
            schema.conn.execute("""
                INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz)
                VALUES ('000001', 'cn', 'Duplicate', 'stock', 'CNY', 'Asia/Shanghai')
            """)

    def test_assets_no_default_currency(self, schema: DatabaseSchema) -> None:
        """Currency must be explicit - no default CNY problem."""
        with pytest.raises(duckdb.Error):
            schema.conn.execute("""
                INSERT INTO assets (symbol, market, name, asset_type, exchange_tz)
                VALUES ('MSFT', 'us', 'Microsoft', 'stock', 'America/New_York')
            """)

    # ── ohlcv table ─────────────────────────────────────────────────────────

    def test_insert_and_query_ohlcv(self, schema: DatabaseSchema) -> None:
        """Test ohlcv table with DECIMAL prices."""
        # Insert prerequisite asset
        schema.conn.execute("""
            INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz)
            VALUES ('AAPL', 'us', 'Apple Inc.', 'stock', 'USD', 'America/New_York')
        """)

        schema.conn.execute("""
            INSERT INTO ohlcv (symbol, market, ts, timeframe, provider, open, high, low, close, volume)
            VALUES ('AAPL', 'us', '2024-01-02 09:30:00', '1d', 'yahoo',
                    185.12345678, 186.99999999, 184.00000001, 185.50000000, 50000000)
        """)

        result = schema.conn.execute("SELECT open, high, low, close, volume FROM ohlcv WHERE symbol = 'AAPL'").fetchone()

        assert result is not None
        # DECIMAL(18,8) preserves precision
        assert float(result[0]) == pytest.approx(185.12345678)
        assert float(result[1]) == pytest.approx(186.99999999)
        assert result[4] == 50000000

    def test_ohlcv_composite_pk(self, schema: DatabaseSchema) -> None:
        """Test composite PK prevents duplicate OHLCV records."""
        schema.conn.execute("""
            INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz)
            VALUES ('AAPL', 'us', 'Apple', 'stock', 'USD', 'America/New_York')
        """)

        schema.conn.execute("""
            INSERT INTO ohlcv (symbol, market, ts, timeframe, provider, close, volume)
            VALUES ('AAPL', 'us', '2024-01-02', '1d', 'yahoo', 185.50, 1000)
        """)

        # Same provider, same time, same timeframe → should fail
        with pytest.raises(duckdb.Error):
            schema.conn.execute("""
                INSERT INTO ohlcv (symbol, market, ts, timeframe, provider, close, volume)
                VALUES ('AAPL', 'us', '2024-01-02', '1d', 'yahoo', 186.00, 2000)
            """)

        # Different provider → should succeed
        schema.conn.execute("""
            INSERT INTO ohlcv (symbol, market, ts, timeframe, provider, close, volume)
            VALUES ('AAPL', 'us', '2024-01-02', '1d', 'alpha_vantage', 185.51, 999)
        """)

    def test_ohlcv_check_constraints(self, schema: DatabaseSchema) -> None:
        """Test CHECK constraints: low <= high, open > 0."""
        schema.conn.execute("""
            INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz)
            VALUES ('TEST', 'us', 'Test', 'stock', 'USD', 'America/New_York')
        """)

        # low > high should fail
        with pytest.raises(duckdb.Error):
            schema.conn.execute("""
                INSERT INTO ohlcv (symbol, market, ts, timeframe, provider, open, high, low, close)
                VALUES ('TEST', 'us', '2024-01-02', '1d', 'test', 10.0, 9.0, 11.0, 10.0)
            """)

        # open = 0 should fail
        with pytest.raises(duckdb.Error):
            schema.conn.execute("""
                INSERT INTO ohlcv (symbol, market, ts, timeframe, provider, open, high, low, close)
                VALUES ('TEST', 'us', '2024-01-03', '1d', 'test', 0.0, 10.0, 9.0, 10.0)
            """)

        # NULL open should be OK
        schema.conn.execute("""
            INSERT INTO ohlcv (symbol, market, ts, timeframe, provider, high, low, close)
            VALUES ('TEST', 'us', '2024-01-04', '1d', 'test', 10.0, 9.0, 10.0)
        """)

    def test_ohlcv_fk_to_assets(self, schema: DatabaseSchema) -> None:
        """Test foreign key from ohlcv to assets."""
        # Insert without parent asset should fail
        with pytest.raises(duckdb.Error):
            schema.conn.execute("""
                INSERT INTO ohlcv (symbol, market, ts, timeframe, provider, close)
                VALUES ('NONEXISTENT', 'us', '2024-01-02', '1d', 'yahoo', 100.0)
            """)

    # ── provider_health table ───────────────────────────────────────────────

    def test_provider_health(self, schema: DatabaseSchema) -> None:
        """Test provider_health table."""
        schema.conn.execute("""
            INSERT INTO provider_health (name, status, req_count, err_count, p95_ms)
            VALUES ('yahoo', 'healthy', 1000, 5, 150.25)
        """)

        result = schema.conn.execute("SELECT name, status, req_count, err_count FROM provider_health WHERE name = 'yahoo'").fetchone()

        assert result is not None
        assert result[1] == "healthy"
        assert result[2] == 1000
        assert result[3] == 5

    def test_provider_health_status_check(self, schema: DatabaseSchema) -> None:
        """Test CHECK constraint on status column."""
        with pytest.raises(duckdb.Error):
            schema.conn.execute("""
                INSERT INTO provider_health (name, status)
                VALUES ('test', 'invalid_status')
            """)

    # ── cache table ─────────────────────────────────────────────────────────

    def test_cache_table(self, schema: DatabaseSchema) -> None:
        """Test cache table with JSON value and expiry."""
        schema.conn.execute("""
            INSERT INTO cache (key, value, expires_at)
            VALUES ('test_key', '{"data": [1, 2, 3]}', '2025-12-31 23:59:59')
        """)

        result = schema.conn.execute("SELECT key, value, hits FROM cache WHERE key = 'test_key'").fetchone()

        assert result is not None
        assert result[0] == "test_key"
        assert result[2] == 0  # default hits

    # ── query_log table ─────────────────────────────────────────────────────

    def test_query_log(self, schema: DatabaseSchema) -> None:
        """Test query_log table."""
        schema.conn.execute("""
            INSERT INTO query_log (id, query_hash, asset_type, market, symbols, provider, status, latency_ms)
            VALUES ('q-001', 'abc123', 'stock', 'us', 'AAPL,MSFT', 'yahoo', 'ok', 150)
        """)

        result = schema.conn.execute("SELECT id, status, latency_ms FROM query_log WHERE id = 'q-001'").fetchone()

        assert result is not None
        assert result[1] == "ok"
        assert result[2] == 150

    def test_query_log_status_check(self, schema: DatabaseSchema) -> None:
        """Test CHECK constraint on query_log status."""
        with pytest.raises(duckdb.Error):
            schema.conn.execute("""
                INSERT INTO query_log (id, query_hash, status)
                VALUES ('q-bad', 'hash', 'invalid')
            """)

    # ── symbol_mappings table ───────────────────────────────────────────────

    def test_symbol_mappings(self, schema: DatabaseSchema) -> None:
        """Test symbol_mappings with FK to assets."""
        schema.conn.execute("""
            INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz)
            VALUES ('000001', 'cn', 'Ping An', 'stock', 'CNY', 'Asia/Shanghai')
        """)

        schema.conn.execute("""
            INSERT INTO symbol_mappings (canonical, raw_symbol, market, source, confidence)
            VALUES ('000001', '000001.SZ', 'cn', 'akshare', 0.95)
        """)

        result = schema.conn.execute("SELECT canonical, raw_symbol, confidence FROM symbol_mappings").fetchone()

        assert result is not None
        assert result[0] == "000001"
        assert result[1] == "000001.SZ"
        assert float(result[2]) == pytest.approx(0.95)

    # ── drop and recreate ───────────────────────────────────────────────────

    def test_drop_and_recreate(self, schema: DatabaseSchema) -> None:
        """Test drop_all_tables and create_all_tables."""
        drop_all_tables(schema.conn)

        # Tables should be gone
        tables = schema.conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_type = 'BASE TABLE'").fetchall()
        assert len(tables) == 0

        # Recreate
        create_all_tables(schema.conn)

        tables = schema.conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_type = 'BASE TABLE'").fetchall()
        assert len(tables) == 6
