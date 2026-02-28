"""Provider factory - simplified provider creation with lazy imports."""

from __future__ import annotations

from typing import Any

from vprism.core.data.providers.base import AuthConfig, AuthType, DataProvider, RateLimitConfig


def create_provider(name: str, **kwargs: Any) -> DataProvider:
    """Create a provider by name with lazy imports.

    Args:
        name: Provider name ('yahoo' or 'akshare')
        **kwargs: Provider-specific parameters (e.g., rate_limit)

    Returns:
        A DataProvider instance.

    Raises:
        ValueError: If provider name is unknown.
    """
    name = name.lower()
    auth_config = AuthConfig(auth_type=AuthType.NONE, credentials={})

    if name == "yahoo":
        from vprism.core.data.providers.yfinance import YFinance

        rate_limit = kwargs.get("rate_limit") or RateLimitConfig(
            requests_per_minute=2000,
            requests_per_hour=10000,
            requests_per_day=100000,
            concurrent_requests=10,
            backoff_factor=1.5,
            max_retries=3,
            initial_delay=0.5,
        )
        return YFinance(auth_config, rate_limit)

    if name == "akshare":
        from vprism.core.data.providers.akshare import AkShare

        rate_limit = kwargs.get("rate_limit") or RateLimitConfig(
            requests_per_minute=1000,
            requests_per_hour=5000,
            requests_per_day=20000,
            concurrent_requests=8,
            backoff_factor=2.0,
            max_retries=3,
            initial_delay=1.0,
        )
        return AkShare(auth_config, rate_limit)

    raise ValueError(f"Unknown provider: {name}. Available: 'yahoo', 'akshare'")


def create_default_providers() -> dict[str, DataProvider]:
    """Create the default set of providers.

    Returns:
        Dictionary mapping provider names to instances.
    """
    return {name: create_provider(name) for name in ["yahoo", "akshare"]}
