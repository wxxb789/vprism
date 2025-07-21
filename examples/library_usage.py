"""vprism库模式使用示例"""

import asyncio
import vprism
from vprism.core.client import VPrismClient


def basic_usage():
    """基础用法示例"""
    print("=== 基础用法示例 ===")
    
    # 获取中国A股数据
    data = vprism.get(
        asset="stock",
        market="cn",
        symbols=["000001", "000002"],
        timeframe="1d",
        start="2024-01-01",
        end="2024-01-31"
    )
    print("中国A股数据:", type(data))
    
    # 获取美股数据
    data = vprism.get(
        asset="stock",
        market="us",
        symbols=["AAPL", "GOOGL"],
        timeframe="1d"
    )
    print("美股数据:", type(data))
    
    # 获取加密货币数据
    data = vprism.get(
        asset="crypto",
        market="global",
        symbols=["BTC", "ETH"],
        timeframe="1h"
    )
    print("加密货币数据:", type(data))


def advanced_usage():
    """高级用法示例"""
    print("\n=== 高级用法示例 ===")
    
    # 创建客户端实例
    client = VPrismClient()
    
    # 配置客户端
    client.configure(
        cache={
            "enabled": True,
            "memory_size": 2000,
            "disk_path": "/tmp/vprism_cache"
        },
        providers={
            "timeout": 60,
            "max_retries": 5,
            "rate_limit": True
        }
    )
    
    # 使用QueryBuilder构建复杂查询
    query = client.query() \
        .asset("stock") \
        .market("hk") \
        .symbols(["00700", "00005"]) \
        .timeframe("1d") \
        .date_range("2024-01-01", "2024-12-31") \
        .build()
    
    # 执行查询
    data = client.get(
        asset="stock",
        market="hk",
        symbols=["00700", "00005"],
        timeframe="1d",
        start="2024-01-01",
        end="2024-12-31"
    )
    print("港股数据查询完成")


async def async_usage():
    """异步用法示例"""
    print("\n=== 异步用法示例 ===")
    
    # 使用全局异步接口
    data = await vprism.get_async(
        asset="stock",
        market="us",
        symbols=["MSFT", "TSLA", "NVDA"],
        timeframe="1d",
        start="2024-01-01",
        end="2024-01-10"
    )
    print("异步美股数据:", type(data))
    
    # 使用客户端实例的异步接口
    client = VPrismClient()
    data = await client.get_async(
        asset="crypto",
        market="global",
        symbols=["BTC", "ETH", "SOL"],
        timeframe="15m"
    )
    print("异步加密货币数据:", type(data))
    
    # 批量异步查询
    tasks = []
    symbols_list = [["AAPL"], ["GOOGL"], ["MSFT"]]
    
    for symbols in symbols_list:
        task = vprism.get_async(
            asset="stock",
            market="us",
            symbols=symbols,
            timeframe="1d",
            start="2024-01-01",
            end="2024-01-05"
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    print("批量异步查询完成，结果数量:", len(results))


def configuration_usage():
    """配置用法示例"""
    print("\n=== 配置用法示例 ===")
    
    # 使用默认配置
    client1 = VPrismClient()
    
    # 使用自定义配置
    client2 = VPrismClient({
        "cache": {
            "enabled": False,  # 禁用缓存
            "memory_size": 500
        },
        "providers": {
            "timeout": 120,
            "max_retries": 10
        },
        "logging": {
            "level": "DEBUG",
            "file": "/tmp/vprism_debug.log"
        }
    })
    
    # 运行时配置
    client3 = VPrismClient()
    client3.configure(
        providers={"timeout": 45},
        logging={"level": "WARNING"}
    )
    
    print("配置示例完成")


def error_handling_example():
    """错误处理示例"""
    print("\n=== 错误处理示例 ===")
    
    try:
        # 尝试获取不存在的股票代码
        data = vprism.get(
            asset="stock",
            market="cn",
            symbols=["INVALID_CODE"],
            timeframe="1d"
        )
    except vprism.VPrismException as e:
        print(f"捕获vprism异常: {e}")
    except Exception as e:
        print(f"捕获其他异常: {e}")


def batch_usage():
    """批量查询示例"""
    print("\n=== 批量查询示例 ===")
    
    # 批量查询不同市场
    markets = ["cn", "us", "hk"]
    symbols = [["000001"], ["AAPL"], ["00700"]]
    
    for market, symbol_list in zip(markets, symbols):
        data = vprism.get(
            asset="stock",
            market=market,
            symbols=symbol_list,
            timeframe="1d",
            start="2024-01-01",
            end="2024-01-05"
        )
        print(f"{market}市场数据: {len(data) if hasattr(data, '__len__') else 'N/A'}")


async def main():
    """主函数"""
    print("vprism库模式使用示例")
    print("=" * 50)
    
    # 基础用法
    basic_usage()
    
    # 高级用法
    advanced_usage()
    
    # 异步用法
    await async_usage()
    
    # 配置用法
    configuration_usage()
    
    # 错误处理
    error_handling_example()
    
    # 批量查询
    batch_usage()
    
    print("\n" + "=" * 50)
    print("所有示例执行完成")


if __name__ == "__main__":
    asyncio.run(main())