"""
Provider factory for creating and managing data provider instances.

This module provides factory functions to create data provider instances
based on configuration, with proper dependency injection and error handling.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from vprism.core.exceptions import ConfigurationException, ProviderException
from vprism.core.provider_abstraction import EnhancedDataProvider, EnhancedProviderRegistry
from vprism.core.provider_config import ProviderConfig, ProviderConfigManager

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory for creating data provider instances."""
    
    def __init__(self):
        """Initialize provider factory."""
        self._provider_classes: Dict[str, Type[EnhancedDataProvider]] = {}
        self._register_built_in_providers()
    
    def _register_built_in_providers(self) -> None:
        """Register built-in provider classes."""
        try:
            from vprism.core.providers.akshare_provider import AkshareProvider
            self._provider_classes["akshare"] = AkshareProvider
        except ImportError:
            logger.warning("AkshareProvider not available - akshare dependency missing")
        
        try:
            from vprism.core.providers.yfinance_provider import YfinanceProvider
            self._provider_classes["yfinance"] = YfinanceProvider
        except ImportError:
            logger.warning("YfinanceProvider not available - yfinance dependency missing")
        
        try:
            from vprism.core.providers.alpha_vantage_provider import AlphaVantageProvider
            self._provider_classes["alpha_vantage"] = AlphaVantageProvider
        except ImportError:
            logger.warning("AlphaVantageProvider not available")
    
    def register_provider_class(self, name: str, provider_class: Type[EnhancedDataProvider]) -> None:
        """Register a custom provider class."""
        if not issubclass(provider_class, EnhancedDataProvider):
            raise ConfigurationException(
                f"Provider class {provider_class.__name__} must inherit from EnhancedDataProvider",
                config_key="provider_class"
            )
        
        self._provider_classes[name] = provider_class
        logger.info(f"Registered custom provider class: {name}")
    
    def create_provider(self, config: ProviderConfig) -> Optional[EnhancedDataProvider]:
        """Create a provider instance from configuration."""
        if not config.enabled:
            logger.debug(f"Provider {config.name} is disabled, skipping creation")
            return None
        
        provider_class = self._provider_classes.get(config.name)
        if not provider_class:
            logger.warning(f"Provider class not found for: {config.name}")
            return None
        
        try:
            # Create provider instance based on type
            if config.name == "akshare":
                return self._create_akshare_provider(config)
            elif config.name == "yfinance":
                return self._create_yfinance_provider(config)
            elif config.name == "alpha_vantage":
                return self._create_alpha_vantage_provider(config)
            else:
                # Generic provider creation
                return self._create_generic_provider(provider_class, config)
                
        except Exception as e:
            logger.error(f"Failed to create provider {config.name}: {e}")
            return None
    
    def _create_akshare_provider(self, config: ProviderConfig) -> Optional[EnhancedDataProvider]:
        """Create akshare provider instance."""
        try:
            from vprism.core.providers.akshare_provider import AkshareProvider
            return AkshareProvider()
        except ImportError:
            logger.warning("Cannot create AkshareProvider - akshare dependency missing")
            return None
        except Exception as e:
            logger.error(f"Failed to create AkshareProvider: {e}")
            return None
    
    def _create_yfinance_provider(self, config: ProviderConfig) -> Optional[EnhancedDataProvider]:
        """Create yfinance provider instance."""
        try:
            from vprism.core.providers.yfinance_provider import YfinanceProvider
            return YfinanceProvider()
        except ImportError:
            logger.warning("Cannot create YfinanceProvider - yfinance dependency missing")
            return None
        except Exception as e:
            logger.error(f"Failed to create YfinanceProvider: {e}")
            return None
    
    def _create_alpha_vantage_provider(self, config: ProviderConfig) -> Optional[EnhancedDataProvider]:
        """Create Alpha Vantage provider instance."""
        try:
            from vprism.core.providers.alpha_vantage_provider import AlphaVantageProvider
            
            # Validate API key
            api_key = config.credentials.get("api_key")
            if not api_key:
                logger.warning("Alpha Vantage provider requires API key")
                return None
            
            return AlphaVantageProvider(api_key=api_key)
        except ImportError:
            logger.warning("Cannot create AlphaVantageProvider")
            return None
        except Exception as e:
            logger.error(f"Failed to create AlphaVantageProvider: {e}")
            return None
    
    def _create_generic_provider(
        self, 
        provider_class: Type[EnhancedDataProvider], 
        config: ProviderConfig
    ) -> Optional[EnhancedDataProvider]:
        """Create a generic provider instance."""
        try:
            # Try to create with configuration
            auth_config = config.to_auth_config()
            rate_limit = config.to_rate_limit_config()
            
            return provider_class(
                provider_name=config.name,
                auth_config=auth_config,
                rate_limit=rate_limit
            )
        except Exception as e:
            logger.error(f"Failed to create generic provider {config.name}: {e}")
            return None
    
    def create_all_providers(self, configs: List[ProviderConfig]) -> List[EnhancedDataProvider]:
        """Create all provider instances from configurations."""
        providers = []
        
        for config in configs:
            provider = self.create_provider(config)
            if provider:
                providers.append(provider)
        
        logger.info(f"Created {len(providers)} provider instances")
        return providers
    
    def get_available_provider_names(self) -> List[str]:
        """Get list of available provider names."""
        return list(self._provider_classes.keys())


class ProviderManager:
    """High-level manager for provider lifecycle and registry."""
    
    def __init__(self, config_manager: Optional[ProviderConfigManager] = None):
        """Initialize provider manager."""
        self.config_manager = config_manager or ProviderConfigManager()
        self.factory = ProviderFactory()
        self.registry = EnhancedProviderRegistry()
        self._initialized = False
    
    def initialize(self) -> None:
        """Initialize providers from configuration."""
        if self._initialized:
            return
        
        try:
            # Load configuration
            config = self.config_manager.get_config()
            
            # Apply environment credentials
            self.config_manager.apply_environment_credentials()
            
            # Create and register providers
            enabled_configs = config.get_providers_by_priority()
            providers = self.factory.create_all_providers(enabled_configs)
            
            for provider in providers:
                self.registry.register_provider(provider)
            
            self._initialized = True
            logger.info(f"Initialized provider manager with {len(providers)} providers")
            
        except Exception as e:
            logger.error(f"Failed to initialize provider manager: {e}")
            raise ConfigurationException(
                f"Provider manager initialization failed: {e}",
                config_key="provider_manager"
            )
    
    def get_registry(self) -> EnhancedProviderRegistry:
        """Get the provider registry."""
        if not self._initialized:
            self.initialize()
        return self.registry
    
    def get_provider(self, name: str) -> Optional[EnhancedDataProvider]:
        """Get a specific provider by name."""
        if not self._initialized:
            self.initialize()
        
        providers = self.registry.get_all_providers()
        return providers.get(name)
    
    def get_enabled_providers(self) -> List[EnhancedDataProvider]:
        """Get all enabled providers."""
        if not self._initialized:
            self.initialize()
        
        return self.registry.get_healthy_providers()
    
    def reload_providers(self) -> None:
        """Reload providers from configuration."""
        logger.info("Reloading providers...")
        
        # Clear existing providers
        for provider_name in list(self.registry.get_all_providers().keys()):
            self.registry.unregister_provider(provider_name)
        
        # Reinitialize
        self._initialized = False
        self.initialize()
    
    def add_provider_credentials(self, provider_name: str, credentials: Dict[str, str]) -> None:
        """Add credentials for a provider and reload if necessary."""
        self.config_manager.set_credentials(provider_name, credentials)
        
        # If provider is currently disabled, reload to enable it
        current_provider = self.get_provider(provider_name)
        if not current_provider:
            self.reload_providers()
    
    def configure_alpha_vantage(self, api_key: str) -> None:
        """Configure Alpha Vantage provider."""
        self.config_manager.configure_alpha_vantage(api_key)
        self.reload_providers()
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Perform health check on all providers."""
        if not self._initialized:
            self.initialize()
        
        return await self.registry.check_all_provider_health()
    
    def get_provider_status(self) -> Dict[str, Dict[str, any]]:
        """Get status information for all providers."""
        if not self._initialized:
            self.initialize()
        
        status = {}
        all_providers = self.registry.get_all_providers()
        
        for name, provider in all_providers.items():
            status[name] = {
                "name": provider.name,
                "enabled": True,  # If it's in registry, it's enabled
                "healthy": self.registry._provider_health.get(name, False),
                "score": self.registry.get_provider_score(name),
                "capability": {
                    "supported_assets": list(provider.capability.supported_assets),
                    "supported_markets": list(provider.capability.supported_markets),
                    "supports_real_time": provider.capability.supports_real_time,
                    "supports_historical": provider.capability.supports_historical,
                }
            }
        
        return status


# Global provider manager instance
_provider_manager: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    """Get the global provider manager instance."""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = ProviderManager()
    return _provider_manager


def create_provider_manager(config_manager: Optional[ProviderConfigManager] = None) -> ProviderManager:
    """Factory function to create a provider manager."""
    return ProviderManager(config_manager)


def initialize_providers() -> None:
    """Initialize the global provider manager."""
    manager = get_provider_manager()
    manager.initialize()


def get_provider_registry() -> EnhancedProviderRegistry:
    """Get the global provider registry."""
    manager = get_provider_manager()
    return manager.get_registry()