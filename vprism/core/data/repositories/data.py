"""Data repository - persistence abstraction for OHLCV data."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from loguru import logger

from vprism.core.data.repositories.base import Repository
from vprism.core.data.storage.database import DatabaseManager
from vprism.core.data.storage.models import OHLCVRecord
from vprism.core.models.base import DataPoint
from vprism.core.models.query import DataQuery


class DataRepository(Repository[OHLCVRecord]):
    """Persistence layer for OHLCV data using the unified schema."""

    def __init__(self, db_manager: DatabaseManager | None = None) -> None:
        self.db = db_manager or DatabaseManager()

    def from_data_point(self, dp: DataPoint, provider: str, timeframe: str = "1d") -> OHLCVRecord:
        """Convert a DataPoint to an OHLCVRecord.

        Args:
            dp: The data point to convert.
            provider: Provider name that sourced the data.
            timeframe: Timeframe identifier.

        Returns:
            An OHLCVRecord ready for persistence.
        """
        return OHLCVRecord.from_data_point(dp, provider, timeframe)

    async def save(self, entity: OHLCVRecord) -> str:
        """Save a single OHLCV record."""
        self.db.insert_ohlcv(
            symbol=entity.symbol,
            market=entity.market,
            ts=entity.ts,
            timeframe=entity.timeframe,
            provider=entity.provider,
            open=entity.open,
            high=entity.high,
            low=entity.low,
            close=entity.close,
            volume=entity.volume,
            amount=entity.amount,
            batch_id=entity.batch_id,
        )
        return f"{entity.symbol}:{entity.market}:{entity.ts.isoformat()}"

    async def save_batch(self, entities: list[OHLCVRecord]) -> list[str]:
        """Save a batch of OHLCV records."""
        if not entities:
            return []

        data = [
            {
                "symbol": r.symbol,
                "market": r.market,
                "ts": r.ts,
                "timeframe": r.timeframe,
                "provider": r.provider,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                "amount": r.amount,
                "batch_id": r.batch_id,
            }
            for r in entities
        ]
        count = self.db.batch_insert_ohlcv(data)
        logger.info(f"Batch saved {count} OHLCV records")
        return [f"{r.symbol}:{r.market}:{r.ts.isoformat()}" for r in entities]

    async def find_by_id(self, entity_id: str) -> OHLCVRecord | None:
        """Find a record by composite key (symbol:market:ts)."""
        parts = entity_id.split(":")
        if len(parts) < 3:
            return None
        rows = self.db.query_ohlcv(symbol=parts[0], market=parts[1], limit=1)
        if rows:
            return self._row_to_record(rows[0])
        return None

    async def find_all(self, limit: int | None = None, offset: int = 0) -> list[OHLCVRecord]:
        """Find all OHLCV records."""
        rows = self.db.query_ohlcv(limit=limit)
        return [self._row_to_record(r) for r in rows]

    async def find_by_query(self, query: DataQuery) -> list[OHLCVRecord]:
        """Find OHLCV records matching a query.

        Args:
            query: The data query to match against.

        Returns:
            List of matching OHLCV records.
        """
        results: list[OHLCVRecord] = []
        symbols = query.symbols or []

        for symbol in symbols:
            rows = self.db.query_ohlcv(
                symbol=symbol,
                market=query.market.value if query.market else None,
                timeframe=query.timeframe.value if query.timeframe else None,
                start=query.start,
                end=query.end,
            )
            results.extend(self._row_to_record(r) for r in rows)

        return results

    async def delete(self, entity_id: str) -> bool:
        """Delete a record."""
        return True

    async def exists(self, entity_id: str) -> bool:
        """Check if a record exists."""
        record = await self.find_by_id(entity_id)
        return record is not None

    def health_check(self) -> bool:
        """Check if the repository is healthy."""
        try:
            self.db.connection.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the repository."""
        self.db.close()

    @staticmethod
    def _row_to_record(row: dict[str, Any]) -> OHLCVRecord:
        """Convert a database row dict to an OHLCVRecord."""
        return OHLCVRecord(
            symbol=row["symbol"],
            market=row["market"],
            ts=row["ts"],
            timeframe=row["timeframe"],
            provider=row["provider"],
            open=Decimal(str(row["open"])) if row.get("open") is not None else None,
            high=Decimal(str(row["high"])) if row.get("high") is not None else None,
            low=Decimal(str(row["low"])) if row.get("low") is not None else None,
            close=Decimal(str(row["close"])) if row.get("close") is not None else None,
            volume=int(row["volume"]) if row.get("volume") is not None else None,
            amount=Decimal(str(row["amount"])) if row.get("amount") is not None else None,
            batch_id=row.get("batch_id"),
        )
