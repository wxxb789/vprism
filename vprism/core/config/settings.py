"""配置管理模块 - 处理vprism客户端的配置"""

import os
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


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

    cache: CacheConfig = field(default_factory=CacheConfig)
    providers: ProviderConfig = field(default_factory=ProviderConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def __post_init__(self) -> None:
        pass

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "VPrismConfig":
        """从字典创建配置"""
        cache_config = CacheConfig(**config_dict.get("cache", {}))
        provider_config = ProviderConfig(**config_dict.get("providers", {}))
        logging_config = LoggingConfig(**config_dict.get("logging", {}))

        return cls(cache=cache_config, providers=provider_config, logging=logging_config)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "cache": asdict(self.cache),
            "providers": asdict(self.providers),
            "logging": asdict(self.logging),
        }


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: Path | None = None):
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

        def deep_update(d: dict[str, Any], u: dict[str, Any]) -> dict[str, Any]:
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

            import tomli_w

            with open(self.config_path, "wb") as f:
                tomli_w.dump(self.config.to_dict(), f)
        except Exception as e:
            print(f"Warning: Failed to save config to {self.config_path}: {e}")


def get_default_config() -> VPrismConfig:
    """获取默认配置"""
    return VPrismConfig()


def load_config_from_env() -> dict[str, Any]:
    """从环境变量加载配置"""
    config = {}

    # 缓存配置
    cache_config: dict[str, Any] = {}
    vprism_cache_enabled = os.getenv("VPRISM_CACHE_ENABLED")
    if vprism_cache_enabled is not None:
        cache_config["enabled"] = vprism_cache_enabled.lower() == "true"
    vprism_cache_memory_size = os.getenv("VPRISM_CACHE_MEMORY_SIZE")
    if vprism_cache_memory_size is not None:
        cache_config["memory_size"] = int(vprism_cache_memory_size)
    if os.getenv("VPRISM_CACHE_DISK_PATH"):
        cache_config["disk_path"] = os.getenv("VPRISM_CACHE_DISK_PATH")

    if cache_config:
        config["cache"] = cache_config

    # 提供商配置
    provider_config: dict[str, Any] = {}
    vprism_provider_timeout = os.getenv("VPRISM_PROVIDER_TIMEOUT")
    if vprism_provider_timeout is not None:
        provider_config["timeout"] = int(vprism_provider_timeout)
    vprism_provider_max_retries = os.getenv("VPRISM_PROVIDER_MAX_RETRIES")
    if vprism_provider_max_retries is not None:
        provider_config["max_retries"] = int(vprism_provider_max_retries)
    vprism_provider_rate_limit = os.getenv("VPRISM_PROVIDER_RATE_LIMIT")
    if vprism_provider_rate_limit is not None:
        provider_config["rate_limit"] = vprism_provider_rate_limit.lower() == "true"

    if provider_config:
        config["providers"] = provider_config

    # 日志配置
    logging_config: dict[str, Any] = {}
    vprism_logging_level = os.getenv("VPRISM_LOGGING_LEVEL")
    if vprism_logging_level is not None:
        logging_config["level"] = vprism_logging_level
    vprism_logging_file = os.getenv("VPRISM_LOGGING_FILE")
    if vprism_logging_file is not None:
        logging_config["file"] = vprism_logging_file

    if logging_config:
        config["logging"] = logging_config

    return config
