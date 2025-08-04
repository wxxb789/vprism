"""提供商配置."""

from dataclasses import dataclass


@dataclass
class ProviderConfig:
    """提供商配置"""

    timeout: int = 30
    max_retries: int = 3
    rate_limit: bool = True
    backoff_factor: float = 1.0
    max_backoff: int = 60
