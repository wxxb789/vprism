"""
Provider configuration management.

This module provides configuration management for data providers,
including authentication credentials, rate limits, and provider-specific
settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from vprism.core.exceptions import ConfigurationException
from vprism.core.provider_abstraction import AuthConfig, AuthType, RateLimitConfig


class ProviderConfig(BaseModel):
    """Configuration for a single data provider."""

    name: str = Field(..., description="Provider name")
    enabled: bool = Field(True, description="Whether provider is enabled")
    priority: int = Field(1, description="Provider priority (1=highest)")

    # Authentication settings
    auth_type: AuthType = Field(AuthType.NONE, description="Authentication type")
    credentials: Dict[str, str] = Field(
        default_factory=dict, description="Authentication credentials"
    )

    # Rate limiting settings
    requests_per_minute: int = Field(60, description="Requests per minute limit")
    requests_per_hour: int = Field(1000, description="Requests per hour limit")
    concurrent_requests: int = Field(5, description="Concurrent requests limit")

    # Provider-specific settings
    settings: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific settings"
    )

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        """Validate priority is positive."""
        if v < 1:
            raise ValueError("Priority must be positive")
        return v

    @field_validator("requests_per_minute", "requests_per_hour", "concurrent_requests")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        """Validate rate limit values are positive."""
        if v <= 0:
            raise ValueError("Rate limit values must be positive")
        return v

    def to_auth_config(self) -> AuthConfig:
        """Convert to AuthConfig object."""
        return AuthConfig(auth_type=self.auth_type, credentials=self.credentials.copy())

    def to_rate_limit_config(self) -> RateLimitConfig:
        """Convert to RateLimitConfig object."""
        return RateLimitConfig(
            requests_per_minute=self.requests_per_minute,
            requests_per_hour=self.requests_per_hour,
            concurrent_requests=self.concurrent_requests,
        )


class ProvidersConfig(BaseModel):
    """Configuration for all data providers."""

    providers: Dict[str, ProviderConfig] = Field(
        default_factory=dict, description="Provider configurations"
    )
    default_provider: Optional[str] = Field(None, description="Default provider name")

    def add_provider(self, config: ProviderConfig) -> None:
        """Add a provider configuration."""
        self.providers[config.name] = config

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Get provider configuration by name."""
        return self.providers.get(name)

    def get_enabled_providers(self) -> List[ProviderConfig]:
        """Get all enabled provider configurations."""
        return [config for config in self.providers.values() if config.enabled]

    def get_providers_by_priority(self) -> List[ProviderConfig]:
        """Get enabled providers sorted by priority."""
        enabled = self.get_enabled_providers()
        return sorted(enabled, key=lambda p: p.priority)


@dataclass
class DefaultProviderConfigs:
    """Default configurations for built-in providers."""

    AKSHARE = ProviderConfig(
        name="akshare",
        enabled=True,
        priority=3,  # Lower priority
        auth_type=AuthType.NONE,
        requests_per_minute=30,
        requests_per_hour=1000,
        concurrent_requests=2,
        settings={
            "data_delay_seconds": 900,  # 15 minutes
            "max_history_days": 3650,  # ~10 years
        },
    )

    YFINANCE = ProviderConfig(
        name="yfinance",
        enabled=True,
        priority=2,  # Medium priority
        auth_type=AuthType.NONE,
        requests_per_minute=60,
        requests_per_hour=2000,
        concurrent_requests=5,
        settings={
            "data_delay_seconds": 0,  # Real-time
            "max_history_days": 36500,  # ~100 years
        },
    )

    ALPHA_VANTAGE = ProviderConfig(
        name="alpha_vantage",
        enabled=False,  # Disabled by default (requires API key)
        priority=2,  # Medium priority
        auth_type=AuthType.API_KEY,
        credentials={"api_key": ""},  # Must be configured by user
        requests_per_minute=5,  # Free tier limit
        requests_per_hour=500,  # Free tier limit
        concurrent_requests=1,
        settings={
            "data_delay_seconds": 0,  # Real-time
            "max_history_days": 7300,  # ~20 years
        },
    )


class ProviderConfigManager:
    """Manager for provider configurations."""

    def __init__(self, config_file: Optional[Path] = None):
        """Initialize configuration manager."""
        self.config_file = config_file or Path.home() / ".vprism" / "providers.json"
        self._config: Optional[ProvidersConfig] = None

    def load_config(self) -> ProvidersConfig:
        """Load provider configurations from file or create defaults."""
        if self._config is not None:
            return self._config

        if self.config_file.exists():
            try:
                import json

                with open(self.config_file, "r") as f:
                    data = json.load(f)
                self._config = ProvidersConfig.model_validate(data)
            except Exception as e:
                raise ConfigurationException(
                    f"Failed to load provider config from {self.config_file}: {e}",
                    config_key="provider_config_file",
                )
        else:
            # Create default configuration
            self._config = self._create_default_config()
            self.save_config()

        return self._config

    def save_config(self) -> None:
        """Save provider configurations to file."""
        if self._config is None:
            return

        # Ensure config directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            import json

            with open(self.config_file, "w") as f:
                json.dump(self._config.model_dump(), f, indent=2)
        except Exception as e:
            raise ConfigurationException(
                f"Failed to save provider config to {self.config_file}: {e}",
                config_key="provider_config_file",
            )

    def _create_default_config(self) -> ProvidersConfig:
        """Create default provider configuration."""
        config = ProvidersConfig()

        # Add default providers
        config.add_provider(DefaultProviderConfigs.AKSHARE)
        config.add_provider(DefaultProviderConfigs.YFINANCE)
        config.add_provider(DefaultProviderConfigs.ALPHA_VANTAGE)

        # Set default provider
        config.default_provider = "yfinance"

        return config

    def get_config(self) -> ProvidersConfig:
        """Get current provider configuration."""
        return self.load_config()

    def update_provider(self, provider_config: ProviderConfig) -> None:
        """Update a provider configuration."""
        config = self.load_config()
        config.add_provider(provider_config)
        self.save_config()

    def enable_provider(self, provider_name: str) -> None:
        """Enable a provider."""
        config = self.load_config()
        provider = config.get_provider(provider_name)
        if provider:
            provider.enabled = True
            self.save_config()

    def disable_provider(self, provider_name: str) -> None:
        """Disable a provider."""
        config = self.load_config()
        provider = config.get_provider(provider_name)
        if provider:
            provider.enabled = False
            self.save_config()

    def set_credentials(self, provider_name: str, credentials: Dict[str, str]) -> None:
        """Set credentials for a provider."""
        config = self.load_config()
        provider = config.get_provider(provider_name)
        if provider:
            provider.credentials.update(credentials)
            # Enable provider if credentials are provided
            if credentials and provider.auth_type != AuthType.NONE:
                provider.enabled = True
            self.save_config()
        else:
            raise ConfigurationException(
                f"Provider {provider_name} not found", config_key="provider_name"
            )

    def configure_alpha_vantage(self, api_key: str) -> None:
        """Configure Alpha Vantage provider with API key."""
        if not api_key:
            raise ConfigurationException(
                "Alpha Vantage API key cannot be empty",
                config_key="alpha_vantage_api_key",
            )

        self.set_credentials("alpha_vantage", {"api_key": api_key})

    def get_environment_credentials(self) -> Dict[str, Dict[str, str]]:
        """Get credentials from environment variables."""
        credentials = {}

        # Alpha Vantage
        alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if alpha_vantage_key:
            credentials["alpha_vantage"] = {"api_key": alpha_vantage_key}

        # Add other providers as needed
        # Example: Polygon.io
        polygon_key = os.getenv("POLYGON_API_KEY")
        if polygon_key:
            credentials["polygon"] = {"api_key": polygon_key}

        return credentials

    def apply_environment_credentials(self) -> None:
        """Apply credentials from environment variables."""
        env_credentials = self.get_environment_credentials()

        for provider_name, creds in env_credentials.items():
            try:
                self.set_credentials(provider_name, creds)
            except ConfigurationException:
                # Provider doesn't exist, skip
                continue


def create_provider_config_manager(
    config_file: Optional[Path] = None,
) -> ProviderConfigManager:
    """Factory function to create provider configuration manager."""
    return ProviderConfigManager(config_file)


def get_default_providers_config() -> ProvidersConfig:
    """Get default providers configuration."""
    config = ProvidersConfig()
    config.add_provider(DefaultProviderConfigs.AKSHARE)
    config.add_provider(DefaultProviderConfigs.YFINANCE)
    config.add_provider(DefaultProviderConfigs.ALPHA_VANTAGE)
    config.default_provider = "yfinance"
    return config
