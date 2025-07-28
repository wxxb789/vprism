"""缓存仓储实现."""

import uuid
from datetime import datetime, timezone
from typing import Any

from core.data.storage.models import CacheRecord
from core.data.storage.database import DatabaseManager

from .base import Repository


class CacheRepository(Repository[CacheRecord]):
    """缓存仓储实现."""

    def __init__(self, db_manager: DatabaseManager):
        """初始化缓存仓储."""
        self.db_manager = db_manager

    async def save(self, entity: CacheRecord) -> str:
        """保存缓存记录."""
        if not entity.id:
            entity.id = str(uuid.uuid4())
        return self.db_manager.upsert_cache_record(entity)

    async def find_by_id(self, entity_id: str) -> CacheRecord | None:
        """根据ID查找缓存记录."""
        # 注意：这里entity_id是cache_key
        record = self.db_manager.get_cache_record(entity_id)
        if record:
            return CacheRecord(**record)
        return None

    async def find_by_cache_key(self, cache_key: str) -> CacheRecord | None:
        """根据缓存键查找缓存记录."""
        return await self.find_by_id(cache_key)

    async def find_all(
        self, limit: int | None = None, offset: int = 0
    ) -> list[CacheRecord]:
        """查找所有缓存记录."""
        # 简化的实现，实际需要通过扩展DatabaseManager
        return []

    async def find_expired(self) -> list[CacheRecord]:
        """查找过期的缓存记录."""
        # 简化的实现
        return []

    async def increment_hit_count(self, cache_key: str) -> bool:
        """增加缓存命中计数."""
        record = await self.find_by_cache_key(cache_key)
        if record:
            record.hit_count += 1
            record.last_access = datetime.now(timezone.utc)
            await self.save(record)
            return True
        return False

    async def update_last_access(self, cache_key: str) -> bool:
        """更新最后访问时间."""
        record = await self.find_by_cache_key(cache_key)
        if record:
            record.last_access = datetime.now(timezone.utc)
            await self.save(record)
            return True
        return False

    async def cleanup_expired(self) -> int:
        """清理过期的缓存记录."""
        return self.db_manager.cleanup_expired_cache()

    async def get_cache_stats(self) -> dict[str, Any]:
        """获取缓存统计信息."""
        # 简化的实现
        return {
            "total_entries": 0,
            "active_entries": 0,
            "expired_entries": 0,
            "total_hits": 0,
        }

    async def delete(self, entity_id: str) -> bool:
        """删除缓存记录."""
        return True

    async def exists(self, entity_id: str) -> bool:
        """检查缓存记录是否存在."""
        record = await self.find_by_cache_key(entity_id)
        return record is not None

    def create_cache_record(
        self,
        cache_key: str,
        query_hash: str,
        data_source: str,
        expires_at: datetime,
        **kwargs,
    ) -> CacheRecord:
        """创建新的缓存记录."""
        return CacheRecord(
            cache_key=cache_key,
            query_hash=query_hash,
            data_source=data_source,
            expires_at=expires_at,
            **kwargs,
        )

    async def find_by_query_hash(self, query_hash: str) -> list[CacheRecord]:
        """根据查询哈希查找缓存记录."""
        # 简化的实现
        return []

    async def get_popular_caches(self, limit: int = 10) -> list[CacheRecord]:
        """获取热门缓存记录."""
        # 简化的实现
        return []
