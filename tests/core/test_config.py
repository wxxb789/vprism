"""
Tests for configuration management.

This module contains comprehensive tests for the configuration system,
ensuring proper loading, saving, and validation of configuration data.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import toml

from vprism.core.config import (
    CacheConfig,
    ConfigManager,
    DatabaseConfig,
    LoggingConfig,
    ProviderConfig,
    SecurityConfig,
    VPrismConfig,
    get_config,
    get_config_manager,
)


class TestProviderConfig:
    """Test ProviderConfig model."""

    def test_provider_config_creation(self):
        """Test creating a provider configuration."""
        config = ProviderConfig(
            name="test_provider",
            enabled=True,
            api_key="test_key",
            base_url="https://api.example.com",
            rate_limit=1000,
            timeout=30.0,
            retry_attempts=3,
            priority=100,
        )

        assert config.name == "test_provider"
        assert config.enabled is True
        assert config.api_key == "test_key"
        assert config.base_url == "https://api.example.com"
        assert config.rate_limit == 1000
        assert config.timeout == 30.0
        assert config.retry_attempts == 3
        assert config.priority == 100
        assert config.extra_config == {}

    def test_provider_config_defaults(self):
        """Test provider configuration defaults."""
        config = ProviderConfig(name="test_provider")

        assert config.name == "test_provider"
        assert config.enabled is True
        assert config.api_key is None
        assert config.base_url is None
        assert config.rate_limit is None
        assert config.timeout == 30.0
        assert config.retry_attempts == 3
        assert config.priority == 100
        assert config.extra_config == {}

    def test_provider_config_with_extra_config(self):
        """Test provider configuration with extra config."""
        extra_config = {"custom_param": "value", "debug": True}
        config = ProviderConfig(name="test_provider", extra_config=extra_config)

        assert config.extra_config == extra_config


class TestCacheConfig:
    """Test CacheConfig model."""

    def test_cache_config_defaults(self):
        """Test cache configuration defaults."""
        config = CacheConfig()

        assert config.enabled is True
        assert config.backend == "memory"
        assert config.redis_url is None
        assert config.default_ttl == 3600
        assert config.max_size == 1000
        assert config.file_cache_dir is None

    def test_cache_config_custom_values(self):
        """Test cache configuration with custom values."""
        config = CacheConfig(
            enabled=False,
            backend="redis",
            redis_url="redis://localhost:6379",
            default_ttl=7200,
            max_size=5000,
        )

        assert config.enabled is False
        assert config.backend == "redis"
        assert config.redis_url == "redis://localhost:6379"
        assert config.default_ttl == 7200
        assert config.max_size == 5000


class TestDatabaseConfig:
    """Test DatabaseConfig model."""

    def test_database_config_defaults(self):
        """Test database configuration defaults."""
        config = DatabaseConfig()

        assert config.enabled is False
        assert config.backend == "duckdb"
        assert config.connection_string is None
        assert config.auto_create_tables is True
        assert config.batch_size == 1000


class TestLoggingConfig:
    """Test LoggingConfig model."""

    def test_logging_config_defaults(self):
        """Test logging configuration defaults."""
        config = LoggingConfig()

        assert config.level == "INFO"
        assert "{time:" in config.format
        assert config.file_path is None
        assert config.rotation == "1 day"
        assert config.retention == "30 days"
        assert config.structured is True


class TestSecurityConfig:
    """Test SecurityConfig model."""

    def test_security_config_defaults(self):
        """Test security configuration defaults."""
        config = SecurityConfig()

        assert config.encryption_key is None
        assert config.api_key_encryption is True
        assert config.rate_limiting is True
        assert config.max_requests_per_minute == 1000


class TestVPrismConfig:
    """Test VPrismConfig model."""

    def test_vprism_config_defaults(self):
        """Test VPrism configuration defaults."""
        config = VPrismConfig()

        assert config.debug is False
        assert config.environment == "production"
        assert isinstance(config.cache, CacheConfig)
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.security, SecurityConfig)
        assert config.providers == {}
        assert config.max_concurrent_requests == 100
        assert config.request_timeout == 30.0
        assert config.enable_streaming is True
        assert config.enable_caching is True
        assert config.enable_metrics is True

    def test_vprism_config_with_custom_values(self):
        """Test VPrism configuration with custom values."""
        config = VPrismConfig(
            debug=True,
            environment="development",
            max_concurrent_requests=200,
            request_timeout=60.0,
        )

        assert config.debug is True
        assert config.environment == "development"
        assert config.max_concurrent_requests == 200
        assert config.request_timeout == 60.0

    def test_load_from_file(self):
        """Test loading configuration from file."""
        config_data = {
            "debug": True,
            "environment": "development",
            "max_concurrent_requests": 200,
            "providers": {
                "test_provider": {
                    "name": "test_provider",
                    "enabled": True,
                    "api_key": "test_key",
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            toml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = VPrismConfig.load_from_file(config_path)

            assert config.debug is True
            assert config.environment == "development"
            assert config.max_concurrent_requests == 200
            assert "test_provider" in config.providers
            assert config.providers["test_provider"].name == "test_provider"
            assert config.providers["test_provider"].enabled is True
            assert config.providers["test_provider"].api_key == "test_key"
        finally:
            config_path.unlink()

    def test_load_from_nonexistent_file(self):
        """Test loading from nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            VPrismConfig.load_from_file(Path("/nonexistent/config.toml"))

    def test_save_to_file(self):
        """Test saving configuration to file."""
        config = VPrismConfig(debug=True, environment="test")

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config.save_to_file(config_path)

            assert config_path.exists()

            # Load and verify
            loaded_data = toml.load(config_path)
            assert loaded_data["debug"] is True
            assert loaded_data["environment"] == "test"

    def test_get_provider_config(self):
        """Test getting provider configuration."""
        provider_config = ProviderConfig(name="test_provider", enabled=True)
        config = VPrismConfig()
        config.add_provider_config(provider_config)

        retrieved_config = config.get_provider_config("test_provider")
        assert retrieved_config is not None
        assert retrieved_config.name == "test_provider"
        assert retrieved_config.enabled is True

        # Test nonexistent provider
        assert config.get_provider_config("nonexistent") is None

    def test_add_provider_config(self):
        """Test adding provider configuration."""
        config = VPrismConfig()
        provider_config = ProviderConfig(name="test_provider", enabled=True)

        config.add_provider_config(provider_config)

        assert "test_provider" in config.providers
        assert config.providers["test_provider"] == provider_config

    def test_remove_provider_config(self):
        """Test removing provider configuration."""
        config = VPrismConfig()
        provider_config = ProviderConfig(name="test_provider", enabled=True)
        config.add_provider_config(provider_config)

        # Remove existing provider
        assert config.remove_provider_config("test_provider") is True
        assert "test_provider" not in config.providers

        # Remove nonexistent provider
        assert config.remove_provider_config("nonexistent") is False

    def test_get_enabled_providers(self):
        """Test getting enabled providers."""
        config = VPrismConfig()

        # Add enabled provider
        enabled_provider = ProviderConfig(name="enabled_provider", enabled=True)
        config.add_provider_config(enabled_provider)

        # Add disabled provider
        disabled_provider = ProviderConfig(name="disabled_provider", enabled=False)
        config.add_provider_config(disabled_provider)

        enabled_providers = config.get_enabled_providers()

        assert len(enabled_providers) == 1
        assert "enabled_provider" in enabled_providers
        assert "disabled_provider" not in enabled_providers


class TestConfigManager:
    """Test ConfigManager class."""

    def test_config_manager_initialization(self):
        """Test config manager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            manager = ConfigManager(config_path)

            assert manager.config_path == config_path
            assert manager._config is None

    def test_config_manager_default_path(self):
        """Test config manager with default path."""
        manager = ConfigManager()

        # Should create a default path
        assert manager.config_path is not None
        assert manager.config_path.name == "config.toml"

    def test_load_config_creates_default(self):
        """Test loading config creates default when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            manager = ConfigManager(config_path)

            config = manager.load_config()

            assert isinstance(config, VPrismConfig)
            assert config.debug is False
            assert config.environment == "production"
            assert config_path.exists()  # Should be created

    def test_load_config_from_existing_file(self):
        """Test loading config from existing file."""
        config_data = {"debug": True, "environment": "test"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            toml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            manager = ConfigManager(config_path)
            config = manager.load_config()

            assert config.debug is True
            assert config.environment == "test"
        finally:
            config_path.unlink()

    def test_save_config(self):
        """Test saving configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            manager = ConfigManager(config_path)

            # Load default config
            config = manager.load_config()
            config.debug = True
            config.environment = "test"

            # Save config
            manager.save_config()

            # Verify file was updated
            loaded_data = toml.load(config_path)
            assert loaded_data["debug"] is True
            assert loaded_data["environment"] == "test"

    def test_update_config(self):
        """Test updating configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            manager = ConfigManager(config_path)

            # Update config
            manager.update_config(debug=True, environment="test")

            # Verify updates
            config = manager.config
            assert config.debug is True
            assert config.environment == "test"

            # Verify file was saved
            loaded_data = toml.load(config_path)
            assert loaded_data["debug"] is True
            assert loaded_data["environment"] == "test"

    def test_reset_config(self):
        """Test resetting configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            manager = ConfigManager(config_path)

            # Set some custom values
            manager.update_config(debug=True, environment="test")
            assert manager.config.debug is True

            # Reset config
            manager.reset_config()

            # Verify reset to defaults
            config = manager.config
            assert config.debug is False
            assert config.environment == "production"

    def test_config_property_lazy_loading(self):
        """Test that config property loads configuration lazily."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            manager = ConfigManager(config_path)

            # Config should not be loaded initially
            assert manager._config is None

            # Accessing config property should load it
            config = manager.config
            assert manager._config is not None
            assert isinstance(config, VPrismConfig)

    def test_config_loading_error_handling(self):
        """Test config loading error handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            manager = ConfigManager(config_path)

            # Create an invalid TOML file
            config_path.write_text("invalid toml content [[[")

            # Should handle the error gracefully and use default config
            with patch("builtins.print") as mock_print:
                config = manager.config
                assert config is not None
                assert isinstance(config, VPrismConfig)
                # Should have printed warning messages
                assert mock_print.call_count >= 2


class TestGlobalConfigManager:
    """Test global configuration manager functions."""

    def test_get_config_manager_singleton(self):
        """Test that get_config_manager returns singleton."""
        manager1 = get_config_manager()
        manager2 = get_config_manager()

        assert manager1 is manager2

    def test_get_config(self):
        """Test get_config function."""
        config = get_config()

        assert isinstance(config, VPrismConfig)

    @patch("vprism.core.config._config_manager", None)
    def test_get_config_manager_creates_new_instance(self):
        """Test that get_config_manager creates new instance when needed."""
        # Reset global manager
        import vprism.core.config

        vprism.core.config._config_manager = None

        manager = get_config_manager()
        assert isinstance(manager, ConfigManager)


class TestConfigIntegration:
    """Integration tests for configuration system."""

    def test_full_config_workflow(self):
        """Test complete configuration workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            manager = ConfigManager(config_path)

            # Load default config
            config = manager.load_config()
            assert config.debug is False

            # Add provider
            provider_config = ProviderConfig(
                name="test_provider",
                enabled=True,
                api_key="test_key",
                rate_limit=1000,
            )
            config.add_provider_config(provider_config)

            # Update other settings
            manager.update_config(debug=True, environment="development")

            # Verify all changes
            updated_config = manager.config
            assert updated_config.debug is True
            assert updated_config.environment == "development"
            assert "test_provider" in updated_config.providers
            assert updated_config.providers["test_provider"].api_key == "test_key"

            # Create new manager with same path
            new_manager = ConfigManager(config_path)
            loaded_config = new_manager.load_config()

            # Verify persistence
            assert loaded_config.debug is True
            assert loaded_config.environment == "development"
            assert "test_provider" in loaded_config.providers
            assert loaded_config.providers["test_provider"].api_key == "test_key"
