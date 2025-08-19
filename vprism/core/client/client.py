"""vprism主客户端 - 提供同步和异步接口"""

import asyncio
from collections.abc import Coroutine
from datetime import datetime
from typing import Any

from vprism.core.client.builder import QueryBuilder
from vprism.core.config.settings import ConfigManager, load_config_from_env
from vprism.core.models.market import AssetType, MarketType, TimeFrame
from vprism.core.models.query import DataQuery
from vprism.core.models.response import DataResponse


class VPrismClient:
    """vprism主客户端 - 提供同步和异步接口"""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """初始化客户端

        Args:
            config: 可选配置字典
        """
        # 初始化配置管理器
        self.config_manager = ConfigManager()

        # 加载环境变量配置
        env_config = load_config_from_env()
        if env_config:
            self.config_manager.update_config(**env_config)

        # 加载用户提供的配置
        if config:
            self.config_manager.update_config(**config)

        # 初始化核心组件
        from vprism.core.data.providers.registry import ProviderRegistry
        from vprism.core.services.routing import DataRouter

        self.registry = ProviderRegistry()
        self.router = DataRouter(self.registry)
        self._configured = True

        # 应用配置
        self._apply_config()

    def configure(self, **config: Any) -> None:
        """配置客户端

        Args:
            **config: 配置参数

        支持的配置项:
            cache.enabled: 是否启用缓存 (bool)
            cache.memory_size: 内存缓存大小 (int)
            cache.disk_path: 磁盘缓存路径 (str)
            providers.timeout: 提供商超时时间 (int)
            providers.max_retries: 最大重试次数 (int)
            providers.rate_limit: 是否启用速率限制 (bool)
            logging.level: 日志级别 (str)
            logging.file: 日志文件路径 (str)
        """
        self.config_manager.update_config(**config)
        self._apply_config()

    def _apply_config(self) -> None:
        """应用配置到各个组件"""
        from vprism.core.data.providers.factory import create_default_providers

        # 注册默认提供商（如果注册表为空）
        if len(self.registry) == 0:
            providers = create_default_providers()
            for _name, provider in providers.items():
                self.registry.register(provider)
            self.router.refresh_scores()

    def query(self) -> QueryBuilder:
        """获取查询构建器"""
        return QueryBuilder()

    async def execute(self, query: DataQuery) -> DataResponse:
        """执行查询"""
        if not self._configured:
            self._apply_config()

        provider = await self.router.route_query(query)
        return await provider.get_data(query)

    def get(
        self,
        asset: str,
        market: str | None = None,
        symbols: list[str] | None = None,
        timeframe: str | None = None,
        start: str | None = None,
        end: str | None = None,
        provider: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """简单API - 同步获取数据

        Args:
            asset: 资产类型 (stock, bond, etf, fund, futures, options, forex, crypto)
            market: 市场 (cn, us, hk, eu, jp, global)
            symbols: 股票代码列表
            timeframe: 时间框架 (tick, 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)
            start: 开始日期 (YYYY-MM-DD)
            end: 结束日期 (YYYY-MM-DD)
            provider: 数据提供商 (可选)
            **kwargs: 其他参数

        Returns:
            金融数据

        Examples:
            >>> import vprism
            >>> # 获取中国A股日线数据
            >>> data = vprism.get(
            ...     asset="stock",
            ...     market="cn",
            ...     symbols=["000001", "000002"],
            ...     timeframe="1d",
            ...     start="2024-01-01",
            ...     end="2024-12-31"
            ... )
            >>> print(data)
        """
        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None
        query = DataQuery(
            asset=AssetType(asset) if asset else AssetType.STOCK,
            market=MarketType(market) if market else None,
            symbols=symbols,
            timeframe=TimeFrame(timeframe) if timeframe else TimeFrame.DAY_1,
            start=start_dt,
            end=end_dt,
            provider=provider,
        )

        return self._run_sync(self.execute(query))

    async def get_async(
        self,
        asset: str,
        market: str | None = None,
        symbols: list[str] | None = None,
        timeframe: str | None = None,
        start: str | None = None,
        end: str | None = None,
        provider: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """异步简单API - 异步获取数据

        Args:
            asset: 资产类型
            market: 市场
            symbols: 股票代码列表
            timeframe: 时间框架
            start: 开始日期
            end: 结束日期
            provider: 数据提供商
            **kwargs: 其他参数

        Returns:
            金融数据

        Examples:
            >>> import asyncio
            >>> import vprism
            >>>
            >>> async def main():
            ...     data = await vprism.get_async(
            ...         asset="crypto",
            ...         market="global",
            ...         symbols=["BTC", "ETH"],
            ...         timeframe="1h"
            ...     )
            ...     print(data)
            >>>
            >>> asyncio.run(main())
        """
        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None
        query = DataQuery(
            asset=AssetType(asset) if asset else AssetType.STOCK,
            market=MarketType(market) if market else None,
            symbols=symbols,
            timeframe=TimeFrame(timeframe) if timeframe else TimeFrame.DAY_1,
            start=start_dt,
            end=end_dt,
            provider=provider,
        )

        return await self.execute(query)

    def _run_sync(self, coro: Coroutine[Any, Any, Any]) -> Any:
        """运行异步协程的同步包装器"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已有事件循环中运行
                import nest_asyncio  # type: ignore

                nest_asyncio.apply()
                return loop.run_until_complete(coro)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
