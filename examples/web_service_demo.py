#!/usr/bin/env python3
"""
Web 服务演示脚本
展示如何使用 vprism 的 FastAPI Web 服务
"""

import requests


def demo_web_service():
    """演示 Web 服务功能"""

    base_url = "http://localhost:8000/api/v1"

    print("=== vprism Web 服务演示 ===\n")

    # 1. 健康检查
    print("1. 健康检查...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            health_data = response.json()
            print(f"   ✓ 系统状态: {health_data['data']['status']}")
            print(f"   ✓ 版本: {health_data['data']['version']}")
        else:
            print(f"   ✗ 健康检查失败: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 连接失败: {e}")
        return

    # 2. 获取股票数据 (GET)
    print("\n2. 获取股票数据 (GET)...")
    try:
        response = requests.get(f"{base_url}/data/stock/AAPL?market=us&timeframe=1d&limit=5")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ 成功获取 {len(data['data']['data'])} 条 AAPL 数据")
            print(f"   ✓ 最近收盘价: {data['data']['data'][0]['close']}")
        else:
            print(f"   ✗ 获取数据失败: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 获取数据失败: {e}")

    # 3. 获取股票数据 (POST)
    print("\n3. 获取股票数据 (POST)...")
    try:
        payload = {"symbol": "MSFT", "market": "us", "timeframe": "1d", "limit": 3}
        response = requests.post(f"{base_url}/data/stock", json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ 成功获取 {len(data['data']['data'])} 条 MSFT 数据")
        else:
            print(f"   ✗ 获取数据失败: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 获取数据失败: {e}")

    # 4. 批量数据查询
    print("\n4. 批量数据查询...")
    try:
        payload = {
            "queries": [
                {"symbol": "AAPL", "market": "us", "timeframe": "1d", "limit": 2},
                {"symbol": "GOOGL", "market": "us", "timeframe": "1d", "limit": 2},
            ],
            "async_processing": False,
        }
        response = requests.post(f"{base_url}/data/batch", json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ 成功获取 {len(data['data'])} 只股票的数据")
            for item in data["data"]:
                print(f"   ✓ {item['query']['symbol']}: {len(item['data']['data'])} 条记录")
        else:
            print(f"   ✗ 批量查询失败: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 批量查询失败: {e}")

    # 5. 获取市场数据
    print("\n5. 获取市场数据...")
    try:
        payload = {
            "market": "us",
            "timeframe": "1d",
            "symbols": ["AAPL", "MSFT", "GOOGL"],
            "limit": 2,
        }
        response = requests.post(f"{base_url}/data/market", json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ 成功获取 {len(data['data'])} 只股票的市场数据")
        else:
            print(f"   ✗ 获取市场数据失败: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 获取市场数据失败: {e}")

    # 6. 获取股票代码列表
    print("\n6. 获取股票代码列表...")
    try:
        response = requests.get(f"{base_url}/data/symbols?market=us")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ 成功获取 {len(data['data'])} 个美国股票代码")
            print(f"   ✓ 示例代码: {', '.join(data['data'][:5])}")
        else:
            print(f"   ✗ 获取股票代码失败: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 获取股票代码失败: {e}")

    # 7. 获取系统指标
    print("\n7. 获取系统指标...")
    try:
        response = requests.get(f"{base_url}/metrics")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ 系统运行时间: {data['data']['uptime']:.2f}秒")
            print(f"   ✓ 请求总数: {data['data']['requests_count']}")
        else:
            print(f"   ✗ 获取指标失败: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 获取指标失败: {e}")

    print("\n=== 演示完成 ===")
    print("\n使用说明:")
    print("1. 启动服务: python main.py web")
    print("2. 访问文档: http://localhost:8000/docs")
    print("3. 访问ReDoc: http://localhost:8000/redoc")


if __name__ == "__main__":
    demo_web_service()
