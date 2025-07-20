"""
Example demonstrating provider usage and configuration.

This example shows how to configure and use different data providers
with the vprism platform.
"""

import asyncio
import os
from datetime import datetime, timedelta

from vprism.core.provider_factory import ProviderManager
from vprism.core.provider_config import ProviderConfigManager
from vprism.core.models import DataQuery, AssetType, MarketType, TimeFrame


async def main():
    """Demonstrate provider usage."""
    print("vprism Provider Usage Example")
    print("=" * 40)
    
    # Create provider manager
    config_manager = ProviderConfigManager()
    provider_manager = ProviderManager(config_manager)
    
    # Configure Alpha Vantage if API key is available
    alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if alpha_vantage_key:
        print(f"Configuring Alpha Vantage with API key: {alpha_vantage_key[:8]}...")
        provider_manager.configure_alpha_vantage(alpha_vantage_key)
    else:
        print("No Alpha Vantage API key found in environment")
    
    # Initialize providers
    print("\nInitializing providers...")
    provider_manager.initialize()
    
    # Get provider status
    print("\nProvider Status:")
    status = provider_manager.get_provider_status()
    for name, info in status.items():
        print(f"  {name}:")
        print(f"    Enabled: {info['enabled']}")
        print(f"    Healthy: {info['healthy']}")
        print(f"    Score: {info['score']:.2f}")
        print(f"    Supports Real-time: {info['capability']['supports_real_time']}")
        print(f"    Supported Assets: {', '.join(info['capability']['supported_assets'])}")
        print()
    
    # Get registry for querying
    registry = provider_manager.get_registry()
    
    # Example query
    query = DataQuery(
        asset=AssetType.STOCK,
        market=MarketType.US,
        symbols=["AAPL"],
        timeframe=TimeFrame.DAY_1,
        start=datetime.now() - timedelta(days=30),
        end=datetime.now()
    )
    
    print(f"Example Query: {query.asset.value} data for {query.symbols}")
    
    # Find capable providers
    capable_providers = registry.find_capable_providers(query)
    print(f"\nProviders capable of handling this query:")
    for provider in capable_providers:
        print(f"  - {provider.name}")
        print(f"    Priority Score: {registry.get_provider_score(provider.name):.2f}")
        print(f"    Can handle query: {provider.can_handle_query(query)}")
    
    if capable_providers:
        print(f"\nBest provider: {capable_providers[0].name}")
        
        # Example: Try to get data (this would normally make real API calls)
        try:
            print("\nAttempting to fetch data...")
            print("(Note: This would make real API calls in a production environment)")
            
            # For demonstration, we'll just show the query structure
            print(f"Query details:")
            print(f"  Asset: {query.asset.value}")
            print(f"  Market: {query.market.value if query.market else 'Any'}")
            print(f"  Symbols: {query.symbols}")
            print(f"  Timeframe: {query.timeframe.value if query.timeframe else 'Any'}")
            print(f"  Date range: {query.start} to {query.end}")
            
        except Exception as e:
            print(f"Error fetching data: {e}")
    else:
        print("\nNo providers available for this query")
    
    # Health check all providers
    print("\nPerforming health checks...")
    health_results = await provider_manager.health_check_all()
    for provider_name, is_healthy in health_results.items():
        status_text = "✓ Healthy" if is_healthy else "✗ Unhealthy"
        print(f"  {provider_name}: {status_text}")
    
    print("\nExample completed!")


if __name__ == "__main__":
    asyncio.run(main())