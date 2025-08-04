"""数据库管理器."""

import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from .models import CacheRecord, DataRecord, ProviderRecord, QueryRecord
from .schema import setup_database


class DatabaseManager:
    """数据库管理器，提供统一的数据库操作接口."""

    def __init__(self, db_path: str = "data/vprism.db"):
        """初始化数据库管理器."""
        self.db_path = db_path
        self.connection = None
        self._setup()

    def _setup(self) -> None:
        """设置数据库连接和表结构."""
        self.connection = setup_database(self.db_path)

    def close(self) -> None:
        """关闭数据库连接."""
        if self.connection:
            self.connection.close()

    # 数据记录操作
    def insert_data_record(self, record: DataRecord) -> str:
        """插入数据记录."""
        record_id = record.id or str(uuid.uuid4())

        self.connection.execute(
            """
            INSERT INTO data_records (
                id, symbol, asset_type, market, timestamp, open, high, low,
                close, volume, amount, timeframe, provider, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                record_id,
                record.symbol,
                record.asset_type,
                record.market,
                record.timestamp,
                record.open,
                record.high,
                record.low,
                record.close,
                record.volume,
                record.amount,
                record.timeframe,
                record.provider,
                record.metadata,
            ],
        )

        return record_id

    def batch_insert_data_records(self, records: list[DataRecord]) -> list[str]:
        """批量插入数据记录."""
        if not records:
            return []

        record_ids = [str(uuid.uuid4()) for _ in records]

        # 准备批量插入数据
        data = []
        for i, record in enumerate(records):
            data.append(
                [
                    record_ids[i],
                    record.symbol,
                    record.asset_type,
                    record.market,
                    record.timestamp,
                    record.open,
                    record.high,
                    record.low,
                    record.close,
                    record.volume,
                    record.amount,
                    record.timeframe,
                    record.provider,
                    record.metadata,
                ]
            )

        # 执行批量插入
        self.connection.executemany(
            """
            INSERT INTO data_records (
                id, symbol, asset_type, market, timestamp, open, high, low,
                close, volume, amount, timeframe, provider, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )

        return record_ids

    def query_data_records(
        self,
        symbol: str | None = None,
        asset_type: str | None = None,
        market: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        timeframe: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """查询数据记录."""

        where_conditions = []
        params = []

        if symbol:
            where_conditions.append("symbol = ?")
            params.append(symbol)

        if asset_type:
            where_conditions.append("asset_type = ?")
            params.append(asset_type)

        if market:
            where_conditions.append("market = ?")
            params.append(market)

        if start_date:
            where_conditions.append("timestamp >= ?")
            params.append(start_date)

        if end_date:
            where_conditions.append("timestamp <= ?")
            params.append(end_date)

        if timeframe:
            where_conditions.append("timeframe = ?")
            params.append(timeframe)

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        query = f"""
            SELECT * FROM data_records
            WHERE {where_clause}
            ORDER BY timestamp DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        result = self.connection.execute(query, params).fetchall()

        # 转换为字典列表
        columns = [desc[0] for desc in self.connection.description]
        return [dict(zip(columns, row, strict=False)) for row in result]

    # 提供商记录操作
    def upsert_provider_record(self, record: ProviderRecord) -> str:
        """插入或更新提供商记录."""
        record_id = record.id or str(uuid.uuid4())

        self.connection.execute(
            """
            INSERT OR REPLACE INTO provider_records (
                id, name, version, endpoint, status, last_healthy,
                request_count, error_count, avg_response_time_ms, capabilities
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                record_id,
                record.name,
                record.version,
                record.endpoint,
                record.status,
                record.last_healthy,
                record.request_count,
                record.error_count,
                record.avg_response_time_ms,
                record.capabilities,
            ],
        )

        return record_id

    def get_provider_record(self, name: str) -> dict[str, Any] | None:
        """获取提供商记录."""
        result = self.connection.execute("SELECT * FROM provider_records WHERE name = ?", [name]).fetchone()

        if result:
            columns = [desc[0] for desc in self.connection.description]
            return dict(zip(columns, result, strict=False))
        return None

    def update_provider_status(self, name: str, status: str) -> bool:
        """更新提供商状态."""
        result = self.connection.execute(
            "UPDATE provider_records SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
            [status, name],
        )
        return result.rowcount > 0

    # 缓存记录操作
    def upsert_cache_record(self, record: CacheRecord) -> str:
        """插入或更新缓存记录."""
        record_id = record.id or str(uuid.uuid4())

        self.connection.execute(
            """
            INSERT OR REPLACE INTO cache_records (
                id, cache_key, query_hash, data_source, hit_count,
                last_access, expires_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                record_id,
                record.cache_key,
                record.query_hash,
                record.data_source,
                record.hit_count,
                record.last_access,
                record.expires_at,
                record.metadata,
            ],
        )

        return record_id

    def get_cache_record(self, cache_key: str) -> dict[str, Any] | None:
        """获取缓存记录."""
        result = self.connection.execute("SELECT * FROM cache_records WHERE cache_key = ?", [cache_key]).fetchone()

        if result:
            columns = [desc[0] for desc in self.connection.description]
            return dict(zip(columns, result, strict=False))
        return None

    # 查询记录操作
    def insert_query_record(self, record: QueryRecord) -> str:
        """插入查询记录."""
        record_id = record.id or str(uuid.uuid4())

        self.connection.execute(
            """
            INSERT INTO query_records (
                id, query_hash, asset_type, market, symbols, timeframe,
                start_date, end_date, provider, status, request_time_ms,
                response_size, cache_hit, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                record_id,
                record.query_hash,
                record.asset_type,
                record.market,
                record.symbols,
                record.timeframe,
                record.start_date,
                record.end_date,
                record.provider,
                record.status,
                record.request_time_ms,
                record.response_size,
                record.cache_hit,
                record.completed_at,
            ],
        )

        return record_id

    def update_query_record(self, record_id: str, **kwargs) -> None:
        """更新查询记录."""
        set_clauses = []
        params = []

        for key, value in kwargs.items():
            set_clauses.append(f"{key} = ?")
            params.append(value)

        if set_clauses:
            params.append(record_id)
            query = f"UPDATE query_records SET {', '.join(set_clauses)} WHERE id = ?"
            self.connection.execute(query, params)

    # 统计和清理操作
    def get_database_stats(self) -> dict[str, Any]:
        """获取数据库统计信息."""
        stats = {}

        # 数据记录统计
        result = self.connection.execute("SELECT COUNT(*) FROM data_records").fetchone()
        stats["data_records_count"] = result[0] if result else 0

        # 提供商统计
        result = self.connection.execute("SELECT COUNT(*) FROM provider_records").fetchone()
        stats["provider_records_count"] = result[0] if result else 0

        # 缓存统计
        result = self.connection.execute("SELECT COUNT(*) FROM cache_records").fetchone()
        stats["cache_records_count"] = result[0] if result else 0

        # 查询统计
        result = self.connection.execute("SELECT COUNT(*) FROM query_records").fetchone()
        stats["query_records_count"] = result[0] if result else 0

        return stats

    def cleanup_expired_cache(self) -> int:
        """清理过期的缓存记录."""
        try:
            result = self.connection.execute("DELETE FROM cache_records WHERE expires_at <= CURRENT_TIMESTAMP")
            return max(0, result.rowcount)  # Ensure non-negative
        except Exception:
            return 0

    def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        """清理旧数据记录."""
        cutoff_date = datetime.now(timezone.utc).replace(days=-days_to_keep)
        result = self.connection.execute("DELETE FROM data_records WHERE timestamp < ?", [cutoff_date])
        return result.rowcount

    # 数据库维护
    def vacuum(self) -> None:
        """清理数据库空间."""
        self.connection.execute("VACUUM")

    def analyze(self) -> None:
        """分析数据库统计信息."""
        self.connection.execute("ANALYZE")

    @contextmanager
    def transaction(self):
        """事务上下文管理器."""
        try:
            self.connection.execute("BEGIN")
            yield
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise

    def __enter__(self):
        """上下文管理器入口."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口."""
        self.close()
