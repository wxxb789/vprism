"""数据路由服务 - 负责将查询路由到合适的提供商"""

from core.data.providers.base import DataProvider
from core.data.providers.registry import ProviderRegistry
from core.models.query import DataQuery


class DataRouter:
    """数据路由器 - 将查询路由到合适的提供商"""

    def __init__(self, registry: ProviderRegistry):
        """初始化数据路由器

        Args:
            registry: 提供商注册表
        """
        self.registry = registry

    async def route_query(self, query: DataQuery) -> DataProvider:
        """将查询路由到最合适的提供商

        Args:
            query: 数据查询对象

        Returns:
            最合适的提供商实例
        """
        # 查找能处理该查询的提供商
        capable_providers = self.registry.find_capable_providers(query)

        if not capable_providers:
            raise ValueError(f"No provider can handle query: {query}")

        # 简单实现：返回第一个健康的提供商
        return capable_providers[0]

    def refresh_scores(self) -> None:
        """刷新提供商评分（用于测试）"""
        pass
