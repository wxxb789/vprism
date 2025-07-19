"""
Provider registry for managing data providers.

This module implements the provider registration and discovery mechanism,
allowing dynamic registration of data providers and intelligent selection
based on query requirements.
"""

from __future__ import annotations

import logging
from typing import Any

from vprism.core.exceptions import (
    ConfigurationException,
    NoAvailableProviderException,
    ProviderException,
)
from vprism.core.interfaces import DataProvider
from vprism.core.models import AssetType, DataQuery, ProviderInfo

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Registry for managing data providers.

    Handles provider registration, discovery, and selection based on
    query requirements and provider capabilities.
    """

    def __init__(self) -> None:
        """Initialize the provider registry."""
        self._providers: dict[str, DataProvider] = {}
        self._provider_configs: dict[str, dict[str, Any]] = {}
        self._provider_health: dict[str, bool] = {}

    def register_provider(
        self,
        provider: DataProvider,
        config: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a data provider.

        Args:
            provider: The data provider to register
            config: Optional configuration for the provider

        Raises:
            ConfigurationException: When provider configuration is invalid
        """
        if not isinstance(provider, DataProvider):
            raise ConfigurationException(
                "Provider must implement DataProvider interface",
                config_key="provider_type",
                details={"provider_class": type(provider).__name__},
            )

        provider_name = provider.name
        if not provider_name:
            raise ConfigurationException(
                "Provider name cannot be empty",
                config_key="provider_name",
            )

        if provider_name in self._providers:
            logger.warning(f"Overriding existing provider: {provider_name}")

        self._providers[provider_name] = provider
        self._provider_configs[provider_name] = config or {}
        self._provider_health[provider_name] = True  # Assume healthy initially

        logger.info(f"Registered provider: {provider_name}")

    def unregister_provider(self, provider_name: str) -> bool:
        """
        Unregister a data provider.

        Args:
            provider_name: Name of the provider to unregister

        Returns:
            bool: True if provider was unregistered, False if not found
        """
        if provider_name not in self._providers:
            return False

        del self._providers[provider_name]
        self._provider_configs.pop(provider_name, None)
        self._provider_health.pop(provider_name, None)

        logger.info(f"Unregistered provider: {provider_name}")
        return True

    def get_provider(self, provider_name: str) -> DataProvider | None:
        """
        Get a specific provider by name.

        Args:
            provider_name: Name of the provider

        Returns:
            DataProvider or None if not found
        """
        return self._providers.get(provider_name)

    def get_all_providers(self) -> dict[str, DataProvider]:
        """
        Get all registered providers.

        Returns:
            Dictionary mapping provider names to provider instances
        """
        return self._providers.copy()

    def find_providers(self, query: DataQuery) -> list[DataProvider]:
        """
        Find providers that can handle the given query.

        Args:
            query: The data query to match against

        Returns:
            List of compatible providers, ordered by preference
        """
        compatible_providers = []

        for provider_name, provider in self._providers.items():
            # Skip unhealthy providers
            if not self._provider_health.get(provider_name, False):
                continue

            # Check if provider can handle the query
            if provider.can_handle_query(query):
                compatible_providers.append(provider)

        # Sort providers by preference (can be enhanced with more sophisticated logic)
        return self._sort_providers_by_preference(compatible_providers, query)

    def find_providers_by_asset(self, asset_type: AssetType) -> list[DataProvider]:
        """
        Find providers that support a specific asset type.

        Args:
            asset_type: The asset type to search for

        Returns:
            List of providers supporting the asset type
        """
        compatible_providers = []

        for provider_name, provider in self._providers.items():
            # Skip unhealthy providers
            if not self._provider_health.get(provider_name, False):
                continue

            if asset_type in provider.supported_assets:
                compatible_providers.append(provider)

        return compatible_providers

    def get_provider_config(self, provider_name: str) -> dict[str, Any]:
        """
        Get configuration for a specific provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Provider configuration dictionary
        """
        return self._provider_configs.get(provider_name, {}).copy()

    def update_provider_config(
        self, provider_name: str, config: dict[str, Any]
    ) -> None:
        """
        Update configuration for a specific provider.

        Args:
            provider_name: Name of the provider
            config: New configuration dictionary

        Raises:
            ConfigurationException: When provider is not found
        """
        if provider_name not in self._providers:
            raise ConfigurationException(
                f"Provider not found: {provider_name}",
                config_key="provider_name",
                details={"provider_name": provider_name},
            )

        self._provider_configs[provider_name] = config.copy()
        logger.info(f"Updated configuration for provider: {provider_name}")

    def get_provider_info(self, provider_name: str) -> ProviderInfo | None:
        """
        Get information about a specific provider.

        Args:
            provider_name: Name of the provider

        Returns:
            ProviderInfo or None if provider not found
        """
        provider = self._providers.get(provider_name)
        return provider.info if provider else None

    def update_provider_health(self, provider_name: str, is_healthy: bool) -> None:
        """
        Update the health status of a provider.

        Args:
            provider_name: Name of the provider
            is_healthy: Whether the provider is healthy
        """
        if provider_name in self._providers:
            self._provider_health[provider_name] = is_healthy
            status = "healthy" if is_healthy else "unhealthy"
            logger.info(f"Provider {provider_name} marked as {status}")

    async def check_all_provider_health(self) -> dict[str, bool]:
        """
        Check health of all registered providers.

        Returns:
            Dictionary mapping provider names to health status
        """
        health_results = {}

        for provider_name, provider in self._providers.items():
            try:
                is_healthy = await provider.health_check()
                self.update_provider_health(provider_name, is_healthy)
                health_results[provider_name] = is_healthy
            except Exception as e:
                logger.error(f"Health check failed for provider {provider_name}: {e}")
                self.update_provider_health(provider_name, False)
                health_results[provider_name] = False

        return health_results

    def get_healthy_providers(self) -> list[DataProvider]:
        """
        Get all healthy providers.

        Returns:
            List of healthy providers
        """
        healthy_providers = []
        for provider_name, provider in self._providers.items():
            if self._provider_health.get(provider_name, False):
                healthy_providers.append(provider)
        return healthy_providers

    def get_provider_statistics(self) -> dict[str, Any]:
        """
        Get statistics about registered providers.

        Returns:
            Dictionary containing provider statistics
        """
        total_providers = len(self._providers)
        healthy_providers = sum(self._provider_health.values())
        unhealthy_providers = total_providers - healthy_providers

        asset_coverage = {}
        for asset_type in AssetType:
            providers_for_asset = len(self.find_providers_by_asset(asset_type))
            asset_coverage[asset_type.value] = providers_for_asset

        return {
            "total_providers": total_providers,
            "healthy_providers": healthy_providers,
            "unhealthy_providers": unhealthy_providers,
            "asset_coverage": asset_coverage,
            "provider_names": list(self._providers.keys()),
        }

    def _sort_providers_by_preference(
        self, providers: list[DataProvider], query: DataQuery
    ) -> list[DataProvider]:
        """
        Sort providers by preference for the given query.

        This is a basic implementation that can be enhanced with more
        sophisticated logic based on factors like:
        - Provider reliability/uptime
        - Data quality scores
        - Response times
        - Cost considerations
        - User preferences

        Args:
            providers: List of providers to sort
            query: The query context for sorting

        Returns:
            Sorted list of providers
        """
        # For now, sort by provider name for consistent ordering
        # This can be enhanced with more sophisticated preference logic
        return sorted(providers, key=lambda p: p.name)


# Global provider registry instance
_global_registry: ProviderRegistry | None = None


def get_global_registry() -> ProviderRegistry:
    """
    Get the global provider registry instance.

    Returns:
        Global ProviderRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ProviderRegistry()
    return _global_registry


def register_provider(
    provider: DataProvider, config: dict[str, Any] | None = None
) -> None:
    """
    Register a provider with the global registry.

    Args:
        provider: The data provider to register
        config: Optional configuration for the provider
    """
    get_global_registry().register_provider(provider, config)


def unregister_provider(provider_name: str) -> bool:
    """
    Unregister a provider from the global registry.

    Args:
        provider_name: Name of the provider to unregister

    Returns:
        bool: True if provider was unregistered
    """
    return get_global_registry().unregister_provider(provider_name)


def find_providers(query: DataQuery) -> list[DataProvider]:
    """
    Find providers that can handle the given query.

    Args:
        query: The data query to match against

    Returns:
        List of compatible providers
    """
    return get_global_registry().find_providers(query)
