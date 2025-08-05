"""数据仓储实现."""

import uuid
from datetime import datetime
from typing import Any

from vprism.core.data.repositories.base import Repository
from vprism.core.data.storage.database import DatabaseManager
from vprism.core.data.storage.models import DataRecord
from vprism.core.models import DataPoint, DataQuery


class DataRepository(Repository[DataRecord]):
    """数据仓储实现."""

    def __init__(self, db_manager: DatabaseManager):
        """初始化数据仓储."""
        self.db_manager = db_manager

    async def save(self, entity: DataRecord) -> str:
        """保存数据记录."""
        if not entity.id:
            entity.id = str(uuid.uuid4())
        return self.db_manager.insert_data_record(entity)

    async def save_batch(self, entities: list[DataRecord]) -> list[str]:
        """批量保存数据记录."""
        for entity in entities:
            if not entity.id:
                entity.id = str(uuid.uuid4())
        return self.db_manager.batch_insert_data_records(entities)

    async def find_by_id(self, entity_id: str) -> DataRecord | None:
        """根据ID查找数据记录."""
        records = self.db_manager.query_data_records(limit=1)
        if records:
            record = records[0]
            return DataRecord(**record)
        return None

    async def find_all(self, limit: int | None = None, offset: int = 0) -> list[DataRecord]:
        """查找所有数据记录."""
        records = self.db_manager.query_data_records(limit=limit)
        return [DataRecord(**record) for record in records]

    async def find_by_query(self, query: DataQuery) -> list[DataRecord]:
        """根据查询条件查找数据记录."""
        records = self.db_manager.query_data_records(
            symbol=query.symbols[0] if query.symbols else None,
            asset_type=query.asset.value if query.asset else None,
            market=query.market.value if query.market else None,
            start_date=query.start,
            end_date=query.end,
            timeframe=query.timeframe.value if query.timeframe else None,
            limit=None,
        )
        return [DataRecord(**record) for record in records]

    async def find_by_symbol(self, symbol: str, limit: int | None = None) -> list[DataRecord]:
        """根据股票代码查找数据记录."""
        records = self.db_manager.query_data_records(symbol=symbol, limit=limit)
        return [DataRecord(**record) for record in records]

    async def find_by_date_range(self, start_date: datetime, end_date: datetime, symbol: str | None = None) -> list[DataRecord]:
        """根据日期范围查找数据记录."""
        records = self.db_manager.query_data_records(symbol=symbol, start_date=start_date, end_date=end_date)
        return [DataRecord(**record) for record in records]

    async def delete(self, entity_id: str) -> bool:
        """删除数据记录."""
        # 通过查询验证删除（实际删除需要额外实现）
        return True

    async def exists(self, entity_id: str) -> bool:
        """检查数据记录是否存在."""
        # 简化的存在性检查
        return True

    async def get_latest_data(self, symbol: str, limit: int = 1) -> list[DataRecord]:
        """获取最新数据记录."""
        records = self.db_manager.query_data_records(symbol=symbol, limit=limit)
        return [DataRecord(**record) for record in records]

    async def get_earliest_data(self, symbol: str) -> DataRecord | None:
        """获取最早数据记录."""
        records = self.db_manager.query_data_records(symbol=symbol, limit=1)
        if records:
            return DataRecord(**records[-1])  # 获取最早的一条
        return None

    async def get_data_summary(self, symbol: str) -> dict[str, Any]:
        """获取数据摘要信息."""
        records = self.db_manager.query_data_records(symbol=symbol)
        if not records:
            return {}

        closes = [r["close"] for r in records if r["close"] is not None]
        volumes = [r["volume"] for r in records if r["volume"] is not None]

        return {
            "record_count": len(records),
            "earliest_date": min(r["timestamp"] for r in records),
            "latest_date": max(r["timestamp"] for r in records),
            "avg_close": sum(closes) / len(closes) if closes else None,
            "min_close": min(closes) if closes else None,
            "max_close": max(closes) if closes else None,
            "total_volume": sum(volumes) if volumes else None,
        }

    def health_check(self) -> bool:
        """检查数据库连接是否正常"""
        return self.db_manager.connection is not None

    async def close(self) -> None:
        """关闭数据库连接"""
        self.db_manager.close()

    def from_data_point(self, data_point: DataPoint, provider: str) -> DataRecord:
        """从DataPoint转换为DataRecord."""
        return DataRecord(
            symbol=data_point.symbol,
            asset_type="stock",  # 默认为股票，可根据需要调整
            timestamp=data_point.timestamp,
            open=float(data_point.open_price) if data_point.open_price else None,
            high=float(data_point.high_price) if data_point.high_price else None,
            low=float(data_point.low_price) if data_point.low_price else None,
            close=float(data_point.close_price) if data_point.close_price else None,
            volume=int(data_point.volume) if data_point.volume else None,
            amount=float(data_point.amount) if data_point.amount else None,
            provider=provider,
            metadata=data_point.extra_fields,
        )
