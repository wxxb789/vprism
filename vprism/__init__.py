"""vprism - 金融数据获取库

提供简单易用的API来获取股票、基金、加密货币等金融数据。
支持同步和异步操作，内置缓存和错误处理。
"""

from .core.client.client import VPrismClient
from .core.models.market import AssetType, MarketType, TimeFrame
from .core.models.query import DataQuery

# 创建全局客户端实例
_client = None


def get_client() -> VPrismClient:
    """获取全局vprism客户端实例"""
    global _client
    if _client is None:
        _client = VPrismClient()
    return _client


def get(
    asset: str = None,
    market: str = None,
    symbols: list[str] = None,
    timeframe: str = None,
    start: str = None,
    end: str = None,
    provider: str = None,
    **kwargs,
):
    """同步获取金融数据

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
    client = get_client()
    return client.get(
        asset=asset,
        market=market,
        symbols=symbols,
        timeframe=timeframe,
        start=start,
        end=end,
        provider=provider,
        **kwargs,
    )


async def get_async(
    asset: str = None,
    market: str = None,
    symbols: list[str] = None,
    timeframe: str = None,
    start: str = None,
    end: str = None,
    provider: str = None,
    **kwargs,
):
    """异步获取金融数据

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
    client = get_client()
    return await client.get_async(
        asset=asset,
        market=market,
        symbols=symbols,
        timeframe=timeframe,
        start=start,
        end=end,
        provider=provider,
        **kwargs,
    )


def query():
    """获取查询构建器

    Returns:
        QueryBuilder: 查询构建器实例

    Examples:
        >>> import vprism
        >>> query = vprism.query()
        >>> data = (query
        ...         .asset("stock")
        ...         .market("us")
        ...         .symbols(["AAPL", "GOOGL"])
        ...         .timeframe("1d")
        ...         .date_range("2024-01-01", "2024-12-31")
        ...         .build())
        >>> result = vprism.execute(query)
    """
    client = get_client()
    return client.query()


async def execute(query):
    """执行查询

    Args:
        query: 查询对象

    Returns:
        查询结果

    Examples:
        >>> import asyncio
        >>> import vprism
        >>>
        >>> async def main():
        ...     query = vprism.query().asset("stock").market("cn").symbols(["000001"]).build()
        ...     result = await vprism.execute(query)
        ...     print(result)
        >>>
        >>> asyncio.run(main())
    """
    client = get_client()
    return await client.execute(query)


def configure(**config):
    """配置全局客户端

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

    Examples:
        >>> import vprism
        >>> vprism.configure(
        ...     cache={"enabled": True, "memory_size": 2000},
        ...     providers={"timeout": 60, "max_retries": 3}
        ... )
    """
    client = get_client()
    client.configure(**config)


# 版本信息
__version__ = "0.1.0"
__author__ = "vprism team"
__email__ = "team@vprism.com"

# 导出主要类和函数
__all__ = [
    "VPrismClient",
    "AssetType",
    "MarketType",
    "TimeFrame",
    "DataQuery",
    "get",
    "get_async",
    "query",
    "execute",
    "configure",
    "get_client",
]
