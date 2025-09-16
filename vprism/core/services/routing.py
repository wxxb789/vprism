"""智能数据路由器实现"""

from datetime import datetime
from typing import Any

from vprism.core.data.providers.base import DataProvider, ProviderProtocol
from vprism.core.data.providers.registry import ProviderRegistry
from vprism.core.exceptions.base import NoCapableProviderError
from vprism.core.models.query import DataQuery
from vprism.core.monitoring import PerformanceLogger, StructuredLogger, bind

logger = StructuredLogger().logger


class DataRouter:
    """智能数据路由器，负责将查询路由到最佳的数据提供商

    特性：
    - 基于提供商能力的智能路由
    - 提供商性能评分和选择
    - 健康状态检查
    - 故障转移支持
    """

    def __init__(self, registry: ProviderRegistry):
        """初始化数据路由器

        Args:
            registry: 提供商注册表
        """
        self.registry = registry
        self.provider_scores: dict[str, float] = {}
        self._init_default_scores()

    def _init_default_scores(self) -> None:
        """初始化所有提供商的默认评分"""
        providers = self.registry.get_all_providers()
        for provider in providers:
            self.provider_scores[provider.name] = 1.0

    def refresh_scores(self) -> None:
        """刷新提供商评分（当有新提供商注册时）"""
        self._init_default_scores()

    @PerformanceLogger("route_query")
    async def route_query(self, query: DataQuery) -> ProviderProtocol:
        """将查询路由到最佳的数据提供商

        Args:
            query: 数据查询请求

        Returns:
            最佳的数据提供商

        Raises:
            NoCapableProviderError: 当没有可行的提供商时
        """
        logger = bind(
            component="DataRouter",
            action="route_query",
            symbols=query.symbols,
            market=query.market.value if query.market else None,
            asset_type=query.asset.value,
        )
        logger.info("Starting routing decision")

        # 查找所有可行的提供商
        capable_providers = self.registry.find_capable_providers(query)

        if not capable_providers:
            logger.error("No capable provider found", extra={"query_details": str(query)})
            raise NoCapableProviderError(f"No provider can handle query: asset={query.asset}, market={query.market}, symbols={query.symbols}")

        logger.info(
            "Found capable providers",
            extra={
                "provider_count": len(capable_providers),
                "provider_names": [p.name for p in capable_providers],
            },
        )

        # 如果只有一个可行的提供商，直接返回
        if len(capable_providers) == 1:
            provider = capable_providers[0]
            logger.info("Routing to single provider", extra={"provider_name": provider.name})
            return provider

        # 使用评分系统选择最佳提供商
        best_provider = self._select_best_provider(capable_providers, query)
        logger.info(
            "Selected best provider",
            extra={
                "provider_name": best_provider.name,
                "provider_score": round(self.provider_scores[best_provider.name], 2),
            },
        )

        return best_provider

    def _select_best_provider(self, providers: list[DataProvider], query: DataQuery) -> ProviderProtocol:
        """根据多个因素选择最佳提供商

        Args:
            providers: 可行的提供商列表
            query: 查询请求

        Returns:
            最佳提供商
        """
        # 计算每个提供商的综合评分
        scored_providers = []

        for provider in providers:
            score = self._calculate_provider_score(provider, query)
            scored_providers.append((score, provider))

        # 按评分排序，选择评分最高的提供商
        scored_providers.sort(key=lambda x: x[0], reverse=True)
        best_score, best_provider = scored_providers[0]

        logger.debug(f"Provider selection scores: {[f'{p.name}:{s:.2f}' for s, p in scored_providers]}")

        return best_provider

    def _calculate_provider_score(self, provider: DataProvider, query: DataQuery) -> float:
        """计算提供商的综合评分

        考虑因素：
        1. 历史性能评分（权重：40%）
        2. 数据延迟（权重：30%）
        3. 符号数量限制匹配度（权重：20%）
        4. 提供商稳定性（权重：10%）

        Args:
            provider: 数据提供商
            query: 查询请求

        Returns:
            综合评分（0-2.0）
        """
        base_score = self.provider_scores.get(provider.name, 1.0)
        capability = provider.capability

        # 数据延迟评分（延迟越低分数越高）
        delay_penalty = min(capability.data_delay_seconds / 100.0, 1.0)
        delay_score = 1.0 - delay_penalty

        # 符号数量匹配度评分
        symbol_count = len(query.symbols) if query.symbols else 1
        symbol_ratio = min(symbol_count / capability.max_symbols_per_request, 1.0)
        symbol_score = 1.0 - (symbol_ratio * 0.5)  # 越接近限制，分数越低

        # 综合计算
        final_score = (
            base_score * 0.4  # 历史性能
            + delay_score * 0.3  # 数据延迟
            + symbol_score * 0.2  # 符号匹配
            + 0.1  # 稳定性基础分
        )

        return min(final_score, 2.0)  # 限制最大值为2.0

    def update_provider_score(self, provider_name: str, success: bool, latency_ms: int) -> None:
        """更新提供商的性能评分

        Args:
            provider_name: 提供商名称
            success: 请求是否成功
            latency_ms: 请求延迟（毫秒）
        """
        if provider_name not in self.provider_scores:
            self.provider_scores[provider_name] = 1.0

        current_score = self.provider_scores[provider_name]

        if success:
            # 成功时增加评分，延迟越低奖励越大
            latency_bonus = max(0.1 - (latency_ms / 1000), 0)  # 最高奖励0.1
            score_delta = 0.05 + latency_bonus
        else:
            # 失败时减少评分
            score_delta = -0.2

        # 更新评分并限制范围
        new_score = max(0.1, min(2.0, current_score + score_delta))
        self.provider_scores[provider_name] = new_score

        logger.debug(f"Updated provider score: {provider_name} ({current_score:.2f} -> {new_score:.2f}) success={success}, latency={latency_ms}ms")

    def get_provider_ranking(self) -> dict[str, float]:
        """获取提供商排名"""
        return dict(sorted(self.provider_scores.items(), key=lambda x: x[1], reverse=True))

    async def get_provider_health_status(self) -> dict[str, dict[str, Any]]:
        """获取提供商健康状态"""
        health_status = {}

        for provider_name in self.registry.providers:
            is_healthy = self.registry.provider_health.get(provider_name, True)
            score = self.provider_scores.get(provider_name, 1.0)

            health_status[provider_name] = {
                "healthy": is_healthy,
                "score": score,
                "last_updated": datetime.now().isoformat(),
            }

        return health_status

    async def health_check(self) -> dict[str, Any]:
        """健康检查摘要"""
        return {
            "providers": await self.get_provider_health_status(),
            "ranking": self.get_provider_ranking(),
        }
