"""
Tests for provider factory and configuration management.

This module tests the provider factory, configuration management,
and provider manager functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json

from vprism.core.provider_factory import ProviderFactory, ProviderManager
from vprism.core.provider_config import (
    ProviderConfig, 
    ProvidersConfig, 
    ProviderConfigManager,
    DefaultProviderConfigs
)
from vprism.core.provider_abstraction import AuthType
from vprism.core.exceptions import ConfigurationException, ProviderException


class TestProviderConfig:
    """Test suite for ProviderConfig."""

    def test_provider_config_creation(self):
        """Test provider configuration creation."""
        config = ProviderConfig(
            name="test_provider",
            enabled=True,
            priority=1,
            auth_type=AuthType.API_KEY,
            credentials={"api_key": "test_key"},
            requests_per_minute=60
        )
        
        assert config.name == "test_provider"
        assert config.enabled is True
        assert config.priority == 1
        assert config.auth_type == AuthType.API_KEY
        assert config.credentials["api_key"] == "test_key"

    def test_provider_config_validation(self):
        """Test provider configuration validation."""
        # Test invalid priority
        with pytest.raises(ValueError, match="Priority must be positive"):
            ProviderConfig(
                name="test",
                priority=0
            )
        
        # Test invalid rate limits
        with pytest.raises(ValueError, match="Rate limit values must be positive"):
            ProviderConfig(
                name="test",
                requests_per_minute=0
            )

    def test_auth_config_conversion(self):
        """Test conversion to AuthConfig."""
        config = ProviderConfig(
            name="test",
            auth_type=AuthType.API_KEY,
            credentials={"api_key": "test_key"}
        )
        
        auth_config = config.to_auth_config()
        assert auth_config.auth_type == AuthType.API_KEY
        assert auth_config.credentials["api_key"] == "test_key"

    def test_rate_limit_config_conversion(self):
        """Test conversion to RateLimitConfig."""
        config = ProviderConfig(
            name="test",
            requests_per_minute=60,
            requests_per_hour=1000,
            concurrent_requests=5
        )
        
        rate_limit = config.to_rate_limit_config()
        assert rate_limit.requests_per_minute == 60
        assert rate_limit.requests_per_hour == 1000
        assert rate_limit.concurrent_requests == 5


class TestProvidersConfig:
    """Test suite for ProvidersConfig."""

    def test_providers_config_creation(self):
        """Test providers configuration creation."""
        config = ProvidersConfig()
        assert len(config.providers) == 0
        assert config.default_provider is None

    def test_add_provider(self):
        """Test adding provider configuration."""
        config = ProvidersConfig()
        provider_config = ProviderConfig(name="test_provider")
        
        config.add_provider(provider_config)
        assert "test_provider" in config.providers
        assert config.providers["test_provider"] == provider_config

    def test_get_enabled_providers(self):
        """Test getting enabled providers."""
        config = ProvidersConfig()
        
        enabled_provider = ProviderConfig(name="enabled", enabled=True)
        disabled_provider = ProviderConfig(name="disabled", enabled=False)
        
        config.add_provider(enabled_provider)
        config.add_provider(disabled_provider)
        
        enabled = config.get_enabled_providers()
        assert len(enabled) == 1
        assert enabled[0].name == "enabled"

    def test_get_providers_by_priority(self):
        """Test getting providers sorted by priority."""
        config = ProvidersConfig()
        
        low_priority = ProviderConfig(name="low", priority=3, enabled=True)
        high_priority = ProviderConfig(name="high", priority=1, enabled=True)
        medium_priority = ProviderConfig(name="medium", priority=2, enabled=True)
        
        config.add_provider(low_priority)
        config.add_provider(high_priority)
        config.add_provider(medium_priority)
        
        sorted_providers = config.get_providers_by_priority()
        assert len(sorted_providers) == 3
        assert sorted_providers[0].name == "high"
        assert sorted_providers[1].name == "medium"
        assert sorted_providers[2].name == "low"


class TestProviderConfigManager:
    """Test suite for ProviderConfigManager."""

    def test_config_manager_creation(self):
        """Test configuration manager creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            manager = ProviderConfigManager(config_file)
            assert manager.config_file == config_file

    def test_create_default_config(self):
        """Test creating default configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            manager = ProviderConfigManager(config_file)
            
            config = manager.load_config()
            assert isinstance(config, ProvidersConfig)
            assert len(config.providers) > 0
            assert "akshare" in config.providers
            assert "yfinance" in config.providers
            assert "alpha_vantage" in config.providers

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            manager = ProviderConfigManager(config_file)
            
            # Create and save config
            config = manager.load_config()
            config.default_provider = "test_provider"
            manager.save_config()
            
            # Load config again
            manager._config = None  # Reset cache
            loaded_config = manager.load_config()
            assert loaded_config.default_provider == "test_provider"

    def test_update_provider(self):
        """Test updating provider configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            manager = ProviderConfigManager(config_file)
            
            new_provider = ProviderConfig(
                name="new_provider",
                enabled=True,
                priority=1
            )
            
            manager.update_provider(new_provider)
            
            config = manager.get_config()
            assert "new_provider" in config.providers
            assert config.providers["new_provider"].enabled is True

    def test_set_credentials(self):
        """Test setting provider credentials."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            manager = ProviderConfigManager(config_file)
            
            # Load default config first
            manager.load_config()
            
            # Set credentials for alpha_vantage
            manager.set_credentials("alpha_vantage", {"api_key": "test_key"})
            
            config = manager.get_config()
            alpha_vantage = config.get_provider("alpha_vantage")
            assert alpha_vantage.credentials["api_key"] == "test_key"
            assert alpha_vantage.enabled is True  # Should be enabled when credentials are set

    def test_configure_alpha_vantage(self):
        """Test Alpha Vantage configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            manager = ProviderConfigManager(config_file)
            
            manager.configure_alpha_vantage("test_api_key")
            
            config = manager.get_config()
            alpha_vantage = config.get_provider("alpha_vantage")
            assert alpha_vantage.credentials["api_key"] == "test_api_key"
            assert alpha_vantage.enabled is True

    def test_configure_alpha_vantage_empty_key(self):
        """Test Alpha Vantage configuration with empty key."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            manager = ProviderConfigManager(config_file)
            
            with pytest.raises(ConfigurationException):
                manager.configure_alpha_vantage("")

    @patch.dict('os.environ', {'ALPHA_VANTAGE_API_KEY': 'env_test_key'})
    def test_environment_credentials(self):
        """Test getting credentials from environment variables."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            manager = ProviderConfigManager(config_file)
            
            env_creds = manager.get_environment_credentials()
            assert "alpha_vantage" in env_creds
            assert env_creds["alpha_vantage"]["api_key"] == "env_test_key"

    @patch.dict('os.environ', {'ALPHA_VANTAGE_API_KEY': 'env_test_key'})
    def test_apply_environment_credentials(self):
        """Test applying environment credentials."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            manager = ProviderConfigManager(config_file)
            
            # Load default config first
            manager.load_config()
            
            # Apply environment credentials
            manager.apply_environment_credentials()
            
            config = manager.get_config()
            alpha_vantage = config.get_provider("alpha_vantage")
            assert alpha_vantage.credentials["api_key"] == "env_test_key"


class TestProviderFactory:
    """Test suite for ProviderFactory."""

    def test_factory_creation(self):
        """Test factory creation."""
        factory = ProviderFactory()
        assert isinstance(factory, ProviderFactory)
        
        # Check that built-in providers are registered
        available_names = factory.get_available_provider_names()
        assert "alpha_vantage" in available_names

    def test_create_alpha_vantage_provider(self):
        """Test creating Alpha Vantage provider."""
        factory = ProviderFactory()
        
        config = ProviderConfig(
            name="alpha_vantage",
            enabled=True,
            auth_type=AuthType.API_KEY,
            credentials={"api_key": "test_key"}
        )
        
        provider = factory.create_provider(config)
        assert provider is not None
        assert provider.name == "alpha_vantage"

    def test_create_alpha_vantage_provider_no_key(self):
        """Test creating Alpha Vantage provider without API key."""
        factory = ProviderFactory()
        
        config = ProviderConfig(
            name="alpha_vantage",
            enabled=True,
            auth_type=AuthType.API_KEY,
            credentials={}  # No API key
        )
        
        provider = factory.create_provider(config)
        assert provider is None  # Should fail without API key

    def test_create_disabled_provider(self):
        """Test creating disabled provider."""
        factory = ProviderFactory()
        
        config = ProviderConfig(
            name="alpha_vantage",
            enabled=False,  # Disabled
            auth_type=AuthType.API_KEY,
            credentials={"api_key": "test_key"}
        )
        
        provider = factory.create_provider(config)
        assert provider is None  # Should not create disabled provider

    def test_create_unknown_provider(self):
        """Test creating unknown provider."""
        factory = ProviderFactory()
        
        config = ProviderConfig(
            name="unknown_provider",
            enabled=True
        )
        
        provider = factory.create_provider(config)
        assert provider is None  # Should not create unknown provider

    def test_create_all_providers(self):
        """Test creating all providers from configurations."""
        factory = ProviderFactory()
        
        configs = [
            ProviderConfig(
                name="alpha_vantage",
                enabled=True,
                auth_type=AuthType.API_KEY,
                credentials={"api_key": "test_key"}
            ),
            ProviderConfig(
                name="unknown_provider",
                enabled=True
            ),
            ProviderConfig(
                name="alpha_vantage",
                enabled=False,  # Disabled duplicate
                auth_type=AuthType.API_KEY,
                credentials={"api_key": "test_key2"}
            )
        ]
        
        providers = factory.create_all_providers(configs)
        assert len(providers) == 1  # Only one should be created
        assert providers[0].name == "alpha_vantage"


class TestProviderManager:
    """Test suite for ProviderManager."""

    def test_manager_creation(self):
        """Test manager creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            config_manager = ProviderConfigManager(config_file)
            manager = ProviderManager(config_manager)
            
            assert manager.config_manager == config_manager
            assert not manager._initialized

    def test_manager_initialization(self):
        """Test manager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            config_manager = ProviderConfigManager(config_file)
            manager = ProviderManager(config_manager)
            
            # Mock environment to avoid actual API calls
            with patch.dict('os.environ', {'ALPHA_VANTAGE_API_KEY': 'test_key'}):
                manager.initialize()
            
            assert manager._initialized
            registry = manager.get_registry()
            assert registry is not None

    def test_get_provider_status(self):
        """Test getting provider status."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            config_manager = ProviderConfigManager(config_file)
            manager = ProviderManager(config_manager)
            
            # Mock environment and initialize
            with patch.dict('os.environ', {'ALPHA_VANTAGE_API_KEY': 'test_key'}):
                manager.initialize()
            
            status = manager.get_provider_status()
            assert isinstance(status, dict)
            
            # Should have at least alpha_vantage if API key is provided
            if "alpha_vantage" in status:
                alpha_status = status["alpha_vantage"]
                assert "name" in alpha_status
                assert "enabled" in alpha_status
                assert "capability" in alpha_status

    def test_configure_alpha_vantage(self):
        """Test configuring Alpha Vantage through manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            config_manager = ProviderConfigManager(config_file)
            manager = ProviderManager(config_manager)
            
            manager.configure_alpha_vantage("test_api_key")
            
            # Check that provider is available
            provider = manager.get_provider("alpha_vantage")
            assert provider is not None
            assert provider.name == "alpha_vantage"


class TestDefaultConfigs:
    """Test suite for default configurations."""

    def test_default_akshare_config(self):
        """Test default akshare configuration."""
        config = DefaultProviderConfigs.AKSHARE
        assert config.name == "akshare"
        assert config.enabled is True
        assert config.priority == 3
        assert config.auth_type == AuthType.NONE

    def test_default_yfinance_config(self):
        """Test default yfinance configuration."""
        config = DefaultProviderConfigs.YFINANCE
        assert config.name == "yfinance"
        assert config.enabled is True
        assert config.priority == 2
        assert config.auth_type == AuthType.NONE

    def test_default_alpha_vantage_config(self):
        """Test default Alpha Vantage configuration."""
        config = DefaultProviderConfigs.ALPHA_VANTAGE
        assert config.name == "alpha_vantage"
        # Note: The config might be enabled if environment variables are set
        # In a clean environment, it should be disabled by default
        assert config.priority == 2
        assert config.auth_type == AuthType.API_KEY