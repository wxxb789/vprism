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

def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(description="vprism - 下一代个人金融数据平台")
    parser.add_argument(
        "mode",
        choices=["web", "library"],
        help="运行模式: web(服务模式) 或 library(库模式示例)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "web":
        print("启动 vprism Web 服务...")
        run_web_service()
    elif args.mode == "library":
        print("运行 vprism 库模式示例...")
        run_library_mode()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()