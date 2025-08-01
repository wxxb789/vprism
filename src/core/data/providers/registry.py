"""提供商注册表，管理所有数据提供商实例."""

import asyncio
import contextlib
from datetime import datetime, timezone
from typing import Any

from core.models.query import DataQuery
from .base import DataProvider


class ProviderRegistry:
    """提供商注册表，管理数据提供商的生命周期和健康状态."""

    def __init__(self):
        """初始化提供商注册表."""
        self.providers: dict[str, DataProvider] = {}
        self.provider_health: dict[str, bool] = {}
        self.provider_metadata: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._health_check_interval = 300  # 5分钟
        self._health_check_task: asyncio.Task | None = None

    def register(self, provider: DataProvider) -> None:
        """注册提供商.

        Args:
            provider: 数据提供商实例
        """
        self.providers[provider.name] = provider
        self.provider_health[provider.name] = True  # 默认健康
        self.provider_metadata[provider.name] = {
            "registered_at": datetime.now(timezone.utc),
            "last_health_check": None,
            "health_check_count": 0,
            "total_failures": 0,
        }

    def unregister(self, provider_name: str) -> bool:
        """注销提供商.

        Args:
            provider_name: 提供商名称

        Returns:
            是否成功注销
        """
        if provider_name in self.providers:
            del self.providers[provider_name]
            del self.provider_health[provider_name]
            del self.provider_metadata[provider_name]
            return True
        return False

    def get_provider(self, provider_name: str) -> DataProvider | None:
        """获取指定名称的提供商.

        Args:
            provider_name: 提供商名称

        Returns:
            提供商实例，不存在返回None
        """
        return self.providers.get(provider_name)

    def get_all_providers(self) -> list[DataProvider]:
        """获取所有注册的提供商.

        Returns:
            提供商列表
        """
        return list(self.providers.values())

    def find_capable_providers(self, query: DataQuery) -> list[DataProvider]:
        """查找能处理查询的提供商.

        Args:
            query: 数据查询对象

        Returns:
            能处理该查询的提供商列表
        """
        capable = []
        for provider in self.providers.values():
            if self.provider_health.get(provider.name, False) and provider.can_handle_query(query):
                capable.append(provider)
        return capable

    def mark_healthy(self, provider_name: str) -> None:
        """标记提供商为健康状态.

        Args:
            provider_name: 提供商名称
        """
        if provider_name in self.providers:
            self.provider_health[provider_name] = True
            if provider_name in self.provider_metadata:
                self.provider_metadata[provider_name]["last_health_check"] = datetime.now(timezone.utc)

    def mark_unhealthy(self, provider_name: str) -> None:
        """标记提供商为不健康状态.

        Args:
            provider_name: 提供商名称
        """
        if provider_name in self.providers:
            self.provider_health[provider_name] = False
            if provider_name in self.provider_metadata:
                self.provider_metadata[provider_name]["last_health_check"] = datetime.now(timezone.utc)
                self.provider_metadata[provider_name]["total_failures"] += 1

    def is_healthy(self, provider_name: str) -> bool:
        """检查提供商是否健康.

        Args:
            provider_name: 提供商名称

        Returns:
            是否健康
        """
        return self.provider_health.get(provider_name, False)

    def get_provider_list(self) -> list[dict[str, Any]]:
        """获取提供商列表信息.

        Returns:
            提供商信息列表
        """
        providers = []
        for name, provider in self.providers.items():
            providers.append(
                {
                    "name": name,
                    "healthy": self.provider_health.get(name, False),
                    "capability": {
                        "supported_assets": list(provider.capability.supported_assets),
                        "supported_markets": list(provider.capability.supported_markets),
                        "supported_timeframes": list(provider.capability.supported_timeframes),
                        "max_symbols_per_request": (provider.capability.max_symbols_per_request),
                        "supports_real_time": provider.capability.supports_real_time,
                        "supports_historical": provider.capability.supports_historical,
                        "data_delay_seconds": provider.capability.data_delay_seconds,
                    },
                    "metadata": self.provider_metadata.get(name, {}),
                    "authenticated": provider.is_authenticated,
                }
            )
        return providers

    async def start_health_check(self) -> None:
        """启动定期健康检查.

        创建一个后台任务定期检查所有提供商的健康状态。
        """
        if self._health_check_task is None or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._periodic_health_check())

    async def stop_health_check(self) -> None:
        """停止定期健康检查."""
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_check_task

    async def _periodic_health_check(self) -> None:
        """定期健康检查协程."""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._check_all_providers_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # 记录错误但不中断健康检查
                print(f"Health check error: {e}")

    async def _check_all_providers_health(self) -> None:
        """检查所有提供商的健康状态."""
        async with self._lock:
            tasks = []
            for provider in self.providers.values():
                task = asyncio.create_task(self._check_provider_health(provider))
                tasks.append(task)

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_provider_health(self, provider: DataProvider) -> None:
        """检查单个提供商的健康状态.

        Args:
            provider: 提供商实例
        """
        try:
            is_healthy = await provider.health_check()
            if is_healthy:
                self.mark_healthy(provider.name)
            else:
                self.mark_unhealthy(provider.name)

            if provider.name in self.provider_metadata:
                self.provider_metadata[provider.name]["health_check_count"] += 1

        except Exception:
            self.mark_unhealthy(provider.name)
            if provider.name in self.provider_metadata:
                self.provider_metadata[provider.name]["total_failures"] += 1
                self.provider_metadata[provider.name]["health_check_count"] += 1

    async def refresh_provider_capabilities(self) -> None:
        """刷新所有提供商的能力信息.

        重新发现每个提供商的能力，用于处理提供商更新。
        """
        async with self._lock:
            for provider in self.providers.values():
                # 强制重新发现能力
                provider._capability = None
                _ = provider.capability  # 触发重新发现

    def get_health_summary(self) -> dict[str, Any]:
        """获取健康状态摘要.

        Returns:
            健康状态摘要
        """
        total_providers = len(self.providers)
        healthy_providers = sum(1 for h in self.provider_health.values() if h)

        return {
            "total_providers": total_providers,
            "healthy_providers": healthy_providers,
            "unhealthy_providers": total_providers - healthy_providers,
            "health_percentage": ((healthy_providers / total_providers * 100) if total_providers > 0 else 0),
            "providers": self.get_provider_list(),
        }

    def __len__(self) -> int:
        """返回注册表中的提供商数量."""
        return len(self.providers)

    def __contains__(self, provider_name: str) -> bool:
        """检查是否包含指定名称的提供商."""
        return provider_name in self.providers

    def __repr__(self) -> str:
        """字符串表示."""
        return f"ProviderRegistry({len(self.providers)} providers)"
