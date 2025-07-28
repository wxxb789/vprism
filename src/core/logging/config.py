"""Logging configuration."""

from typing import Any

from pydantic import BaseModel


class LogConfig(BaseModel):
    """Logging configuration model."""

    level: str = "INFO"
    format: str = "json"
    console_output: bool = True
    file_output: bool = False
    file_path: str | None = None
    rotation: str | None = None
    retention: str | None = None
    compression: str | None = None
    serialize: bool = True
    enqueue: bool = False
    catch: bool = True
    colorize: bool = True
    backtrace: bool = True
    diagnose: bool = True
    extra: dict[str, Any] = {}
