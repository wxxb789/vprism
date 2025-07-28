"""vprism库模式使用示例（简化版）"""

from datetime import date, datetime

import vprism
from vprism.core.client import VPrismClient


def format_table(data_list, title):
    """将数据格式化为表格输出"""
    if not data_list:
        print("无数据")
        return

    # 取前10条记录
    records = data_list[:10]

    # 获取所有字段名
    all_keys = set()
    for record in records:
        if hasattr(record, "__dict__"):
            all_keys.update(record.__dict__.keys())
        elif isinstance(record, dict):
            all_keys.update(record.keys())

    if not all_keys:
        print("无有效数据字段")
        return

    # 转换为列表并保持顺序
    headers = sorted(all_keys)

    # 准备数据行
    rows = []
    for record in records:
        row = []
        for header in headers:
            if hasattr(record, "__dict__"):
                value = record.__dict__.get(header, "")
            elif isinstance(record, dict):
                value = record.get(header, "")
            else:
                value = str(record)

            # 格式化datetime对象
            if isinstance(value, datetime | date):
                value = value.strftime("%Y-%m-%d %H:%M:%S")
            elif value is None:
                value = ""
            else:
                value = str(value)

            # 截断长字符串
            if len(value) > 20:
                value = value[:17] + "..."
            row.append(value)
        rows.append(row)

    # 计算列宽
    col_widths = []
    for i, header in enumerate(headers):
        max_width = max(len(str(header)), max(len(row[i]) for row in rows) if rows else 0)
        col_widths.append(min(max_width + 2, 25))  # 最大宽度25

    # 打印标题
    print(f"\n=== {title} ===")
    print(f"显示前10条记录，共{len(data_list)}条数据")

    # 打印表头
    header_line = ""
    for i, header in enumerate(headers):
        header_line += str(header).ljust(col_widths[i])[: col_widths[i]]
    print(header_line)
    print("-" * (sum(col_widths) + len(col_widths) - 1))

    # 打印数据行
    for row in rows:
        line = ""
        for i, cell in enumerate(row):
            line += cell.ljust(col_widths[i])[: col_widths[i]]
        print(line)


def print_data_sample(data, title):
    """打印数据样本（表格格式）"""
    if hasattr(data, "data") and data.data:
        format_table(data.data, title)
    else:
        print("无数据")


def basic_usage():
    """基础用法示例"""
    print("=== 基础用法示例 ===")

    # 获取中国A股数据
    try:
        data = vprism.get(asset="stock", market="cn", symbols=["000001"], timeframe="1d", limit=10)
        print_data_sample(data, "中国A股数据 - 平安银行(000001)")
    except Exception as e:
        print(f"获取中国A股数据失败: {e}")

    # 获取美股数据
    try:
        data = vprism.get(asset="stock", market="us", symbols=["AAPL"], timeframe="1d", limit=10)
        print_data_sample(data, "美股数据 - 苹果(AAPL)")
    except Exception as e:
        print(f"获取美股数据失败: {e}")

    # 获取加密货币数据
    try:
        data = vprism.get(asset="crypto", market="global", symbols=["BTC"], timeframe="1d", limit=10)
        print_data_sample(data, "加密货币数据 - 比特币(BTC)")
    except Exception as e:
        print(f"获取加密货币数据失败: {e}")


def advanced_usage():
    """高级用法示例"""
    print("\n=== 高级用法示例 ===")

    # 创建客户端实例
    client = VPrismClient()

    # 配置客户端
    client.configure(
        cache={"enabled": True, "memory_size": 2000, "disk_path": "/tmp/vprism_cache"},
        providers={"timeout": 60, "max_retries": 5, "rate_limit": True},
    )

    # 使用简单API获取数据
    try:
        data = client.get(asset="stock", market="us", symbols=["GOOGL"], timeframe="1d", limit=10)
        print_data_sample(data, "谷歌股票数据 - GOOGL")
    except Exception as e:
        print(f"谷歌股票数据获取失败: {e}")


def configuration_usage():
    """配置用法示例"""
    print("\n=== 配置用法示例 ===")

    # 使用默认配置
    client1 = VPrismClient()

    # 使用自定义配置
    client2 = VPrismClient(
        {
            "cache": {
                "enabled": False,  # 禁用缓存
                "memory_size": 500,
            },
            "providers": {"timeout": 120, "max_retries": 10},
            "logging": {"level": "DEBUG", "file": "/tmp/vprism_debug.log"},
        }
    )

    # 运行时配置
    client3 = VPrismClient()
    client3.configure(providers={"timeout": 45}, logging={"level": "WARNING"})

    print("配置示例完成")


def error_handling_example():
    """错误处理示例"""
    print("\n=== 错误处理示例 ===")

    try:
        # 尝试获取不存在的股票代码
        data = vprism.get(asset="stock", market="cn", symbols=["INVALID_CODE"], timeframe="1d")
    except vprism.VPrismException as e:
        print(f"捕获vprism异常: {e}")
    except Exception as e:
        print(f"捕获其他异常: {e}")


def batch_usage():
    """批量查询示例"""
    print("\n=== 批量查询示例 ===")

    # 批量查询不同市场
    markets = ["cn", "us", "global"]
    symbols = [["000001"], ["AAPL"], ["BTC"]]
    names = ["平安银行(000001)", "苹果(AAPL)", "比特币(BTC)"]

    for market, symbol_list, name in zip(markets, symbols, names, strict=False):
        try:
            data = vprism.get(
                asset="stock",
                market=market,
                symbols=symbol_list,
                timeframe="1d",
                limit=10,
            )
            print_data_sample(data, f"{market}市场数据 - {name}")
        except Exception as e:
            print(f"{market}市场数据获取失败: {e}")


def main():
    """主函数"""
    print("vprism库模式使用示例")
    print("=" * 50)

    # 基础用法
    basic_usage()

    # 高级用法
    advanced_usage()

    # 配置用法
    configuration_usage()

    # 错误处理
    error_handling_example()

    # 批量查询
    batch_usage()

    print("\n" + "=" * 50)
    print("所有示例执行完成")


if __name__ == "__main__":
    main()
