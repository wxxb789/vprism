"""Unified DuckDB schema definition.

6 tables with proper types, composite keys, constraints, and FK relationships.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    import duckdb
except ImportError:  # pragma: no cover
    duckdb = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

# ── Table DDL ────────────────────────────────────────────────────────────────

ASSETS_DDL = """
CREATE TABLE IF NOT EXISTS assets (
    symbol      VARCHAR NOT NULL,
    market      VARCHAR NOT NULL,
    name        VARCHAR NOT NULL,
    asset_type  VARCHAR NOT NULL,
    currency    VARCHAR NOT NULL,
    exchange    VARCHAR,
    exchange_tz VARCHAR NOT NULL,
    sector      VARCHAR,
    industry    VARCHAR,
    is_active   BOOLEAN DEFAULT TRUE,
    first_traded DATE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, market)
)
"""

OHLCV_DDL = """
CREATE TABLE IF NOT EXISTS ohlcv (
    symbol      VARCHAR NOT NULL,
    market      VARCHAR NOT NULL,
    ts          TIMESTAMP NOT NULL,
    timeframe   VARCHAR NOT NULL,
    provider    VARCHAR NOT NULL,
    open        DECIMAL(18,8),
    high        DECIMAL(18,8),
    low         DECIMAL(18,8),
    close       DECIMAL(18,8),
    volume      BIGINT,
    amount      DECIMAL(18,8),
    batch_id    VARCHAR,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, market, ts, timeframe, provider),
    CHECK (low <= high OR low IS NULL OR high IS NULL),
    CHECK (open > 0 OR open IS NULL),
    FOREIGN KEY (symbol, market) REFERENCES assets(symbol, market)
)
"""

OHLCV_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_ohlcv_ts ON ohlcv(symbol, market, ts)",
    "CREATE INDEX IF NOT EXISTS idx_ohlcv_batch ON ohlcv(batch_id)",
]

SYMBOL_MAPPINGS_DDL = """
CREATE TABLE IF NOT EXISTS symbol_mappings (
    canonical   VARCHAR NOT NULL,
    raw_symbol  VARCHAR NOT NULL,
    market      VARCHAR NOT NULL,
    source      VARCHAR NOT NULL,
    status      VARCHAR DEFAULT 'active' CHECK (status IN ('active','inactive','deprecated')),
    confidence  DECIMAL(3,2) CHECK (confidence BETWEEN 0 AND 1),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (canonical, raw_symbol, market, source),
    FOREIGN KEY (canonical, market) REFERENCES assets(symbol, market)
)
"""

PROVIDER_HEALTH_DDL = """
CREATE TABLE IF NOT EXISTS provider_health (
    name        VARCHAR PRIMARY KEY,
    status      VARCHAR NOT NULL DEFAULT 'healthy' CHECK (status IN ('healthy','degraded','down')),
    last_check  TIMESTAMP,
    req_count   BIGINT DEFAULT 0,
    err_count   BIGINT DEFAULT 0,
    p95_ms      DECIMAL(10,2),
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CACHE_DDL = """
CREATE TABLE IF NOT EXISTS cache (
    key         VARCHAR PRIMARY KEY,
    value       JSON NOT NULL,
    hits        BIGINT DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP NOT NULL
)
"""

CACHE_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cache_expiry ON cache(expires_at)",
]

QUERY_LOG_DDL = """
CREATE TABLE IF NOT EXISTS query_log (
    id          VARCHAR PRIMARY KEY,
    query_hash  VARCHAR NOT NULL,
    asset_type  VARCHAR,
    market      VARCHAR,
    symbols     VARCHAR,
    provider    VARCHAR,
    status      VARCHAR DEFAULT 'pending' CHECK (status IN ('pending','ok','error')),
    latency_ms  INTEGER,
    cache_hit   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# ── Ordered table creation ───────────────────────────────────────────────────

ALL_TABLE_DDL: list[str] = [
    ASSETS_DDL,
    OHLCV_DDL,
    SYMBOL_MAPPINGS_DDL,
    PROVIDER_HEALTH_DDL,
    CACHE_DDL,
    QUERY_LOG_DDL,
]

ALL_INDEX_DDL: list[str] = [
    *OHLCV_INDICES,
    *CACHE_INDICES,
]

TABLE_NAMES: list[str] = [
    "assets",
    "ohlcv",
    "symbol_mappings",
    "provider_health",
    "cache",
    "query_log",
]


def create_all_tables(conn: DuckDBPyConnection) -> None:
    """Create all tables and indices in the database.

    Args:
        conn: An active DuckDB connection.
    """
    for ddl in ALL_TABLE_DDL:
        conn.execute(ddl)
    for idx in ALL_INDEX_DDL:
        conn.execute(idx)


def drop_all_tables(conn: DuckDBPyConnection) -> None:
    """Drop all managed tables (useful for testing/reset).

    Args:
        conn: An active DuckDB connection.
    """
    # Reverse order to respect FK dependencies
    for table in reversed(TABLE_NAMES):
        conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


class DatabaseSchema:
    """Database schema manager (backward compatibility wrapper)."""

    def __init__(self, db_path: str = ":memory:") -> None:
        if duckdb is None:
            msg = "duckdb is required but not installed"
            raise ImportError(msg)
        import os

        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.conn: DuckDBPyConnection = duckdb.connect(db_path)
        create_all_tables(self.conn)

    def get_table_stats(self) -> dict[str, int]:
        """Get row counts for all tables."""
        stats: dict[str, int] = {}
        for table in TABLE_NAMES:
            try:
                result = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                stats[table] = result[0] if result else 0
            except (RuntimeError, Exception) as exc:
                # Table may not exist or connection may be closed
                from loguru import logger

                logger.debug(f"Failed to get stats for table {table}: {exc}")
                stats[table] = 0
        return stats

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self, "conn") and self.conn:
            self.conn.close()

    def __enter__(self) -> DatabaseSchema:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        self.close()


def initialize_database(db_path: str = ":memory:") -> DuckDBPyConnection:
    """Initialize database schema and return the connection.

    Also aliased as ``setup_database`` for backward compatibility.
    """
    schema = DatabaseSchema(db_path)
    return schema.conn


# Backward-compatible alias
setup_database = initialize_database
