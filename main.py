#!/usr/bin/env python3
"""
vprism - 下一代个人金融数据平台
Web 服务启动脚本
"""

from loguru import logger
from vprism.core.logging import configure_logging


def run_web_service():
    """运行 Web 服务模式"""
    logger.info("启动 vprism Web 服务...")
    from vprism.web.main import main

    main()


def run_library_mode():
    """运行库模式示例"""
    import asyncio
    import vprism

    async def example():
        logger.info("=== vprism 库模式示例 ===")

        # 获取股票数据
        try:
            data = await vprism.get_async(
                "AAPL", market="us", timeframe="daily", limit=5
            )
            logger.success(f"成功获取 AAPL 数据: {len(data.data)} 条记录")

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
            logger.success(f"成功获取 MSFT 数据: {len(result.data)} 条记录")

        except Exception as e:
            logger.error(f"获取数据失败: {e}")

    asyncio.run(example())


def run_mcp_mode():
    """运行 MCP 服务器模式"""
    import asyncio
    from vprism.mcp.server import create_mcp_server

    async def example():
        logger.info("=== vprism MCP 服务器模式 ===")

        try:
            server = create_mcp_server()
            logger.info("启动 vprism MCP 服务器...")
            logger.info("支持的工具:")
            logger.info("- get_stock_data: 获取股票历史数据")
            logger.info("- get_market_overview: 获取市场概览")
            logger.info("- search_symbols: 搜索股票代码")
            logger.info("- get_realtime_price: 获取实时价格")
            logger.info("- get_batch_quotes: 批量获取报价")
            logger.info("使用 stdio 传输方式启动...")

            await server.start("stdio")

        except KeyboardInterrupt:
            logger.info("关闭 MCP 服务器...")
        except Exception as e:
            logger.error(f"启动失败: {e}")

    asyncio.run(example())


def main():
    """主入口函数"""
    # 配置日志
    configure_logging(level="INFO", format="console")

    parser = argparse.ArgumentParser(description="vprism - 下一代个人金融数据平台")
    parser.add_argument(
        "mode",
        choices=["web", "library", "mcp"],
        help="运行模式: web(服务模式), library(库模式示例), 或 mcp(MCP服务器模式)",
    )

    args = parser.parse_args()

    logger.info(f"启动 vprism - 模式: {args.mode}")

    if args.mode == "web":
        logger.info("启动 vprism Web 服务...")
        run_web_service()
    elif args.mode == "library":
        logger.info("运行 vprism 库模式示例...")
        run_library_mode()
    elif args.mode == "mcp":
        logger.info("启动 vprism MCP 服务器...")
        run_mcp_mode()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
