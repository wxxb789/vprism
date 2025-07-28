"""日志配置."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class LoggingConfig:
    """日志配置"""

    level: str = "INFO"
    file: str = str(Path.home() / ".vprism" / "logs" / "vprism.log")
    max_file_size: str = "10MB"
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
