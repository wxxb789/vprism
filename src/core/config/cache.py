"""缓存配置."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CacheConfig:
    """缓存配置"""

    enabled: bool = True
    memory_size: int = 1000
    disk_path: str = str(Path.home() / ".vprism" / "cache")
    ttl_default: int = 3600
    ttl_tick: int = 5
    ttl_intraday: int = 300
    ttl_daily: int = 3600
    ttl_weekly: int = 86400
