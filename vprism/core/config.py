"""
Configuration management for vprism.

This module provides centralized configuration management with support for
environment variables, configuration files, and runtime configuration.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import toml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderConfig(BaseModel):
    """Configuration for a data provider."""

    name: str = Field(..., description="Provider name")
    enabled: bool = Field(True, description="Whether provider is enabled")
    api_key: str | None = Field(None, description="API key for provider")
    base_url: str | None = Field(None, description="Base URL for provider API")
    rate_limit: int | None = Field(None, description="Rate limit per minute")
    timeout: float = Field(30.0, description="Request timeout in seconds")
    retry_attempts: int = Field(3, description="Number of retry attempts")
    priority: int = Field(
        100, description="Provider priority (lower = higher priority)"
    )
    extra_config: dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific config"
    )


class CacheConfig(BaseModel):
    """Configuration for caching."""

    enabled: bool = Field(True, description="Whether caching is enabled")
    backend: str = Field("memory", description="Cache backend (memory, redis, file)")
    redis_url: str | None = Field(None, description="Redis connection URL")
    default_ttl: int = Field(3600, description="Default TTL in seconds")
    max_size: int = Field(1000, description="Maximum cache size")
    file_cache_dir: Path | None = Field(None, description="File cache directory")


class DatabaseConfig(BaseModel):
    """Configuration for database storage."""

    enabled: bool = Field(False, description="Whether database storage is enabled")
    backend: str = Field(
        "duckdb", description="Database backend (duckdb, sqlite, postgresql)"
    )
    connection_string: str | None = Field(
        None, description="Database connection string"
    )
    auto_create_tables: bool = Field(True, description="Auto-create database tables")
    batch_size: int = Field(1000, description="Batch size for bulk operations")


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: str = Field("INFO", description="Log level")
    format: str = Field(
        "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        description="Log format",
    )
    file_path: Path | None = Field(None, description="Log file path")
    rotation: str = Field("1 day", description="Log rotation interval")
    retention: str = Field("30 days", description="Log retention period")
    structured: bool = Field(True, description="Use structured logging")


class SecurityConfig(BaseModel):
    """Configuration for security settings."""

    encryption_key: str | None = Field(
        None, description="Encryption key for sensitive data"
    )
    api_key_encryption: bool = Field(True, description="Encrypt API keys in storage")
    rate_limiting: bool = Field(True, description="Enable rate limiting")
    max_requests_per_minute: int = Field(
        1000, description="Max requests per minute per client"
    )


class VPrismConfig(BaseSettings):
    """Main vprism configuration."""

    model_config = SettingsConfigDict(
        env_prefix="VPRISM_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )

    # Core settings
    debug: bool = Field(False, description="Enable debug mode")
    environment: str = Field(
        "production", description="Environment (development, staging, production)"
    )

    # Component configurations
    cache: CacheConfig = Field(
        default_factory=lambda: CacheConfig(), description="Cache configuration"
    )
    database: DatabaseConfig = Field(
        default_factory=lambda: DatabaseConfig(), description="Database configuration"
    )
    logging: LoggingConfig = Field(
        default_factory=lambda: LoggingConfig(), description="Logging configuration"
    )
    security: SecurityConfig = Field(
        default_factory=lambda: SecurityConfig(), description="Security configuration"
    )

    # Provider configurations
    providers: dict[str, ProviderConfig] = Field(
        default_factory=dict, description="Provider configurations"
    )

    # Performance settings
    max_concurrent_requests: int = Field(100, description="Maximum concurrent requests")
    request_timeout: float = Field(30.0, description="Default request timeout")

    # Feature flags
    enable_streaming: bool = Field(True, description="Enable real-time streaming")
    enable_caching: bool = Field(True, description="Enable caching")
    enable_metrics: bool = Field(True, description="Enable metrics collection")

    @classmethod
    def load_from_file(cls, config_path: Path) -> VPrismConfig:
        """Load configuration from a TOML file."""
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        config_data = toml.load(config_path)
        return cls(**config_data)

    def save_to_file(self, config_path: Path) -> None:
        """Save configuration to a TOML file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            toml.dump(self.model_dump(), f)

    def get_provider_config(self, provider_name: str) -> ProviderConfig | None:
        """Get configuration for a specific provider."""
        return self.providers.get(provider_name)

    def add_provider_config(self, provider_config: ProviderConfig) -> None:
        """Add or update provider configuration."""
        self.providers[provider_config.name] = provider_config

    def remove_provider_config(self, provider_name: str) -> bool:
        """Remove provider configuration."""
        if provider_name in self.providers:
            del self.providers[provider_name]
            return True
        return False

    def get_enabled_providers(self) -> dict[str, ProviderConfig]:
        """Get all enabled provider configurations."""
        return {
            name: config for name, config in self.providers.items() if config.enabled
        }


class ConfigManager:
    """Configuration manager for vprism."""

    def __init__(self, config_path: Path | None = None):
        """Initialize configuration manager."""
        self.config_path = config_path or self._get_default_config_path()
        self._config: VPrismConfig | None = None

    def _get_default_config_path(self) -> Path:
        """Get default configuration file path."""
        # Try user config directory first
        config_dir = Path.home() / ".config" / "vprism"
        if os.name == "nt":  # Windows
            config_dir = Path.home() / "AppData" / "Local" / "vprism"

        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.toml"

    @property
    def config(self) -> VPrismConfig:
        """Get current configuration."""
        if self._config is None:
            self.load_config()
        return self._config

    def load_config(self) -> VPrismConfig:
        """Load configuration from file or create default."""
        try:
            if self.config_path.exists():
                self._config = VPrismConfig.load_from_file(self.config_path)
            else:
                self._config = VPrismConfig()
                self.save_config()
        except Exception as e:
            # If loading fails, use default config
            self._config = VPrismConfig()
            print(f"Warning: Failed to load config from {self.config_path}: {e}")
            print("Using default configuration")
        return self._config

        return self._config

    def save_config(self) -> None:
        """Save current configuration to file."""
        if self._config is not None:
            self._config.save_to_file(self.config_path)

    def update_config(self, **kwargs: Any) -> None:
        """Update configuration with new values."""
        if self._config is None:
            self.load_config()

        # Update configuration
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

        self.save_config()

    def reset_config(self) -> None:
        """Reset configuration to defaults."""
        self._config = VPrismConfig()
        self.save_config()


# Global configuration manager instance
_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> VPrismConfig:
    """Get current configuration."""
    return get_config_manager().config
