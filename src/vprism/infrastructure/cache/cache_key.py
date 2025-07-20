"""缓存键生成和TTL计算"""

import hashlib

from vprism.core.models import DataQuery, TimeFrame


class CacheKey:
    """缓存键生成器，根据查询参数生成确定性的缓存键"""

    def __init__(self, query: DataQuery):
        """初始化缓存键

        Args:
            query: 数据查询请求
        """
        self.query = query
        self.key = self._generate_key(query)
        self.ttl = self._calculate_ttl(query)

    def _generate_key(self, query: DataQuery) -> str:
        """生成确定性缓存键

        使用SHA256哈希确保相同的查询参数总是生成相同的键

        Args:
            query: 数据查询请求

        Returns:
            16字符的缓存键
        """
        # 构建标准化的键组成部分
        parts = [
            str(query.asset.value) if query.asset else "any",
            str(query.market.value) if query.market else "any",
            "|".join(sorted(query.symbols)) if query.symbols else "all",
            str(query.timeframe.value) if query.timeframe else "any",
            query.start.isoformat() if query.start else "",
            query.end.isoformat() if query.end else "",
            query.provider or "auto",
        ]

        # 创建标准化内容字符串
        content = "|".join(parts)

        # 生成SHA256哈希并取前16位
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _calculate_ttl(self, query: DataQuery) -> int:
        """根据数据类型和时间框架计算TTL（秒）

        基于数据更新频率和重要性设置不同的缓存时间

        Args:
            query: 数据查询请求

        Returns:
            TTL时间（秒）
        """
        if not query.timeframe:
            return 300  # 默认5分钟

        # 基于时间框架的TTL映射
        ttl_map = {
            TimeFrame.TICK: 5,  # 5秒 - 实时数据
            TimeFrame.MINUTE_1: 60,  # 1分钟 - 分钟级数据
            TimeFrame.MINUTE_5: 300,  # 5分钟 - 5分钟数据
            TimeFrame.MINUTE_15: 900,  # 15分钟 - 15分钟数据
            TimeFrame.MINUTE_30: 1800,  # 30分钟 - 30分钟数据
            TimeFrame.HOUR_1: 3600,  # 1小时 - 小时级数据
            TimeFrame.HOUR_4: 14400,  # 4小时 - 4小时数据
            TimeFrame.DAY_1: 3600,  # 1小时 - 日线数据（每天更新）
            TimeFrame.WEEK_1: 86400,  # 1天 - 周线数据（每周更新）
            TimeFrame.MONTH_1: 86400,  # 1天 - 月线数据（每月更新）
        }

        return ttl_map.get(query.timeframe, 300)

    def __str__(self) -> str:
        return f"CacheKey(key={self.key}, ttl={self.ttl}s)"

    def __repr__(self) -> str:
        return str(self)
