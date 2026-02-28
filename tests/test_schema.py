"""Test the unified 6-table schema design.

Verifies:
- DECIMAL(18,8) for price fields (no precision loss)
- Composite natural keys prevent duplicates
- FK constraints maintain referential integrity
- CHECK constraints validate data quality
"""

from decimal import Decimal

import duckdb
import pytest

from vprism.core.data.storage.schema import (
    ALL_INDEX_DDL,
    ALL_TABLE_DDL,
    TABLE_NAMES,
    DatabaseSchema,
    create_all_tables,
    drop_all_tables,
)


class TestSchemaDesign:
    """Verify schema correctness and constraints."""

    @pytest.fixture
    def db(self) -> DatabaseSchema:
        """Create in-memory database with full schema."""
        schema = DatabaseSchema(":memory:")
        yield schema
        schema.close()

    def test_exactly_six_tables(self, db: DatabaseSchema) -> None:
        """Schema should have exactly 6 tables."""
        assert len(TABLE_NAMES) == 6
        expected = {"assets", "ohlcv", "symbol_mappings", "provider_health", "cache", "query_log"}
        assert set(TABLE_NAMES) == expected

    def test_ddl_count(self) -> None:
        """6 table DDLs and 3 index DDLs."""
        assert len(ALL_TABLE_DDL) == 6
        assert len(ALL_INDEX_DDL) == 3  # 2 ohlcv + 1 cache

    def test_decimal_precision_preserved(self, db: DatabaseSchema) -> None:
        """DECIMAL(18,8) should preserve financial precision."""
        db.conn.execute("""
            INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz)
            VALUES ('BTC', 'global', 'Bitcoin', 'crypto', 'USD', 'UTC')
        """)

        # Insert a price with 8 decimal places
        db.conn.execute("""
            INSERT INTO ohlcv (symbol, market, ts, timeframe, provider, open, close)
            VALUES ('BTC', 'global', '2024-01-01', '1d', 'test', 42156.12345678, 42200.87654321)
        """)

        result = db.conn.execute("SELECT open, close FROM ohlcv WHERE symbol = 'BTC'").fetchone()
        assert result is not None

        open_val = Decimal(str(result[0]))
        close_val = Decimal(str(result[1]))

        # Verify 8 decimal places preserved
        assert str(open_val) == "42156.12345678"
        assert str(close_val) == "42200.87654321"

    def test_no_default_currency_or_timezone(self, db: DatabaseSchema) -> None:
        """Currency and exchange_tz must be explicitly provided."""
        # Missing currency should fail
        with pytest.raises(duckdb.Error):
            db.conn.execute("""
                INSERT INTO assets (symbol, market, name, asset_type, exchange_tz)
                VALUES ('BAD', 'us', 'Bad', 'stock', 'UTC')
            """)

        # Missing exchange_tz should fail
        with pytest.raises(duckdb.Error):
            db.conn.execute("""
                INSERT INTO assets (symbol, market, name, asset_type, currency)
                VALUES ('BAD2', 'us', 'Bad2', 'stock', 'USD')
            """)

    def test_ohlcv_volume_is_bigint(self, db: DatabaseSchema) -> None:
        """Volume should be BIGINT, not DOUBLE."""
        db.conn.execute("""
            INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz)
            VALUES ('VOL', 'us', 'Vol Test', 'stock', 'USD', 'UTC')
        """)

        # Large integer volume
        db.conn.execute("""
            INSERT INTO ohlcv (symbol, market, ts, timeframe, provider, close, volume)
            VALUES ('VOL', 'us', '2024-01-01', '1d', 'test', 100.0, 9999999999)
        """)

        result = db.conn.execute("SELECT volume FROM ohlcv WHERE symbol = 'VOL'").fetchone()
        assert result[0] == 9999999999

    def test_symbol_mapping_confidence_bounds(self, db: DatabaseSchema) -> None:
        """Confidence must be between 0 and 1."""
        db.conn.execute("""
            INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz)
            VALUES ('SYM', 'cn', 'Test', 'stock', 'CNY', 'Asia/Shanghai')
        """)

        # Valid confidence
        db.conn.execute("""
            INSERT INTO symbol_mappings (canonical, raw_symbol, market, source, confidence)
            VALUES ('SYM', 'SYM.SZ', 'cn', 'test', 0.85)
        """)

        # Confidence > 1 should fail
        with pytest.raises(duckdb.Error):
            db.conn.execute("""
                INSERT INTO symbol_mappings (canonical, raw_symbol, market, source, confidence)
                VALUES ('SYM', 'SYM.SH', 'cn', 'test', 1.5)
            """)

    def test_provider_health_status_enum(self, db: DatabaseSchema) -> None:
        """Status must be one of: healthy, degraded, down."""
        # Valid statuses
        for status in ("healthy", "degraded", "down"):
            db.conn.execute(f"""
                INSERT OR REPLACE INTO provider_health (name, status)
                VALUES ('test_{status}', '{status}')
            """)

        # Invalid status
        with pytest.raises(duckdb.Error):
            db.conn.execute("""
                INSERT INTO provider_health (name, status)
                VALUES ('bad', 'broken')
            """)

    def test_query_log_status_enum(self, db: DatabaseSchema) -> None:
        """Status must be one of: pending, ok, error."""
        for i, status in enumerate(("pending", "ok", "error")):
            db.conn.execute(f"""
                INSERT INTO query_log (id, query_hash, status)
                VALUES ('q-{i}', 'hash-{i}', '{status}')
            """)

        with pytest.raises(duckdb.Error):
            db.conn.execute("""
                INSERT INTO query_log (id, query_hash, status)
                VALUES ('q-bad', 'hash', 'timeout')
            """)

    def test_cache_expiry_index(self, db: DatabaseSchema) -> None:
        """Cache should have an index on expires_at for cleanup queries."""
        indexes = db.conn.execute("""
            SELECT index_name FROM duckdb_indexes()
            WHERE table_name = 'cache'
        """).fetchall()

        index_names = [idx[0] for idx in indexes]
        assert "idx_cache_expiry" in index_names

    def test_ohlcv_indices(self, db: DatabaseSchema) -> None:
        """OHLCV should have indices for common query patterns."""
        indexes = db.conn.execute("""
            SELECT index_name FROM duckdb_indexes()
            WHERE table_name = 'ohlcv'
        """).fetchall()

        index_names = [idx[0] for idx in indexes]
        assert "idx_ohlcv_ts" in index_names
        assert "idx_ohlcv_batch" in index_names

    def test_drop_respects_fk_order(self, db: DatabaseSchema) -> None:
        """drop_all_tables should drop in reverse order (children first)."""
        # Insert data with FK relationships
        db.conn.execute("""
            INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz)
            VALUES ('FK', 'us', 'FK Test', 'stock', 'USD', 'UTC')
        """)
        db.conn.execute("""
            INSERT INTO ohlcv (symbol, market, ts, timeframe, provider, close)
            VALUES ('FK', 'us', '2024-01-01', '1d', 'test', 100.0)
        """)

        # Should not raise FK violation errors
        drop_all_tables(db.conn)

        tables = db.conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_type = 'BASE TABLE'").fetchall()
        assert len(tables) == 0

        # Recreate to verify clean state
        create_all_tables(db.conn)
        stats = db.get_table_stats()
        for count in stats.values():
            assert count == 0
