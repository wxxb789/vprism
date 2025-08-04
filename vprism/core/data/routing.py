"""智能数据路由器，实现基于性能和能力的提供商选择."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.exceptions import NoCapableProviderError
from core.models import DataQuery
from core.data.providers.base import DataProvider
from core.data.providers.registry import ProviderRegistry


@dataclass
class ProviderScore:
    """提供商性能评分."""

    provider_name: str
    score: float
    latency_ms: int
    success_rate: float
    last_updated: datetime


class DataRouter:
    """智能数据路由器，根据提供商能力和性能进行路由选择."""

    def __init__(self, registry: ProviderRegistry):
        """初始化数据路由器.

        Args:
            registry: 提供商注册表
        """
        self.registry = registry
        self.provider_scores: dict[str, float] = {}
        self.provider_stats: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def route_query(self, query: DataQuery) -> DataProvider:
        """根据查询条件选择最佳提供商.

        Args:
            query: 数据查询对象

        Returns:
            最适合的提供商实例

        Raises:
            NoCapableProviderError: 没有可用的提供商
        """
        capable_providers = self.registry.find_capable_providers(query)

        if not capable_providers:
            raise NoCapableProviderError(f"No provider can handle query: {query}")

        # 如果只有一个可用提供商，直接返回
        if len(capable_providers) == 1:
            return capable_providers[0]

        # 使用评分系统选择最佳提供商
        return await self._select_best_provider(capable_providers, query)

    async def _select_best_provider(self, providers: list[DataProvider], query: DataQuery) -> DataProvider:
        """根据评分系统选择最佳提供商.

        Args:
            providers: 可用提供商列表
            query: 数据查询对象

        Returns:
            评分最高的提供商
        """
        async with self._lock:
            # 计算每个提供商的评分
            provider_ratings = []

            for provider in providers:
                score = self._calculate_provider_score(provider, query)
                provider_ratings.append((provider, score))

            # 按评分排序，选择最高分的提供商
            provider_ratings.sort(key=lambda x: x[1], reverse=True)
            best_provider = provider_ratings[0][0]

            return best_provider

    def _calculate_provider_score(self, provider: DataProvider, query: DataQuery) -> float:
        """计算提供商对特定查询的评分.

        Args:
            provider: 提供商实例
            query: 数据查询对象

        Returns:
            综合评分 (0-2.0)
        """
        base_score = 1.0
        capability = provider.capability

        # 基础能力评分
        if query.asset in capability.supported_assets:
            base_score += 0.2
        if query.market in capability.supported_markets:
            base_score += 0.2
        if query.timeframe in capability.supported_timeframes:
            base_score += 0.2

        # 数据延迟评分 (越低越好)
        latency_penalty = capability.data_delay_seconds / 100.0
        base_score -= min(latency_penalty, 0.5)

        # 实时数据支持
        if capability.supports_real_time:
            base_score += 0.1

        # 历史数据支持
        if capability.supports_historical:
            base_score += 0.1

        # 批量查询支持
        if query.symbols and len(query.symbols) <= capability.max_symbols_per_request:
            base_score += 0.1

        # 历史评分权重
        historical_score = self.provider_scores.get(provider.name, 1.0)
        final_score = (base_score + historical_score) / 2.0

        return max(0.1, min(2.0, final_score))

    def update_provider_score(self, provider_name: str, success: bool, latency_ms: int) -> None:
        """更新提供商性能评分.

        Args:
            provider_name: 提供商名称
            success: 请求是否成功
            latency_ms: 请求延迟(毫秒)
        """
        current_score = self.provider_scores.get(provider_name, 1.0)

        if success:
            # 成功奖励，延迟越低奖励越高
            score_delta = 0.1 - (latency_ms / 10000.0)
            score_delta = max(0.05, score_delta)  # 确保最小奖励
        else:
            # 失败惩罚
            score_delta = -0.2

        new_score = current_score + score_delta
        self.provider_scores[provider_name] = max(0.1, min(2.0, new_score))

        # 更新统计信息
        if provider_name not in self.provider_stats:
            self.provider_stats[provider_name] = {
                "total_requests": 0,
                "successful_requests": 0,
                "total_latency": 0,
                "last_request_time": None,
            }

        stats = self.provider_stats[provider_name]
        stats["total_requests"] += 1
        if success:
            stats["successful_requests"] += 1
            stats["total_latency"] += latency_ms
        stats["last_request_time"] = datetime.now(timezone.utc)

    def get_provider_stats(self, provider_name: str) -> dict[str, Any] | None:
        """获取提供商统计信息.

        Args:
            provider_name: 提供商名称

        Returns:
            提供商统计信息，如果不存在返回None
        """
        return self.provider_stats.get(provider_name)

    def get_provider_score(self, provider_name: str) -> float:
        """获取提供商当前评分.

        Args:
            provider_name: 提供商名称

        Returns:
            提供商评分 (0.1-2.0)
        """
        return self.provider_scores.get(provider_name, 1.0)

    def get_all_provider_scores(self) -> dict[str, float]:
        """获取所有提供商的评分.

        Returns:
            提供商名称到评分的映射
        """
        return self.provider_scores.copy()

    def reset_provider_score(self, provider_name: str) -> None:
        """重置提供商评分为默认值.

        Args:
            provider_name: 提供商名称
        """
        self.provider_scores[provider_name] = 1.0
        if provider_name in self.provider_stats:
            self.provider_stats[provider_name] = {
                "total_requests": 0,
                "successful_requests": 0,
                "total_latency": 0,
                "last_request_time": None,
            }

    async def get_routing_decision_log(self, query: DataQuery) -> dict[str, Any]:
        """获取路由决策日志，用于调试和分析.

        Args:
            query: 数据查询对象

        Returns:
            路由决策日志
        """
        capable_providers = self.registry.find_capable_providers(query)

        decisions = []
        for provider in capable_providers:
            score = self._calculate_provider_score(provider, query)
            stats = self.get_provider_stats(provider.name)

            decisions.append(
                {
                    "provider_name": provider.name,
                    "score": score,
                    "capability": {
                        "supported_assets": list(provider.capability.supported_assets),
                        "supported_markets": list(provider.capability.supported_markets),
                        "data_delay_seconds": provider.capability.data_delay_seconds,
                        "max_symbols_per_request": (provider.capability.max_symbols_per_request),
                    },
                    "stats": stats,
                    "selected": False,
                }
            )

        # 标记选中的提供商
        if decisions:
            best_score = max(d["score"] for d in decisions)
            for d in decisions:
                if d["score"] == best_score:
                    d["selected"] = True

        return {
            "query": {
                "asset": query.asset.value if query.asset else None,
                "market": query.market.value if query.market else None,
                "symbols": query.symbols,
                "timeframe": query.timeframe.value if query.timeframe else None,
            },
            "total_providers": len(capable_providers),
            "decisions": decisions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
