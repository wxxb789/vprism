"""
Data repository implementations for vprism.

This module implements the repository pattern for data persistence,
providing abstractions for storing and retrieving financial data
with support for batch operations, compression, and incremental updates.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import duckdb

from vprism.core.interfaces import DataRepository
from vprism.core.models import DataPoint, DataQuery, TimeFrame


class DuckDBDataRepository(DataRepository):
    """
    DuckDB-based implementation of the DataRepository interface.

    This repository provides efficient storage and retrieval of financial data
    using DuckDB's columnar storage format, with optimized table structures
    for different data types and time frequencies.
    """

    def __init__(self, db_path: str = "vprism_data.duckdb"):
        """
        Initialize the DuckDB data repository.

        Args:
            db_path: Path to the DuckDB database file
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database tables and indexes for data storage."""
        with duckdb.connect(self.db_path) as conn:
            # Daily OHLCV data table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_ohlcv (
                    symbol VARCHAR(32) NOT NULL,
                    trade_date DATE NOT NULL,
                    market VARCHAR(8) NOT NULL DEFAULT 'cn',
                    open_price DECIMAL(18,6) NOT NULL,
                    high_price DECIMAL(18,6) NOT NULL,
                    low_price DECIMAL(18,6) NOT NULL,
                    close_price DECIMAL(18,6) NOT NULL,
                    volume DECIMAL(20,2) NOT NULL,
                    amount DECIMAL(20,2),
                    provider VARCHAR(32) DEFAULT 'unknown',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, trade_date, market)
                )
            """)

            # Intraday OHLCV data table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intraday_ohlcv (
                    symbol VARCHAR(32) NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    market VARCHAR(8) NOT NULL DEFAULT 'cn',
                    timeframe VARCHAR(8) NOT NULL DEFAULT '1m',
                    open_price DECIMAL(18,6) NOT NULL,
                    high_price DECIMAL(18,6) NOT NULL,
                    low_price DECIMAL(18,6) NOT NULL,
                    close_price DECIMAL(18,6) NOT NULL,
                    volume DECIMAL(20,2) NOT NULL,
                    amount DECIMAL(20,2),
                    provider VARCHAR(32) DEFAULT 'unknown',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, timestamp, market, timeframe)
                )
            """)

            # Create optimized indexes
            self._create_indexes(conn)

    def _create_indexes(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create optimized indexes for query performance."""
        # Daily data indexes
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_symbol_date 
            ON daily_ohlcv(symbol, trade_date DESC)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_date 
            ON daily_ohlcv(trade_date DESC)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_market 
            ON daily_ohlcv(market, trade_date DESC)
        """)

        # Intraday data indexes
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_intraday_symbol_time 
            ON intraday_ohlcv(symbol, timestamp DESC)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_intraday_timestamp 
            ON intraday_ohlcv(timestamp DESC)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_intraday_market_time 
            ON intraday_ohlcv(market, timeframe, timestamp DESC)
        """)

    async def store_data(self, data: List[DataPoint]) -> None:
        """
        Store data points persistently.

        Args:
            data: List of data points to store
        """
        if not data:
            return

        # Group data by storage type (daily vs intraday)
        daily_data = []
        intraday_data = []

        for point in data:
            if self._is_daily_data(point):
                daily_data.append(point)
            else:
                intraday_data.append(point)

        # Store in appropriate tables
        if daily_data:
            await self._store_daily_data(daily_data)

        if intraday_data:
            await self._store_intraday_data(intraday_data)

    def _is_daily_data(self, point: DataPoint) -> bool:
        """
        Determine if a data point should be stored as daily data.

        Args:
            point: Data point to check

        Returns:
            True if should be stored as daily data
        """
        # Consider it daily data if timestamp is at midnight or close to it
        return (
            point.timestamp.hour == 0
            and point.timestamp.minute == 0
            and point.timestamp.second == 0
        )

    async def _store_daily_data(self, data: List[DataPoint]) -> None:
        """Store daily data points in the daily_ohlcv table."""
        with duckdb.connect(self.db_path) as conn:
            for point in data:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO daily_ohlcv 
                    (symbol, trade_date, market, open_price, high_price, 
                     low_price, close_price, volume, amount, provider, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    [
                        point.symbol,
                        point.timestamp.date(),
                        "cn",  # Default market
                        float(point.open) if point.open else 0,
                        float(point.high) if point.high else 0,
                        float(point.low) if point.low else 0,
                        float(point.close) if point.close else 0,
                        float(point.volume) if point.volume else 0,
                        float(point.amount) if point.amount else None,
                        "repository",  # Default provider
                    ],
                )

    async def _store_intraday_data(self, data: List[DataPoint]) -> None:
        """Store intraday data points in the intraday_ohlcv table."""
        with duckdb.connect(self.db_path) as conn:
            for point in data:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO intraday_ohlcv 
                    (symbol, timestamp, market, timeframe, open_price, high_price, 
                     low_price, close_price, volume, amount, provider, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    [
                        point.symbol,
                        point.timestamp,
                        "cn",  # Default market
                        "1m",  # Default timeframe
                        float(point.open) if point.open else 0,
                        float(point.high) if point.high else 0,
                        float(point.low) if point.low else 0,
                        float(point.close) if point.close else 0,
                        float(point.volume) if point.volume else 0,
                        float(point.amount) if point.amount else None,
                        "repository",  # Default provider
                    ],
                )

    async def retrieve_data(self, query: DataQuery) -> List[DataPoint]:
        """
        Retrieve stored data points based on query.

        Args:
            query: Query specification

        Returns:
            List of matching data points
        """
        # Determine which table(s) to query based on timeframe
        if query.timeframe == TimeFrame.DAY_1:
            return await self._retrieve_daily_data(query)
        elif query.timeframe in [
            TimeFrame.MINUTE_1,
            TimeFrame.MINUTE_5,
            TimeFrame.HOUR_1,
        ]:
            return await self._retrieve_intraday_data(query)
        else:
            # Query both tables and combine results
            daily_data = await self._retrieve_daily_data(query)
            intraday_data = await self._retrieve_intraday_data(query)

            # Combine and sort by timestamp
            all_data = daily_data + intraday_data
            all_data.sort(key=lambda x: x.timestamp)

            # Apply limit if specified
            if query.limit:
                all_data = all_data[: query.limit]

            return all_data

    async def _retrieve_daily_data(self, query: DataQuery) -> List[DataPoint]:
        """Retrieve data from daily_ohlcv table."""
        with duckdb.connect(self.db_path) as conn:
            # Build SQL query
            sql_parts = ["SELECT * FROM daily_ohlcv WHERE 1=1"]
            params = []

            # Add symbol filter
            if query.symbols:
                placeholders = ",".join("?" * len(query.symbols))
                sql_parts.append(f"AND symbol IN ({placeholders})")
                params.extend(query.symbols)

            # Add date range filter
            if query.start:
                sql_parts.append("AND trade_date >= ?")
                params.append(query.start.date())

            if query.end:
                sql_parts.append("AND trade_date <= ?")
                params.append(query.end.date())

            # Add ordering
            sql_parts.append("ORDER BY symbol, trade_date DESC")

            # Add limit
            if query.limit:
                sql_parts.append("LIMIT ?")
                params.append(query.limit)

            sql = " ".join(sql_parts)

            # Execute query
            results = conn.execute(sql, params).fetchall()

            # Convert to DataPoint objects
            data_points = []
            for row in results:
                data_point = DataPoint(
                    symbol=row[0],
                    timestamp=datetime.combine(row[1], datetime.min.time()).replace(
                        tzinfo=timezone.utc
                    ),
                    open=row[3],
                    high=row[4],
                    low=row[5],
                    close=row[6],
                    volume=row[7],
                    amount=row[8],
                )
                data_points.append(data_point)

            return data_points

    async def _retrieve_intraday_data(self, query: DataQuery) -> List[DataPoint]:
        """Retrieve data from intraday_ohlcv table."""
        with duckdb.connect(self.db_path) as conn:
            # Build SQL query
            sql_parts = ["SELECT * FROM intraday_ohlcv WHERE 1=1"]
            params = []

            # Add symbol filter
            if query.symbols:
                placeholders = ",".join("?" * len(query.symbols))
                sql_parts.append(f"AND symbol IN ({placeholders})")
                params.extend(query.symbols)

            # Add date range filter
            if query.start:
                sql_parts.append("AND timestamp >= ?")
                params.append(query.start)

            if query.end:
                sql_parts.append("AND timestamp <= ?")
                params.append(query.end)

            # Add timeframe filter
            if query.timeframe:
                sql_parts.append("AND timeframe = ?")
                params.append(query.timeframe.value)

            # Add ordering
            sql_parts.append("ORDER BY symbol, timestamp DESC")

            # Add limit
            if query.limit:
                sql_parts.append("LIMIT ?")
                params.append(query.limit)

            sql = " ".join(sql_parts)

            # Execute query
            results = conn.execute(sql, params).fetchall()

            # Convert to DataPoint objects
            data_points = []
            for row in results:
                data_point = DataPoint(
                    symbol=row[0],
                    timestamp=row[1],
                    open=row[4],
                    high=row[5],
                    low=row[6],
                    close=row[7],
                    volume=row[8],
                    amount=row[9],
                )
                data_points.append(data_point)

            return data_points

    async def delete_data(self, query: DataQuery) -> int:
        """
        Delete stored data points based on query.

        Args:
            query: Query specification for data to delete

        Returns:
            Number of deleted records
        """
        total_deleted = 0

        # Delete from daily table
        daily_deleted = await self._delete_daily_data(query)
        total_deleted += daily_deleted

        # Delete from intraday table
        intraday_deleted = await self._delete_intraday_data(query)
        total_deleted += intraday_deleted

        return total_deleted

    async def _delete_daily_data(self, query: DataQuery) -> int:
        """Delete data from daily_ohlcv table."""
        with duckdb.connect(self.db_path) as conn:
            # Build DELETE query
            sql_parts = ["DELETE FROM daily_ohlcv WHERE 1=1"]
            params = []

            # Add symbol filter
            if query.symbols:
                placeholders = ",".join("?" * len(query.symbols))
                sql_parts.append(f"AND symbol IN ({placeholders})")
                params.extend(query.symbols)

            # Add date range filter
            if query.start:
                sql_parts.append("AND trade_date >= ?")
                params.append(query.start.date())

            if query.end:
                sql_parts.append("AND trade_date <= ?")
                params.append(query.end.date())

            sql = " ".join(sql_parts)

            # Count records before deletion
            count_sql = sql.replace("DELETE FROM", "SELECT COUNT(*) FROM")
            count_result = conn.execute(count_sql, params).fetchone()
            count_before = count_result[0] if count_result else 0

            # Execute delete
            conn.execute(sql, params)
            return count_before

    async def _delete_intraday_data(self, query: DataQuery) -> int:
        """Delete data from intraday_ohlcv table."""
        with duckdb.connect(self.db_path) as conn:
            # Build DELETE query
            sql_parts = ["DELETE FROM intraday_ohlcv WHERE 1=1"]
            params = []

            # Add symbol filter
            if query.symbols:
                placeholders = ",".join("?" * len(query.symbols))
                sql_parts.append(f"AND symbol IN ({placeholders})")
                params.extend(query.symbols)

            # Add date range filter
            if query.start:
                sql_parts.append("AND timestamp >= ?")
                params.append(query.start)

            if query.end:
                sql_parts.append("AND timestamp <= ?")
                params.append(query.end)

            # Add timeframe filter
            if query.timeframe:
                sql_parts.append("AND timeframe = ?")
                params.append(query.timeframe.value)

            sql = " ".join(sql_parts)

            # Execute delete
            result = conn.execute(sql, params)
            return result.rowcount if hasattr(result, "rowcount") else 0

    async def get_data_statistics(self, query: DataQuery) -> dict:
        """
        Get statistics about stored data.

        Args:
            query: Query specification for statistics

        Returns:
            Dictionary containing data statistics
        """
        with duckdb.connect(self.db_path) as conn:
            stats = {}

            # Daily data statistics
            daily_sql = (
                "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_ohlcv"
            )
            daily_params = []

            if query.symbols:
                placeholders = ",".join("?" * len(query.symbols))
                daily_sql += f" WHERE symbol IN ({placeholders})"
                daily_params.extend(query.symbols)

            daily_result = conn.execute(daily_sql, daily_params).fetchone()
            stats["daily_records"] = daily_result[0]
            stats["daily_date_range"] = (daily_result[1], daily_result[2])

            # Intraday data statistics
            intraday_sql = (
                "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM intraday_ohlcv"
            )
            intraday_params = []

            if query.symbols:
                placeholders = ",".join("?" * len(query.symbols))
                intraday_sql += f" WHERE symbol IN ({placeholders})"
                intraday_params.extend(query.symbols)

            intraday_result = conn.execute(intraday_sql, intraday_params).fetchone()
            stats["intraday_records"] = intraday_result[0]
            stats["intraday_time_range"] = (intraday_result[1], intraday_result[2])

            # Symbol statistics
            symbol_sql = """
                SELECT symbol, COUNT(*) as record_count 
                FROM (
                    SELECT symbol FROM daily_ohlcv
                    UNION ALL
                    SELECT symbol FROM intraday_ohlcv
                ) 
                GROUP BY symbol 
                ORDER BY record_count DESC 
                LIMIT 10
            """

            symbol_results = conn.execute(symbol_sql).fetchall()
            stats["top_symbols"] = [(row[0], row[1]) for row in symbol_results]

            return stats

    async def optimize_storage(self) -> dict:
        """
        Optimize storage by running maintenance operations.

        Returns:
            Dictionary containing optimization results
        """
        with duckdb.connect(self.db_path) as conn:
            results = {}

            # Analyze tables for query optimization
            conn.execute("ANALYZE daily_ohlcv")
            conn.execute("ANALYZE intraday_ohlcv")

            # Get storage statistics
            daily_size = conn.execute("""
                SELECT COUNT(*) * 
                (LENGTH(symbol) + 8 + 1 + 8*6 + 8 + 8 + LENGTH(provider) + 16) 
                FROM daily_ohlcv
            """).fetchone()[0]

            intraday_size = conn.execute("""
                SELECT COUNT(*) * 
                (LENGTH(symbol) + 16 + 1 + LENGTH(timeframe) + 8*6 + 8 + 8 + LENGTH(provider) + 16) 
                FROM intraday_ohlcv
            """).fetchone()[0]

            results["estimated_daily_size_bytes"] = daily_size
            results["estimated_intraday_size_bytes"] = intraday_size
            results["total_estimated_size_bytes"] = daily_size + intraday_size

            # Database file size
            db_file_size = (
                Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
            )
            results["actual_file_size_bytes"] = db_file_size

            return results
