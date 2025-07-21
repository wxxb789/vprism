"""配置管理模块 - 处理vprism客户端的配置"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import tomllib
from dataclasses import dataclass, asdict


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


@dataclass
class ProviderConfig:
    """提供商配置"""

    timeout: int = 30
    max_retries: int = 3
    rate_limit: bool = True
    backoff_factor: float = 1.0
    max_backoff: int = 60


@dataclass
class LoggingConfig:
    """日志配置"""

    level: str = "INFO"
    file: str = str(Path.home() / ".vprism" / "logs" / "vprism.log")
    max_file_size: str = "10MB"
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class VPrismConfig:
    """vprism主配置"""

    cache: CacheConfig = None
    providers: ProviderConfig = None
    logging: LoggingConfig = None

    def __post_init__(self):
        if self.cache is None:
            self.cache = CacheConfig()
        if self.providers is None:
            self.providers = ProviderConfig()
        if self.logging is None:
            self.logging = LoggingConfig()

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "VPrismConfig":
        """从字典创建配置"""
        cache_config = CacheConfig(**config_dict.get("cache", {}))
        provider_config = ProviderConfig(**config_dict.get("providers", {}))
        logging_config = LoggingConfig(**config_dict.get("logging", {}))

        return cls(
            cache=cache_config, providers=provider_config, logging=logging_config
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "cache": asdict(self.cache),
            "providers": asdict(self.providers),
            "logging": asdict(self.logging),
        }


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: Optional[Path] = None):
        """初始化配置管理器

        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        self.config_path = config_path or Path.home() / ".vprism" / "config.toml"
        self.config = self._load_config()

    def _load_config(self) -> VPrismConfig:
        """加载配置"""
        if not self.config_path.exists():
            return VPrismConfig()

        try:
            with open(self.config_path, "rb") as f:
                config_dict = tomllib.load(f)
            return VPrismConfig.from_dict(config_dict)
        except Exception as e:
            # 如果配置文件有问题，使用默认配置
            print(f"Warning: Failed to load config from {self.config_path}: {e}")
            return VPrismConfig()

    def get_config(self) -> VPrismConfig:
        """获取当前配置"""
        return self.config

    def update_config(self, **updates: Any) -> None:
        """更新配置"""
        config_dict = self.config.to_dict()

        def deep_update(d: Dict, u: Dict) -> Dict:
            """深度更新字典"""
            for k, v in u.items():
                if isinstance(v, dict):
                    d[k] = deep_update(d.get(k, {}), v)
                else:
                    d[k] = v
            return d

        deep_update(config_dict, updates)
        self.config = VPrismConfig.from_dict(config_dict)

    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            import tomli

            with open(self.config_path, "wb") as f:
                tomli.dump(self.config.to_dict(), f)
        except Exception as e:
            print(f"Warning: Failed to save config to {self.config_path}: {e}")


def get_default_config() -> VPrismConfig:
    """获取默认配置"""
    return VPrismConfig()


def load_config_from_env() -> Dict[str, Any]:
    """从环境变量加载配置"""
    config = {}

    # 缓存配置
    cache_config = {}
    if os.getenv("VPRISM_CACHE_ENABLED"):
        cache_config["enabled"] = os.getenv("VPRISM_CACHE_ENABLED").lower() == "true"
    if os.getenv("VPRISM_CACHE_MEMORY_SIZE"):
        cache_config["memory_size"] = int(os.getenv("VPRISM_CACHE_MEMORY_SIZE"))
    if os.getenv("VPRISM_CACHE_DISK_PATH"):
        cache_config["disk_path"] = os.getenv("VPRISM_CACHE_DISK_PATH")

    if cache_config:
        config["cache"] = cache_config

    # 提供商配置
    provider_config = {}
    if os.getenv("VPRISM_PROVIDER_TIMEOUT"):
        provider_config["timeout"] = int(os.getenv("VPRISM_PROVIDER_TIMEOUT"))
    if os.getenv("VPRISM_PROVIDER_MAX_RETRIES"):
        provider_config["max_retries"] = int(os.getenv("VPRISM_PROVIDER_MAX_RETRIES"))
    if os.getenv("VPRISM_PROVIDER_RATE_LIMIT"):
        provider_config["rate_limit"] = (
            os.getenv("VPRISM_PROVIDER_RATE_LIMIT").lower() == "true"
        )

    if provider_config:
        config["providers"] = provider_config

    # 日志配置
    logging_config = {}
    if os.getenv("VPRISM_LOGGING_LEVEL"):
        logging_config["level"] = os.getenv("VPRISM_LOGGING_LEVEL")
    if os.getenv("VPRISM_LOGGING_FILE"):
        logging_config["file"] = os.getenv("VPRISM_LOGGING_FILE")

    if logging_config:
        config["logging"] = logging_config

    return config
