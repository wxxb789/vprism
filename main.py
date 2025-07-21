#!/usr/bin/env python3
"""
vprism - 下一代个人金融数据平台
Web 服务启动脚本
"""

import argparse
import sys
from pathlib import Path

# 添加 src 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def run_web_service():
    """运行 Web 服务模式"""
    from vprism.web.main import main
    main()

def run_library_mode():
    """运行库模式示例"""
    import asyncio
    import vprism
    
    async def example():
        print("=== vprism 库模式示例 ===")
        
        # 获取股票数据
        try:
            data = await vprism.get_async("AAPL", market="us", timeframe="daily", limit=5)
            print(f"成功获取 AAPL 数据: {len(data.data)} 条记录")
            
            # 使用查询构建器
            query = (
                vprism.query()
                .asset("MSFT")
                .market("us")
                .timeframe("daily")
                .limit(3)
                .build()
            )
            
            result = await vprism.execute_async(query)
            print(f"成功获取 MSFT 数据: {len(result.data)} 条记录")
            
        except Exception as e:
            print(f"获取数据失败: {e}")
    
    asyncio.run(example())

def run_mcp_mode():
    """运行 MCP 服务器模式"""
    import asyncio
    from vprism.mcp.server import create_mcp_server
    
    async def example():
        print("=== vprism MCP 服务器模式 ===")
        
        try:
            server = create_mcp_server()
            print("启动 vprism MCP 服务器...")
            print("支持的工具:")
            print("- get_stock_data: 获取股票历史数据")
            print("- get_market_overview: 获取市场概览")
            print("- search_symbols: 搜索股票代码")
            print("- get_realtime_price: 获取实时价格")
            print("- get_batch_quotes: 批量获取报价")
            print("\n使用 stdio 传输方式启动...")
            
            await server.start("stdio")
            
        except KeyboardInterrupt:
            print("\n关闭 MCP 服务器...")
        except Exception as e:
            print(f"启动失败: {e}")
    
    asyncio.run(example())

def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(description="vprism - 下一代个人金融数据平台")
    parser.add_argument(
        "mode",
        choices=["web", "library", "mcp"],
        help="运行模式: web(服务模式), library(库模式示例), 或 mcp(MCP服务器模式)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "web":
        print("启动 vprism Web 服务...")
        run_web_service()
    elif args.mode == "library":
        print("运行 vprism 库模式示例...")
        run_library_mode()
    elif args.mode == "mcp":
        print("启动 vprism MCP 服务器...")
        run_mcp_mode()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()