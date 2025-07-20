"""
VPrism Native Provider Usage Example.

This example demonstrates how to use the VPrism native provider,
which provides a modern interface to akshare's 1000+ functions.
"""

import asyncio
from datetime import datetime
from vprism.core.models import AssetType, MarketType, TimeFrame, DataQuery
from vprism.core.providers.vprism_native_provider import VPrismNativeProvider


async def main():
    """Demonstrate VPrism native provider usage."""
    print("VPrism Native Provider Example")
    print("=" * 40)
    
    try:
        # Initialize the VPrism native provider
        provider = VPrismNativeProvider()
        print(f"✓ Initialized {provider.name} provider")
        
        # Check provider capabilities
        capability = provider.capability
        print(f"✓ Supported assets: {len(capability.supported_assets)}")
        print(f"✓ Supported markets: {capability.supported_markets}")
        print(f"✓ Max symbols per request: {capability.max_symbols_per_request}")
        
        # Health check
        is_healthy = await provider.health_check()
        print(f"✓ Provider health: {'Healthy' if is_healthy else 'Unhealthy'}")
        
        if not is_healthy:
            print("⚠ Provider is not healthy, skipping data retrieval examples")
            return
        
        # Example 1: Get Chinese stock spot data
        print("\n1. Chinese Stock Spot Data")
        print("-" * 30)
        
        spot_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001", "000002"]  # Ping An Bank, Vanke
        )
        
        try:
            spot_response = await provider.get_data(spot_query)
            print(f"✓ Retrieved {len(spot_response.data)} data points")
            print(f"✓ Execution time: {spot_response.metadata.execution_time_ms:.2f}ms")
            
            if spot_response.data:
                sample_point = spot_response.data[0]
                print(f"✓ Sample data: {sample_point.symbol} - Close: {sample_point.close}")
        
        except Exception as e:
            print(f"✗ Error retrieving spot data: {e}")
        
        # Example 2: Get historical daily data
        print("\n2. Historical Daily Data")
        print("-" * 30)
        
        daily_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 31)
        )
        
        try:
            daily_response = await provider.get_data(daily_query)
            print(f"✓ Retrieved {len(daily_response.data)} daily data points")
            print(f"✓ Date range: {daily_response.data[0].timestamp} to {daily_response.data[-1].timestamp}")
            
        except Exception as e:
            print(f"✗ Error retrieving daily data: {e}")
        
        # Example 3: Get ETF data
        print("\n3. ETF Data")
        print("-" * 30)
        
        etf_query = DataQuery(
            asset=AssetType.ETF,
            market=MarketType.CN,
            symbols=["510050"]  # 50 ETF
        )
        
        try:
            etf_response = await provider.get_data(etf_query)
            print(f"✓ Retrieved {len(etf_response.data)} ETF data points")
            
            if etf_response.data:
                sample_etf = etf_response.data[0]
                print(f"✓ ETF data: {sample_etf.symbol} - Close: {sample_etf.close}")
                print(f"✓ Extra fields: {list(sample_etf.extra_fields.keys())}")
        
        except Exception as e:
            print(f"✗ Error retrieving ETF data: {e}")
        
        # Example 4: Show supported functions
        print("\n4. Supported Functions")
        print("-" * 30)
        
        functions = provider.get_supported_functions()
        print(f"✓ Total supported functions: {len(functions)}")
        
        # Show a few examples
        for i, (key, description) in enumerate(list(functions.items())[:5]):
            print(f"  {i+1}. {key}: {description}")
        
        print("  ...")
        
        # Example 5: Function mapping inspection
        print("\n5. Function Mapping Details")
        print("-" * 30)
        
        mapping = provider.get_function_mapping()
        stock_cn_spot = mapping.get("stock_cn_spot", {})
        print(f"✓ stock_cn_spot maps to: {stock_cn_spot.get('function')}")
        print(f"✓ Parameters: {stock_cn_spot.get('params')}")
        
        print("\n✓ VPrism Native Provider example completed successfully!")
        
    except Exception as e:
        print(f"✗ Error initializing provider: {e}")
        print("Make sure akshare is installed: pip install akshare")


if __name__ == "__main__":
    asyncio.run(main())