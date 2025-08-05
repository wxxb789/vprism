"""多级缓存实现."""

from typing import Any

from vprism.core.data.cache.duckdb import SimpleDuckDBCache
from vprism.core.data.cache.key import CacheKey
from vprism.core.data.cache.memory import ThreadSafeInMemoryCache
from vprism.core.models import DataQuery


class MultiLevelCache:
    """多级缓存系统，包含L1内存缓存和L2 DuckDB缓存."""

    def __init__(self, l1_max_size: int = 1000, l2_db_path: str = ":memory:"):
        """初始化多级缓存."""
        self.l1_cache = ThreadSafeInMemoryCache(max_size=l1_max_size)
        self.l2_cache = SimpleDuckDBCache(db_path=l2_db_path)

    async def get_data(self, query: DataQuery) -> Any | None:
        """从多级缓存获取数据."""
        cache_key = CacheKey(query)

        # 先尝试L1缓存
        result = await self.l1_cache.get(cache_key.key)
        if result is not None:
            return result

        # L1未命中，尝试L2缓存
        result = await self.l2_cache.get(cache_key.key)
        if result is not None:
            # 回填到L1缓存（TTL较短）
            await self.l1_cache.set(
                cache_key.key,
                result,
                ttl=min(cache_key.ttl, 300),  # L1缓存TTL较短
            )
            return result

        return None

    async def set_data(self, query: DataQuery, data: Any) -> None:
        """设置数据到多级缓存."""
        cache_key = CacheKey(query)

        # 设置到L2缓存（TTL为原始值）
        await self.l2_cache.set(cache_key.key, data, ttl=cache_key.ttl)

        # 设置到L1缓存（TTL为原始值的一半，但不超过300秒）
        l1_ttl = min(cache_key.ttl // 2, 300)
        await self.l1_cache.set(cache_key.key, data, ttl=l1_ttl)

    async def invalidate(self, query: DataQuery) -> bool:
        """使特定查询的缓存失效."""
        cache_key = CacheKey(query)

        # 从两个缓存层删除
        l1_deleted = await self.l1_cache.delete(cache_key.key)
        l2_deleted = await self.l2_cache.delete(cache_key.key)

        return l1_deleted or l2_deleted

    async def clear_all(self) -> None:
        """清空所有缓存."""
        await self.l1_cache.clear()
        await self.l2_cache.clear()

    async def cleanup_expired(self) -> int:
        """清理过期数据，只清理L2缓存."""
        return await self.l2_cache.cleanup_expired()

    async def get_cache_stats(self) -> dict[str, Any]:
        """获取缓存统计信息."""
        return {
            "l1_size": self.l1_cache.size(),
            "l2_entries": await self._get_l2_count(),
        }

    async def _get_l2_count(self) -> int:
        """获取L2缓存条目数."""
        try:
            if self.l2_cache._conn:
                result = self.l2_cache._conn.execute("SELECT COUNT(*) FROM cache").fetchone()
                return result[0] if result else 0
        except Exception:
            return 0
        return 0

    async def health_check(self) -> bool:
        """检查缓存健康状况"""
        # 简单检查L2缓存连接
        return self.l2_cache.is_connected()

    async def close(self) -> None:
        """关闭缓存连接"""
        self.l2_cache.close()
