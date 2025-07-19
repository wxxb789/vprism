"""
Tests for provider registry system.

This module contains comprehensive tests for the provider registration
and discovery mechanism, following TDD principles with 100% coverage target.
"""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from vprism.core.exceptions import ConfigurationException
from vprism.core.interfaces import DataProvider
from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    MarketType,
    ProviderInfo,
)
from vprism.core.provider_registry import (
    ProviderRegistry,
    find_providers,
    get_global_registry,
    register_provider,
    unregister_provider,
)


class MockDataProvider(DataProvider):
    """Mock data provider for testing."""

    def __init__(
        self,
        name: str,
        supported_assets: set[AssetType] | None = None,
        can_handle: bool = True,
        is_healthy: bool = True,
    ):
        self._name = name
        self._supported_assets = supported_assets or {AssetType.STOCK}
        self._can_handle = can_handle
        self._is_healthy = is_healthy
        self._info = ProviderInfo(
            name=name,
            version="1.0.0",
            url=f"https://api.{name}.com",
            rate_limit=1000,
            cost="free",
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def info(self) -> ProviderInfo:
        return self._info

    @property
    def supported_assets(self) -> set[AssetType]:
        return self._supported_assets

    async def get_data(self, query: DataQuery) -> DataResponse:
        return MagicMock(spec=DataResponse)

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        yield MagicMock(spec=DataPoint)

    async def health_check(self) -> bool:
        return self._is_healthy

    def can_handle_query(self, query: DataQuery) -> bool:
        return self._can_handle and query.asset in self._supported_assets


class TestProviderRegistry:
    """Test ProviderRegistry class."""

    def test_provider_registry_initialization(self):
        """Test provider registry initialization."""
        registry = ProviderRegistry()
        
        assert registry.get_all_providers() == {}
        stats = registry.get_provider_statistics()
        assert stats["total_providers"] == 0
        assert stats["healthy_providers"] == 0

    def test_register_provider_success(self):
        """Test successful provider registration."""
        registry = ProviderRegistry()
        provider = MockDataProvider("test_provider")
        config = {"api_key": "test_key", "timeout": 30}

        registry.register_provider(provider, config)

        assert "test_provider" in registry.get_all_providers()
        assert registry.get_provider("test_provider") == provider
        assert registry.get_provider_config("test_provider") == config

    def test_register_provider_without_config(self):
        """Test provider registration without configuration."""
        registry = ProviderRegistry()
        provider = MockDataProvider("test_provider")

        registry.register_provider(provider)

        assert registry.get_provider_config("test_provider") == {}

    def test_register_provider_override_existing(self):
        """Test overriding existing provider registration."""
        registry = ProviderRegistry()
        provider1 = MockDataProvider("test_provider")
        provider2 = MockDataProvider("test_provider")

        registry.register_provider(provider1)
        registry.register_provider(provider2)

        # Should have the second provider
        assert registry.get_provider("test_provider") == provider2

    def test_register_invalid_provider(self):
        """Test registering invalid provider raises exception."""
        registry = ProviderRegistry()
        invalid_provider = "not_a_provider"

        with pytest.raises(ConfigurationException) as exc_info:
            registry.register_provider(invalid_provider)

        assert "Provider must implement DataProvider interface" in str(exc_info.value)
        assert exc_info.value.error_code == "CONFIGURATION_ERROR"

    def test_register_provider_empty_name(self):
        """Test registering provider with empty name raises exception."""
        registry = ProviderRegistry()
        
        class EmptyNameProvider(MockDataProvider):
            @property
            def name(self) -> str:
                return ""

        provider = EmptyNameProvider("empty")

        with pytest.raises(ConfigurationException) as exc_info:
            registry.register_provider(provider)

        assert "Provider name cannot be empty" in str(exc_info.value)

    def test_unregister_provider_success(self):
        """Test successful provider unregistration."""
        registry = ProviderRegistry()
        provider = MockDataProvider("test_provider")

        registry.register_provider(provider)
        assert "test_provider" in registry.get_all_providers()

        result = registry.unregister_provider("test_provider")
        
        assert result is True
        assert "test_provider" not in registry.get_all_providers()
        assert registry.get_provider("test_provider") is None

    def test_unregister_nonexistent_provider(self):
        """Test unregistering non-existent provider."""
        registry = ProviderRegistry()

        result = registry.unregister_provider("nonexistent")
        
        assert result is False

    def test_get_provider_existing(self):
        """Test getting existing provider."""
        registry = ProviderRegistry()
        provider = MockDataProvider("test_provider")

        registry.register_provider(provider)
        retrieved_provider = registry.get_provider("test_provider")

        assert retrieved_provider == provider

    def test_get_provider_nonexistent(self):
        """Test getting non-existent provider returns None."""
        registry = ProviderRegistry()

        provider = registry.get_provider("nonexistent")

        assert provider is None

    def test_get_all_providers(self):
        """Test getting all providers."""
        registry = ProviderRegistry()
        provider1 = MockDataProvider("provider1")
        provider2 = MockDataProvider("provider2")

        registry.register_provider(provider1)
        registry.register_provider(provider2)

        all_providers = registry.get_all_providers()

        assert len(all_providers) == 2
        assert "provider1" in all_providers
        assert "provider2" in all_providers
        assert all_providers["provider1"] == provider1
        assert all_providers["provider2"] == provider2

    def test_find_providers_by_query(self):
        """Test finding providers by query."""
        registry = ProviderRegistry()
        
        # Provider that can handle stocks
        stock_provider = MockDataProvider(
            "stock_provider", 
            supported_assets={AssetType.STOCK},
            can_handle=True
        )
        
        # Provider that can handle bonds
        bond_provider = MockDataProvider(
            "bond_provider", 
            supported_assets={AssetType.BOND},
            can_handle=True
        )
        
        # Provider that cannot handle queries
        disabled_provider = MockDataProvider(
            "disabled_provider",
            supported_assets={AssetType.STOCK},
            can_handle=False
        )

        registry.register_provider(stock_provider)
        registry.register_provider(bond_provider)
        registry.register_provider(disabled_provider)

        # Query for stocks
        stock_query = DataQuery(asset=AssetType.STOCK, market=MarketType.US)
        stock_providers = registry.find_providers(stock_query)

        assert len(stock_providers) == 1
        assert stock_providers[0] == stock_provider

        # Query for bonds
        bond_query = DataQuery(asset=AssetType.BOND, market=MarketType.US)
        bond_providers = registry.find_providers(bond_query)

        assert len(bond_providers) == 1
        assert bond_providers[0] == bond_provider

    def test_find_providers_excludes_unhealthy(self):
        """Test that unhealthy providers are excluded from search."""
        registry = ProviderRegistry()
        
        healthy_provider = MockDataProvider("healthy", is_healthy=True)
        unhealthy_provider = MockDataProvider("unhealthy", is_healthy=False)

        registry.register_provider(healthy_provider)
        registry.register_provider(unhealthy_provider)
        
        # Mark unhealthy provider as unhealthy
        registry.update_provider_health("unhealthy", False)

        query = DataQuery(asset=AssetType.STOCK)
        providers = registry.find_providers(query)

        assert len(providers) == 1
        assert providers[0] == healthy_provider

    def test_find_providers_by_asset(self):
        """Test finding providers by asset type."""
        registry = ProviderRegistry()
        
        stock_provider = MockDataProvider("stock", {AssetType.STOCK})
        bond_provider = MockDataProvider("bond", {AssetType.BOND})
        multi_provider = MockDataProvider("multi", {AssetType.STOCK, AssetType.ETF})

        registry.register_provider(stock_provider)
        registry.register_provider(bond_provider)
        registry.register_provider(multi_provider)

        # Find stock providers
        stock_providers = registry.find_providers_by_asset(AssetType.STOCK)
        assert len(stock_providers) == 2
        assert stock_provider in stock_providers
        assert multi_provider in stock_providers

        # Find bond providers
        bond_providers = registry.find_providers_by_asset(AssetType.BOND)
        assert len(bond_providers) == 1
        assert bond_provider in bond_providers

        # Find ETF providers
        etf_providers = registry.find_providers_by_asset(AssetType.ETF)
        assert len(etf_providers) == 1
        assert multi_provider in etf_providers

    def test_get_provider_config(self):
        """Test getting provider configuration."""
        registry = ProviderRegistry()
        provider = MockDataProvider("test_provider")
        config = {"api_key": "secret", "timeout": 60}

        registry.register_provider(provider, config)
        retrieved_config = registry.get_provider_config("test_provider")

        assert retrieved_config == config
        # Ensure it's a copy, not the original
        retrieved_config["new_key"] = "new_value"
        assert "new_key" not in registry.get_provider_config("test_provider")

    def test_get_provider_config_nonexistent(self):
        """Test getting config for non-existent provider."""
        registry = ProviderRegistry()

        config = registry.get_provider_config("nonexistent")

        assert config == {}

    def test_update_provider_config(self):
        """Test updating provider configuration."""
        registry = ProviderRegistry()
        provider = MockDataProvider("test_provider")
        initial_config = {"api_key": "old_key"}
        new_config = {"api_key": "new_key", "timeout": 30}

        registry.register_provider(provider, initial_config)
        registry.update_provider_config("test_provider", new_config)

        updated_config = registry.get_provider_config("test_provider")
        assert updated_config == new_config

    def test_update_provider_config_nonexistent(self):
        """Test updating config for non-existent provider raises exception."""
        registry = ProviderRegistry()

        with pytest.raises(ConfigurationException) as exc_info:
            registry.update_provider_config("nonexistent", {"key": "value"})

        assert "Provider not found: nonexistent" in str(exc_info.value)

    def test_get_provider_info(self):
        """Test getting provider information."""
        registry = ProviderRegistry()
        provider = MockDataProvider("test_provider")

        registry.register_provider(provider)
        info = registry.get_provider_info("test_provider")

        assert info == provider.info
        assert info.name == "test_provider"

    def test_get_provider_info_nonexistent(self):
        """Test getting info for non-existent provider returns None."""
        registry = ProviderRegistry()

        info = registry.get_provider_info("nonexistent")

        assert info is None

    def test_update_provider_health(self):
        """Test updating provider health status."""
        registry = ProviderRegistry()
        provider = MockDataProvider("test_provider")

        registry.register_provider(provider)
        
        # Initially healthy
        assert registry._provider_health["test_provider"] is True

        # Mark as unhealthy
        registry.update_provider_health("test_provider", False)
        assert registry._provider_health["test_provider"] is False

        # Mark as healthy again
        registry.update_provider_health("test_provider", True)
        assert registry._provider_health["test_provider"] is True

    def test_update_provider_health_nonexistent(self):
        """Test updating health for non-existent provider does nothing."""
        registry = ProviderRegistry()

        # Should not raise exception
        registry.update_provider_health("nonexistent", False)

    @pytest.mark.asyncio
    async def test_check_all_provider_health(self):
        """Test checking health of all providers."""
        registry = ProviderRegistry()
        
        healthy_provider = MockDataProvider("healthy", is_healthy=True)
        unhealthy_provider = MockDataProvider("unhealthy", is_healthy=False)

        registry.register_provider(healthy_provider)
        registry.register_provider(unhealthy_provider)

        health_results = await registry.check_all_provider_health()

        assert health_results["healthy"] is True
        assert health_results["unhealthy"] is False
        assert registry._provider_health["healthy"] is True
        assert registry._provider_health["unhealthy"] is False

    @pytest.mark.asyncio
    async def test_check_provider_health_with_exception(self):
        """Test health check handling provider exceptions."""
        registry = ProviderRegistry()
        
        class FailingProvider(MockDataProvider):
            async def health_check(self) -> bool:
                raise Exception("Health check failed")

        failing_provider = FailingProvider("failing")
        registry.register_provider(failing_provider)

        health_results = await registry.check_all_provider_health()

        assert health_results["failing"] is False
        assert registry._provider_health["failing"] is False

    def test_get_healthy_providers(self):
        """Test getting only healthy providers."""
        registry = ProviderRegistry()
        
        healthy1 = MockDataProvider("healthy1")
        healthy2 = MockDataProvider("healthy2")
        unhealthy = MockDataProvider("unhealthy")

        registry.register_provider(healthy1)
        registry.register_provider(healthy2)
        registry.register_provider(unhealthy)
        
        # Mark one as unhealthy
        registry.update_provider_health("unhealthy", False)

        healthy_providers = registry.get_healthy_providers()

        assert len(healthy_providers) == 2
        assert healthy1 in healthy_providers
        assert healthy2 in healthy_providers
        assert unhealthy not in healthy_providers

    def test_get_provider_statistics(self):
        """Test getting provider statistics."""
        registry = ProviderRegistry()
        
        stock_provider = MockDataProvider("stock", {AssetType.STOCK})
        bond_provider = MockDataProvider("bond", {AssetType.BOND})
        multi_provider = MockDataProvider("multi", {AssetType.STOCK, AssetType.ETF})

        registry.register_provider(stock_provider)
        registry.register_provider(bond_provider)
        registry.register_provider(multi_provider)
        
        # Mark one as unhealthy
        registry.update_provider_health("bond", False)

        stats = registry.get_provider_statistics()

        assert stats["total_providers"] == 3
        assert stats["healthy_providers"] == 2
        assert stats["unhealthy_providers"] == 1
        assert stats["asset_coverage"][AssetType.STOCK.value] == 2
        assert stats["asset_coverage"][AssetType.BOND.value] == 0  # Unhealthy provider excluded
        assert stats["asset_coverage"][AssetType.ETF.value] == 1
        assert set(stats["provider_names"]) == {"stock", "bond", "multi"}

    def test_sort_providers_by_preference(self):
        """Test provider sorting by preference."""
        registry = ProviderRegistry()
        
        provider_z = MockDataProvider("z_provider")
        provider_a = MockDataProvider("a_provider")
        provider_m = MockDataProvider("m_provider")

        providers = [provider_z, provider_a, provider_m]
        query = DataQuery(asset=AssetType.STOCK)

        sorted_providers = registry._sort_providers_by_preference(providers, query)

        # Should be sorted alphabetically by name
        assert sorted_providers[0] == provider_a
        assert sorted_providers[1] == provider_m
        assert sorted_providers[2] == provider_z


class TestGlobalRegistry:
    """Test global registry functions."""

    def test_get_global_registry_singleton(self):
        """Test that global registry is a singleton."""
        registry1 = get_global_registry()
        registry2 = get_global_registry()

        assert registry1 is registry2

    def test_register_provider_global(self):
        """Test registering provider with global registry."""
        provider = MockDataProvider("global_test")
        config = {"test": "config"}

        register_provider(provider, config)

        global_registry = get_global_registry()
        assert global_registry.get_provider("global_test") == provider
        assert global_registry.get_provider_config("global_test") == config

        # Cleanup
        unregister_provider("global_test")

    def test_unregister_provider_global(self):
        """Test unregistering provider from global registry."""
        provider = MockDataProvider("global_test")

        register_provider(provider)
        assert get_global_registry().get_provider("global_test") is not None

        result = unregister_provider("global_test")
        
        assert result is True
        assert get_global_registry().get_provider("global_test") is None

    def test_find_providers_global(self):
        """Test finding providers using global registry."""
        provider = MockDataProvider("global_test", {AssetType.STOCK})

        register_provider(provider)
        
        query = DataQuery(asset=AssetType.STOCK)
        providers = find_providers(query)

        assert provider in providers

        # Cleanup
        unregister_provider("global_test")


class TestProviderRegistryIntegration:
    """Integration tests for provider registry."""

    def test_complete_provider_lifecycle(self):
        """Test complete provider lifecycle."""
        registry = ProviderRegistry()
        provider = MockDataProvider(
            "lifecycle_test",
            supported_assets={AssetType.STOCK, AssetType.BOND},
            can_handle=True,
            is_healthy=True
        )
        config = {
            "api_key": "test_key",
            "base_url": "https://api.test.com",
            "timeout": 30
        }

        # 1. Register provider
        registry.register_provider(provider, config)
        assert registry.get_provider("lifecycle_test") == provider

        # 2. Find provider by query
        stock_query = DataQuery(asset=AssetType.STOCK, symbols=["AAPL"])
        found_providers = registry.find_providers(stock_query)
        assert provider in found_providers

        # 3. Update configuration
        new_config = {"api_key": "new_key", "timeout": 60}
        registry.update_provider_config("lifecycle_test", new_config)
        assert registry.get_provider_config("lifecycle_test") == new_config

        # 4. Check health
        registry.update_provider_health("lifecycle_test", False)
        unhealthy_query_result = registry.find_providers(stock_query)
        assert provider not in unhealthy_query_result

        # 5. Restore health
        registry.update_provider_health("lifecycle_test", True)
        healthy_query_result = registry.find_providers(stock_query)
        assert provider in healthy_query_result

        # 6. Get statistics
        stats = registry.get_provider_statistics()
        assert stats["total_providers"] == 1
        assert stats["healthy_providers"] == 1

        # 7. Unregister provider
        result = registry.unregister_provider("lifecycle_test")
        assert result is True
        assert registry.get_provider("lifecycle_test") is None

    @pytest.mark.asyncio
    async def test_health_monitoring_integration(self):
        """Test health monitoring integration."""
        registry = ProviderRegistry()
        
        # Create providers with different health states
        always_healthy = MockDataProvider("always_healthy", is_healthy=True)
        always_unhealthy = MockDataProvider("always_unhealthy", is_healthy=False)
        
        class FlakeyProvider(MockDataProvider):
            def __init__(self):
                super().__init__("flakey")
                self.health_calls = 0
            
            async def health_check(self) -> bool:
                self.health_calls += 1
                return self.health_calls % 2 == 1  # Alternates between healthy/unhealthy

        flakey = FlakeyProvider()

        registry.register_provider(always_healthy)
        registry.register_provider(always_unhealthy)
        registry.register_provider(flakey)

        # Initial health check
        health_results = await registry.check_all_provider_health()
        assert health_results["always_healthy"] is True
        assert health_results["always_unhealthy"] is False
        assert health_results["flakey"] is True

        # Second health check (flakey should now be unhealthy)
        health_results = await registry.check_all_provider_health()
        assert health_results["flakey"] is False

        # Verify healthy providers list
        healthy_providers = registry.get_healthy_providers()
        provider_names = [p.name for p in healthy_providers]
        assert "always_healthy" in provider_names
        assert "always_unhealthy" not in provider_names
        assert "flakey" not in provider_names