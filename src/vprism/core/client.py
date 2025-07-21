"""vprism客户端实现 - 提供简单和复杂的API接口"""

import asyncio
from typing import Any, Dict, Optional
from pathlib import Path
import os

from vprism.core.models import AssetType, DataQuery, MarketType, TimeFrame
from vprism.core.services.data_router import DataRouter
from vprism.core.config import ConfigManager, load_config_from_env
from vprism.infrastructure.providers.registry import ProviderRegistry


class QueryBuilder:
    """构建器模式API - 支持复杂查询构建"""

    def __init__(self):
        self._asset: AssetType | None = None
        self._market: MarketType | None = None
        self._symbols: list[str] | None = None
        self._timeframe: TimeFrame | None = None
        self._start: str | None = None
        self._end: str | None = None
        self._provider: str | None = None

    def asset(self, asset: str) -> "QueryBuilder":
        """设置资产类型"""
        self._asset = AssetType(asset)
        return self

    def market(self, market: str) -> "QueryBuilder":
        """设置市场"""
        self._market = MarketType(market)
        return self

    def symbols(self, symbols: list[str]) -> "QueryBuilder":
        """设置股票代码列表"""
        self._symbols = symbols
        return self

    def timeframe(self, timeframe: str) -> "QueryBuilder":
        """设置时间框架"""
        self._timeframe = TimeFrame(timeframe)
        return self

    def date_range(self, start: str, end: str) -> "QueryBuilder":
        """设置日期范围"""
        self._start = start
        self._end = end
        return self

    def provider(self, provider: str) -> "QueryBuilder":
        """设置数据提供商"""
        self._provider = provider
        return self

    def build(self) -> DataQuery:
        """构建最终的查询对象"""
        from datetime import datetime

        start_dt = None
        end_dt = None
        if self._start:
            start_dt = datetime.fromisoformat(self._start)
        if self._end:
            end_dt = datetime.fromisoformat(self._end)

        return DataQuery(
            asset=self._asset,
            market=self._market,
            symbols=self._symbols,
            timeframe=self._timeframe,
            start=start_dt,
            end=end_dt,
            provider=self._provider,
        )


class VPrismClient:
    """vprism主客户端 - 提供同步和异步接口"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
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
        config = self.config_manager.get_config()
        
        # 配置缓存
        cache_config = config.cache
        # TODO: 应用到缓存系统
        
        # 配置提供商
        provider_config = config.providers
        # TODO: 应用到提供商系统
        
        # 配置日志
        logging_config = config.logging
        # TODO: 配置日志系统

    def query(self) -> QueryBuilder:
        """获取查询构建器"""
        return QueryBuilder()

    async def execute(self, query: DataQuery) -> Any:
        """执行查询"""
        if not self._configured:
            # 使用默认配置
            pass

        provider = await self.router.route_query(query)
        return await provider.get_data(query)

    def get(
        self,
        asset: str = None,
        market: str = None,
        symbols: list[str] = None,
        timeframe: str = None,
        start: str = None,
        end: str = None,
        provider: str = None,
        **kwargs,
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
        query = DataQuery(
            asset=AssetType(asset) if asset else None,
            market=MarketType(market) if market else None,
            symbols=symbols,
            timeframe=TimeFrame(timeframe) if timeframe else None,
            start=start,
            end=end,
            provider=provider,
        )

        return self._run_sync(self.execute(query))

    async def get_async(
        self,
        asset: str = None,
        market: str = None,
        symbols: list[str] = None,
        timeframe: str = None,
        start: str = None,
        end: str = None,
        provider: str = None,
        **kwargs,
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
        query = DataQuery(
            asset=AssetType(asset) if asset else None,
            market=MarketType(market) if market else None,
            symbols=symbols,
            timeframe=TimeFrame(timeframe) if timeframe else None,
            start=start,
            end=end,
            provider=provider,
        )

        return await self.execute(query)

    def _run_sync(self, coro) -> Any:
        """运行异步协程的同步包装器"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已有事件循环中运行
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(coro)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
