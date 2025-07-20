"""数据提供商使用示例."""

import asyncio
from datetime import date

from vprism.core.models import AssetType, DataQuery, MarketType, TimeFrame
from vprism.infrastructure.providers.factory import ProviderFactory
from vprism.infrastructure.providers.registry import ProviderRegistry


async def main():
    """主函数演示提供商使用."""
    print("=== vprism 数据提供商框架演示 ===\n")

    # 1. 创建提供商工厂
    print("1. 创建数据提供商...")

    # 创建Yahoo Finance提供商
    yahoo_provider = ProviderFactory.create_yahoo_provider()
    print(f"   ✓ Yahoo Finance: {yahoo_provider.name}")

    # 创建AkShare提供商
    akshare_provider = ProviderFactory.create_akshare_provider()
    print(f"   ✓ AkShare: {akshare_provider.name}")

    # 2. 创建注册表并注册提供商
    print("\n2. 创建提供商注册表...")
    registry = ProviderRegistry()
    registry.register(yahoo_provider)
    registry.register(akshare_provider)
    print(f"   ✓ 已注册 {len(registry)} 个提供商")

    # 3. 测试提供商能力
    print("\n3. 提供商能力概览:")
    for name, provider in registry.providers.items():
        cap = provider.capability
        print(f"   - {name}: 支持市场 {list(cap.supported_markets)}")
        print(f"     支持资产 {list(cap.supported_assets)}")
        print(f"     支持时间框架 {list(cap.supported_timeframes)}")
        print(f"     最大股票数: {cap.max_symbols_per_request}")

    # 4. 创建查询示例
    print("\n4. 创建数据查询...")
    query = DataQuery(
        asset=AssetType.STOCK,
        market=MarketType.US,
        symbols=["AAPL"],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 10),
        timeframe=TimeFrame.DAY_1,
    )
    print(f"   ✓ 查询: {query.symbols} 在 {query.market.value} 市场")

    # 5. 找到能处理查询的提供商
    print("\n5. 查找能处理查询的提供商...")
    capable_providers = registry.find_capable_providers(query)
    print(f"   ✓ 找到 {len(capable_providers)} 个可用提供商")

    for provider in capable_providers:
        print(f"   - {provider.name}: {provider.can_handle_query(query)}")

    # 6. 按市场创建提供商
    print("\n6. 按市场自动选择提供商...")
    cn_provider = ProviderFactory.create_provider_by_market(MarketType.CN)
    us_provider = ProviderFactory.create_provider_by_market(MarketType.US)

    print(f"   ✓ 中国市场: {cn_provider.name}")
    print(f"   ✓ 美国市场: {us_provider.name}")

    # 7. 获取提供商列表
    print("\n7. 提供商健康状态:")
    summary = registry.get_health_summary()
    print(f"   ✓ 总计: {summary['total_providers']} 个提供商")
    print(f"   ✓ 健康: {summary['healthy_providers']} 个")
    print(f"   ✓ 健康率: {summary['health_percentage']:.1f}%")

    print("\n=== 演示完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
