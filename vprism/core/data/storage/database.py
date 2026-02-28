"""Database manager - unified data access for the new 6-table schema."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from vprism.core.data.storage.schema import setup_database

if TYPE_CHECKING:
    from collections.abc import Generator

    from duckdb import DuckDBPyConnection


class DatabaseManager:
    """Unified database manager for the 6-table schema."""

    def __init__(self, db_path: str = ":memory:") -> None:
        """Initialize the database manager.

        Args:
            db_path: Path to DuckDB database file (or ':memory:' for in-memory).
        """
        self.db_path = db_path
        self.connection: DuckDBPyConnection = setup_database(db_path)

    def close(self) -> None:
        """Close the database connection."""
        if self.connection:
            self.connection.close()

    # ── OHLCV operations ─────────────────────────────────────────────────────

    def insert_ohlcv(
        self,
        symbol: str,
        market: str,
        ts: datetime,
        timeframe: str,
        provider: str,
        *,
        open: Decimal | None = None,
        high: Decimal | None = None,
        low: Decimal | None = None,
        close: Decimal | None = None,
        volume: int | None = None,
        amount: Decimal | None = None,
        batch_id: str | None = None,
    ) -> None:
        """Insert a single OHLCV record."""
        self.connection.execute(
            """INSERT INTO ohlcv (symbol, market, ts, timeframe, provider,
               open, high, low, close, volume, amount, batch_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT DO NOTHING""",
            [symbol, market, ts, timeframe, provider, open, high, low, close, volume, amount, batch_id],
        )

    def batch_insert_ohlcv(self, records: list[dict[str, Any]]) -> int:
        """Batch insert OHLCV records.

        Args:
            records: List of dicts with keys matching ohlcv columns.

        Returns:
            Number of records inserted.
        """
        if not records:
            return 0

        data = [
            [
                r["symbol"],
                r["market"],
                r["ts"],
                r["timeframe"],
                r["provider"],
                r.get("open"),
                r.get("high"),
                r.get("low"),
                r.get("close"),
                r.get("volume"),
                r.get("amount"),
                r.get("batch_id"),
            ]
            for r in records
        ]
        self.connection.executemany(
            """INSERT INTO ohlcv (symbol, market, ts, timeframe, provider,
               open, high, low, close, volume, amount, batch_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT DO NOTHING""",
            data,
        )
        return len(data)

    def query_ohlcv(
        self,
        symbol: str | None = None,
        market: str | None = None,
        timeframe: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        provider: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query OHLCV records with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)
        if market:
            conditions.append("market = ?")
            params.append(market)
        if timeframe:
            conditions.append("timeframe = ?")
            params.append(timeframe)
        if start:
            conditions.append("ts >= ?")
            params.append(start)
        if end:
            conditions.append("ts <= ?")
            params.append(end)
        if provider:
            conditions.append("provider = ?")
            params.append(provider)

        where = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM ohlcv WHERE {where} ORDER BY ts DESC"
        if limit:
            query += f" LIMIT {limit}"

        result = self.connection.execute(query, params).fetchall()
        columns = [desc[0] for desc in self.connection.description] if self.connection.description else []
        return [dict(zip(columns, row, strict=False)) for row in result]

    # ── Asset operations ─────────────────────────────────────────────────────

    def upsert_asset(
        self,
        symbol: str,
        market: str,
        name: str,
        asset_type: str,
        currency: str,
        exchange_tz: str,
        **kwargs: Any,
    ) -> None:
        """Insert or update an asset record."""
        self.connection.execute(
            """INSERT INTO assets (symbol, market, name, asset_type, currency, exchange_tz,
               exchange, sector, industry, is_active, first_traded)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (symbol, market) DO UPDATE SET
                 name = EXCLUDED.name,
                 asset_type = EXCLUDED.asset_type,
                 currency = EXCLUDED.currency,
                 exchange_tz = EXCLUDED.exchange_tz,
                 updated_at = CURRENT_TIMESTAMP""",
            [
                symbol,
                market,
                name,
                asset_type,
                currency,
                exchange_tz,
                kwargs.get("exchange"),
                kwargs.get("sector"),
                kwargs.get("industry"),
                kwargs.get("is_active", True),
                kwargs.get("first_traded"),
            ],
        )

    def get_asset(self, symbol: str, market: str) -> dict[str, Any] | None:
        """Get asset by composite key."""
        result = self.connection.execute(
            "SELECT * FROM assets WHERE symbol = ? AND market = ?",
            [symbol, market],
        ).fetchone()
        if result:
            columns = [desc[0] for desc in self.connection.description] if self.connection.description else []
            return dict(zip(columns, result, strict=False))
        return None

    # ── Provider health operations ───────────────────────────────────────────

    def upsert_provider_health(self, name: str, status: str = "healthy", **kwargs: Any) -> None:
        """Insert or update provider health record."""
        self.connection.execute(
            """INSERT INTO provider_health (name, status, last_check, req_count, err_count, p95_ms)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (name) DO UPDATE SET
                 status = EXCLUDED.status,
                 last_check = EXCLUDED.last_check,
                 req_count = EXCLUDED.req_count,
                 err_count = EXCLUDED.err_count,
                 p95_ms = EXCLUDED.p95_ms,
                 updated_at = CURRENT_TIMESTAMP""",
            [
                name,
                status,
                kwargs.get("last_check"),
                kwargs.get("req_count", 0),
                kwargs.get("err_count", 0),
                kwargs.get("p95_ms"),
            ],
        )

    # ── Cache operations ─────────────────────────────────────────────────────

    def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Set a cache entry."""
        import json

        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        self.connection.execute(
            """INSERT INTO cache (key, value, expires_at)
               VALUES (?, ?::JSON, ?)
               ON CONFLICT (key) DO UPDATE SET
                 value = EXCLUDED.value,
                 expires_at = EXCLUDED.expires_at,
                 created_at = CURRENT_TIMESTAMP""",
            [key, json.dumps(value), expires_at],
        )

    def cache_get(self, key: str) -> Any | None:
        """Get a cache entry (returns None if expired/missing)."""
        import json

        result = self.connection.execute(
            "SELECT value, expires_at FROM cache WHERE key = ? AND expires_at > CURRENT_TIMESTAMP",
            [key],
        ).fetchone()
        if result:
            self.connection.execute(
                "UPDATE cache SET hits = hits + 1 WHERE key = ?",
                [key],
            )
            return json.loads(result[0]) if isinstance(result[0], str) else result[0]
        return None

    def cache_cleanup(self) -> int:
        """Remove expired cache entries."""
        result = self.connection.execute("DELETE FROM cache WHERE expires_at <= CURRENT_TIMESTAMP")
        return max(0, result.rowcount) if result and result.rowcount is not None else 0

    # ── Query log operations ─────────────────────────────────────────────────

    def log_query(
        self,
        query_hash: str,
        *,
        asset_type: str | None = None,
        market: str | None = None,
        symbols: str | None = None,
        provider: str | None = None,
        status: str = "pending",
        latency_ms: int | None = None,
        cache_hit: bool = False,
    ) -> str:
        """Log a query execution."""
        query_id = str(uuid.uuid4())
        self.connection.execute(
            """INSERT INTO query_log (id, query_hash, asset_type, market, symbols,
               provider, status, latency_ms, cache_hit)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [query_id, query_hash, asset_type, market, symbols, provider, status, latency_ms, cache_hit],
        )
        return query_id

    # ── Stats and maintenance ────────────────────────────────────────────────

    def get_database_stats(self) -> dict[str, Any]:
        """Get row counts for all tables."""
        stats: dict[str, Any] = {}
        from vprism.core.data.storage.schema import TABLE_NAMES

        for table in TABLE_NAMES:
            try:
                result = self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                stats[f"{table}_count"] = result[0] if result else 0
            except Exception:
                stats[f"{table}_count"] = 0
        return stats

    def vacuum(self) -> None:
        """Compact the database."""
        self.connection.execute("CHECKPOINT")

    def analyze(self) -> None:
        """Update statistics."""
        self.connection.execute("ANALYZE")

    @contextmanager
    def transaction(self) -> Generator[None]:
        """Transaction context manager."""
        try:
            self.connection.execute("BEGIN")
            yield
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise

    def __enter__(self) -> DatabaseManager:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        self.close()
