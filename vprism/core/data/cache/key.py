"""缓存键生成和管理."""

import hashlib

from vprism.core.models.market import TimeFrame
from vprism.core.models.query import DataQuery


class CacheKey:
    """缓存键生成器."""

    def __init__(self, query: DataQuery):
        """根据查询生成缓存键."""
        self.query = query
        self.key = self._generate_key()
        self.ttl = self._calculate_ttl()

    def _generate_key(self) -> str:
        """生成唯一的缓存键."""
        # 创建包含所有查询参数的字符串
        key_parts = [
            str(self.query.asset.value),
            str(self.query.market.value) if self.query.market else "none",
            ",".join(sorted(self.query.symbols)) if self.query.symbols else "",
            str(self.query.timeframe.value) if self.query.timeframe else "default",
            str(self.query.start.isoformat()) if self.query.start else "",
            str(self.query.end.isoformat()) if self.query.end else "",
            str(self.query.provider) if self.query.provider else "",
        ]

        key_string = "|".join(key_parts)

        # 使用SHA256哈希生成16字符的键
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def _calculate_ttl(self) -> int:
        """根据时间框架计算TTL."""
        ttl_mapping = {
            TimeFrame.TICK: 5,  # 5秒
            TimeFrame.MINUTE_1: 60,  # 1分钟
            TimeFrame.MINUTE_5: 300,  # 5分钟
            TimeFrame.MINUTE_15: 900,  # 15分钟
            TimeFrame.MINUTE_30: 1800,  # 30分钟
            TimeFrame.HOUR_1: 3600,  # 1小时
            TimeFrame.DAY_1: 3600,  # 1小时
            TimeFrame.WEEK_1: 86400,  # 1天
            TimeFrame.MONTH_1: 86400,  # 1天
        }

        if self.query.timeframe:
            return ttl_mapping.get(self.query.timeframe, 300)

        return 300  # 默认5分钟

    def __str__(self) -> str:
        return self.key

    def __repr__(self) -> str:
        return f"CacheKey(key={self.key}, ttl={self.ttl})"
