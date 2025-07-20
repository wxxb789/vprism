"""
Examples demonstrating both API styles in vprism.

This file shows how to use both the simple API and the builder API
for different use cases.
"""

import asyncio
from datetime import datetime

import vprism
from vprism import AssetType, MarketType, TimeFrame


def simple_api_examples():
    """Examples using the simple API style."""
    print("=== Simple API Examples ===")
    
    # Note: These examples show the API usage but won't work without real providers
    # In a real scenario, you would have configured data providers
    
    try:
        # Basic stock data query
        print("1. Basic stock query:")
        print("   vprism.get(asset=AssetType.STOCK, market=MarketType.CN, symbols=['000001'])")
        
        # Query with date range
        print("\n2. Query with date range:")
        print("   vprism.get(")
        print("       asset=AssetType.STOCK,")
        print("       symbols=['000001'],")
        print("       start='2024-01-01',")
        print("       end='2024-12-31'")
        print("   )")
        
        # Query with specific provider
        print("\n3. Query with specific provider:")
        print("   vprism.get(")
        print("       asset=AssetType.STOCK,")
        print("       provider='tushare',")
        print("       symbols=['000001']")
        print("   )")
        
    except Exception as e:
        print(f"Note: Examples would work with configured providers. Error: {e}")


def builder_api_examples():
    """Examples using the builder API style."""
    print("\n=== Builder API Examples ===")
    
    try:
        # Basic query construction
        print("1. Basic query construction:")
        query1 = (vprism.query()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001"])
            .build())
        print(f"   Query: {query1}")
        
        # Complex query with all parameters
        print("\n2. Complex query construction:")
        query2 = (vprism.query()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001", "000002"])
            .timeframe(TimeFrame.DAY_1)
            .date_range("2024-01-01", "2024-12-31")
            .provider("tushare")
            .limit(100)
            .filter("adj", "qfq")
            .build())
        print(f"   Query: {query2}")
        
        # Incremental query building
        print("\n3. Incremental query building:")
        base_query = (vprism.query()
            .asset(AssetType.STOCK)
            .market(MarketType.CN))
        
        # Create different variations
        daily_query = base_query.copy().timeframe(TimeFrame.DAY_1).symbols(["000001"]).build()
        hourly_query = base_query.copy().timeframe(TimeFrame.HOUR_1).symbols(["000002"]).build()
        
        print(f"   Daily query: {daily_query}")
        print(f"   Hourly query: {hourly_query}")
        
        # Query reuse and modification
        print("\n4. Query reuse and modification:")
        builder = vprism.query().asset(AssetType.STOCK).market(MarketType.CN)
        
        # Add symbols one by one
        multi_symbol_query = (builder.copy()
            .symbol("000001")
            .symbol("000002")
            .symbol("000003")
            .build())
        print(f"   Multi-symbol query: {multi_symbol_query}")
        
    except Exception as e:
        print(f"Builder examples completed. Note: {e}")


async def async_api_examples():
    """Examples using async APIs."""
    print("\n=== Async API Examples ===")
    
    try:
        # Simple async API
        print("1. Simple async API:")
        print("   data = await vprism.aget(asset=AssetType.STOCK, symbols=['000001'])")
        
        # Builder with async execution
        print("\n2. Builder with async execution:")
        query = (vprism.query()
            .asset(AssetType.STOCK)
            .symbols(["000001"])
            .build())
        print(f"   Query: {query}")
        print("   data = await vprism.execute(query)")
        
    except Exception as e:
        print(f"Async examples completed. Note: {e}")


def api_equivalence_demo():
    """Demonstrate that both APIs produce equivalent queries."""
    print("\n=== API Equivalence Demo ===")
    
    # Same query using both APIs
    print("Both APIs can produce equivalent queries:")
    
    # Simple API parameters (would be used like this)
    simple_params = {
        'asset': AssetType.STOCK,
        'market': MarketType.CN,
        'symbols': ['000001'],
        'timeframe': TimeFrame.DAY_1,
        'start': '2024-01-01',
        'end': '2024-12-31',
        'provider': 'tushare',
        'limit': 100
    }
    print(f"1. Simple API params: {simple_params}")
    
    # Builder API equivalent
    builder_query = (vprism.query()
        .asset(AssetType.STOCK)
        .market(MarketType.CN)
        .symbols(['000001'])
        .timeframe(TimeFrame.DAY_1)
        .date_range('2024-01-01', '2024-12-31')
        .provider('tushare')
        .limit(100)
        .build())
    print(f"2. Builder API query: {builder_query}")
    
    # Show they have the same essential properties
    print("\nQuery properties:")
    print(f"   Asset: {builder_query.asset}")
    print(f"   Market: {builder_query.market}")
    print(f"   Symbols: {builder_query.symbols}")
    print(f"   Timeframe: {builder_query.timeframe}")
    print(f"   Start: {builder_query.start}")
    print(f"   End: {builder_query.end}")
    print(f"   Provider: {builder_query.provider}")
    print(f"   Limit: {builder_query.limit}")


def advanced_builder_patterns():
    """Advanced patterns with the builder API."""
    print("\n=== Advanced Builder Patterns ===")
    
    # Template pattern
    print("1. Template pattern:")
    stock_template = (vprism.query()
        .asset(AssetType.STOCK)
        .market(MarketType.CN)
        .timeframe(TimeFrame.DAY_1))
    
    # Create specific queries from template
    query_a = stock_template.copy().symbols(["000001"]).build()
    query_b = stock_template.copy().symbols(["000002"]).provider("tushare").build()
    
    print(f"   Template-based query A: {query_a}")
    print(f"   Template-based query B: {query_b}")
    
    # Conditional building
    print("\n2. Conditional building:")
    builder = vprism.query().asset(AssetType.STOCK)
    
    # Add conditions based on some logic
    use_specific_market = True
    use_date_filter = True
    
    if use_specific_market:
        builder = builder.market(MarketType.CN)
    
    if use_date_filter:
        builder = builder.date_range("2024-01-01", "2024-12-31")
    
    conditional_query = builder.symbols(["000001"]).build()
    print(f"   Conditional query: {conditional_query}")
    
    # Filter chaining
    print("\n3. Filter chaining:")
    filtered_query = (vprism.query()
        .asset(AssetType.STOCK)
        .symbols(["000001"])
        .filter("adj", "qfq")
        .filter("ma_period", 20)
        .filter("volume_min", 1000000)
        .build())
    print(f"   Filtered query: {filtered_query}")
    print(f"   Filters: {filtered_query.filters}")


def main():
    """Run all examples."""
    print("vprism Dual API Examples")
    print("=" * 50)
    
    simple_api_examples()
    builder_api_examples()
    asyncio.run(async_api_examples())
    api_equivalence_demo()
    advanced_builder_patterns()
    
    print("\n" + "=" * 50)
    print("Examples completed!")
    print("\nKey takeaways:")
    print("1. Simple API: vprism.get() for quick, straightforward queries")
    print("2. Builder API: vprism.query().build() for complex, reusable queries")
    print("3. Both APIs share the same underlying implementation")
    print("4. Builder API provides more flexibility for complex scenarios")
    print("5. Both support sync and async execution")


if __name__ == "__main__":
    main()