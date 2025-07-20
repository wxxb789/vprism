"""vprism - 下一代个人金融数据平台

vprism 是一个现代化的金融数据基础设施平台，旨在解决传统金融数据库的架构问题。
通过采用领域驱动设计（DDD）、清洁架构原则和现代 Python 技术栈，
vprism 提供统一的、可组合的 API 接口，支持多模态部署。

基本用法:
    
    库模式 (Library Mode):
    ```python
    import vprism
    
    # 简单用法
    data = vprism.get(asset="stock", market="cn", symbols=["000001"])
    
    # 复杂查询
    query = vprism.query() \
        .asset("stock") \
        .market("cn") \
        .symbols(["000001", "000002"]) \
        .timeframe("1d") \
        .date_range("2024-01-01", "2024-12-31") \
        .build()
    data = vprism.execute(query)
    ```

    服务模式 (Service Mode):
    ```python
    from vprism.service import create_app
    app = create_app()
    # 然后运行: uvicorn "vprism.service:app" --host 0.0.0.0 --port 8000
    ```

    MCP 模式 (MCP Mode):
    ```python
    from vprism.mcp import create_mcp_server
    server = create_mcp_server()
    server.run()
    ```
"""

from vprism.core.client import VPrismClient
from vprism.core.models import AssetType, MarketType, TimeFrame
from vprism.core.exceptions import VPrismException

__version__ = "0.1.0"
__author__ = "vprism Team"
__email__ = "team@vprism.dev"

# 客户端实例
_client = None

def get_client() -> VPrismClient:
    """获取全局客户端实例"""
    global _client
    if _client is None:
        _client = VPrismClient()
    return _client

def get(asset: str = None, market: str = None, symbols: list = None, 
        timeframe: str = None, start: str = None, end: str = None,
        provider: str = None, **kwargs):
    """简单API - 获取金融数据
    
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
        **kwargs
    )

def query():
    """构建器模式API - 创建复杂查询"""
    client = get_client()
    return client.query()

async def execute(query):
    """执行查询"""
    client = get_client()
    return await client.execute(query)

def configure(**config):
    """配置客户端"""
    client = get_client()
    client.configure(**config)

# 导出常用类型
__all__ = [
    "get",
    "query", 
    "execute",
    "configure",
    "get_client",
    "VPrismClient",
    "AssetType",
    "MarketType", 
    "TimeFrame",
    "VPrismException"
]