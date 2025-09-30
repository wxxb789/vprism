"""Logging configuration primitives for structured logging."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class LogConfig(BaseModel):
    """Configuration model used to initialise structured logging."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    level: str = "INFO"
    console_output: bool = True
    console_stream: Any = None
    file_output: bool = False
    file_path: str | None = None
    serialize: bool = True
    enqueue: bool = False
    catch: bool = True
    colorize: bool = False
    backtrace: bool = False
    diagnose: bool = False
    extra: dict[str, Any] = {}


__all__ = ["LogConfig"]
