"""数据路由服务 - 负责将查询路由到合适的提供商"""

from vprism.core.data.providers.base import DataProvider
from vprism.core.data.providers.registry import ProviderRegistry
from vprism.core.exceptions.base import ProviderError
from vprism.core.models.query import DataQuery


class DataRouter:
    """数据路由器 - 将查询路由到合适的提供商"""

    def __init__(self, registry: ProviderRegistry):
        """初始化数据路由器

        Args:
            registry: 提供商注册表
        """
        self.registry = registry

    def route_query(self, query: DataQuery) -> DataProvider:
        """将查询路由到最合适的提供商

        Args:
            query: 数据查询对象

        Returns:
            能够处理查询的数据提供商
        """
        # 查找能处理该查询的提供商
        capable_providers = self.registry.find_capable_providers(query)

        if not capable_providers:
            raise ProviderError(f"No provider can handle query: {query}", "DataRouter")

        # 简单实现：使用第一个健康的提供商
        provider = capable_providers[0]
        return provider

    def refresh_scores(self) -> None:
        """刷新提供商评分（用于测试）"""
        pass

    def health_check(self) -> bool:
        """检查路由器和所有提供商的健康状况"""
        summary = self.registry.get_health_summary()
        return summary["healthy_providers"] == summary["total_providers"]
