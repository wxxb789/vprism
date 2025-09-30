"""Structured logging utilities with trace propagation."""

from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any, IO, Iterator
from uuid import uuid4

from vprism.core.logging.config import LogConfig

try:  # pragma: no cover - loguru is an optional dependency at runtime
    from loguru import logger as _loguru_logger
    from loguru._logger import Logger as _LoguruLogger  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - fallback for environments without loguru
    _loguru_logger = logging.getLogger("vprism")

    class _LoguruLogger(logging.Logger):
        pass


_TRACE_ID_VAR: ContextVar[str | None] = ContextVar("vprism_trace_id", default=None)
_CONTEXT_VAR: ContextVar[dict[str, Any]] = ContextVar("vprism_log_context", default={})


def _ensure_trace_id() -> str:
    trace_id = _TRACE_ID_VAR.get()
    if trace_id is None:
        trace_id = uuid4().hex
        _TRACE_ID_VAR.set(trace_id)
    return trace_id


def _patch_record(record: dict[str, Any]) -> None:
    extra = record.setdefault("extra", {})
    trace_id = extra.get("trace_id")
    if trace_id:
        _TRACE_ID_VAR.set(trace_id)
    else:
        extra["trace_id"] = _ensure_trace_id()

    context_values = _CONTEXT_VAR.get({})
    if context_values:
        for key in ("provider", "error_code"):
            if key in context_values and extra.get(key) is None:
                extra[key] = context_values[key]
        for key, value in context_values.items():
            if key not in {"provider", "error_code", "trace_id"}:
                extra.setdefault(key, value)

    extra.setdefault("provider", None)
    extra.setdefault("error_code", None)


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return str(value)


def _format_payload(record: dict[str, Any]) -> dict[str, Any]:
    extra = record.get("extra", {})
    context = {k: v for k, v in extra.items() if k not in {"trace_id", "error_code", "provider"}}
    level_value = record.get("level")
    if isinstance(level_value, dict):
        level_name = level_value.get("name")
    elif hasattr(level_value, "name"):
        level_name = getattr(level_value, "name")
    elif level_value is None:
        level_name = "INFO"
    else:
        level_name = str(level_value)
    payload: dict[str, Any] = {
        "timestamp": record["time"].isoformat() if "time" in record else datetime.utcnow().isoformat(),
        "level": level_name,
        "message": record.get("message"),
        "trace_id": extra.get("trace_id"),
        "error_code": extra.get("error_code"),
        "provider": extra.get("provider"),
    }
    if context:
        payload["context"] = context
    exception = record.get("exception")
    if exception:
        formatted = exception.get("formatted") if isinstance(exception, dict) else None
        payload["exception"] = formatted or str(exception)
    return payload


class _StreamJsonSink:
    """Sink writing structured JSON payloads to a text stream."""

    def __init__(self, stream: IO[str]) -> None:
        self._stream = stream

    def __call__(self, message: Any) -> None:  # pragma: no cover - exercised via tests
        payload = _format_payload(message.record)
        self._stream.write(json.dumps(payload, default=_json_default))
        self._stream.write("\n")
        self._stream.flush()


class _FileJsonSink:
    """Sink persisting JSON lines to a file path."""

    def __init__(self, path: str) -> None:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._path = path

    def __call__(self, message: Any) -> None:  # pragma: no cover - simple file IO
        payload = _format_payload(message.record)
        with open(self._path, "a", encoding="utf-8") as file:
            file.write(json.dumps(payload, default=_json_default))
            file.write("\n")


logger: _LoguruLogger = _loguru_logger  # expose configured logger


def _configure_from_config(config: LogConfig) -> None:
    handlers: list[dict[str, Any]] = []
    if config.console_output:
        stream = config.console_stream or sys.stdout
        handlers.append({"sink": _StreamJsonSink(stream), "level": config.level})
    if config.file_output and config.file_path:
        handlers.append({"sink": _FileJsonSink(config.file_path), "level": config.level})

    configure_kwargs: dict[str, Any] = {"handlers": handlers, "patcher": _patch_record}
    extra = config.extra or {}
    if extra:
        configure_kwargs["extra"] = extra

    if hasattr(logger, "configure"):
        logger.configure(**configure_kwargs)
    else:  # pragma: no cover - stdlib logging fallback
        logging.basicConfig(level=getattr(logging, config.level.upper(), logging.INFO))


def configure_logging(level: str = "INFO", **kwargs: Any) -> None:
    """Configure structured logging with the provided level and options."""

    config = LogConfig(level=level, **kwargs)
    _configure_from_config(config)


class StructuredLogger:
    """Wrapper exposing a configured loguru logger with trace-aware context helpers."""

    def __init__(self, config: LogConfig | None = None) -> None:
        self.config = config or LogConfig()
        _configure_from_config(self.config)
        self.logger: _LoguruLogger = logger

    def configure(self, **kwargs: Any) -> None:
        """Update logger configuration at runtime."""

        self.config = self.config.model_copy(update=kwargs)
        _configure_from_config(self.config)
        self.logger = logger

    @contextmanager
    def context(self, *, trace_id: str | None = None, **extra: Any) -> Iterator[str]:
        """Context manager ensuring a trace id is available for nested log events."""

        with log_context(trace_id=trace_id, **extra) as active_trace:
            yield active_trace


def get_logger(name: str | None = None) -> _LoguruLogger:
    """Return a logger optionally bound to ``name``."""

    if name and hasattr(logger, "bind"):
        return logger.bind(logger_name=name)
    return logger


def bind(**kwargs: Any) -> _LoguruLogger:
    """Bind structured context to the global logger instance."""

    if hasattr(logger, "bind"):
        return logger.bind(**kwargs)
    return logger


@contextmanager
def log_context(*, trace_id: str | None = None, **extra: Any) -> Iterator[str]:
    """Context manager that propagates trace ids and additional metadata."""

    previous_context = _CONTEXT_VAR.get({})
    new_context = {**previous_context, **extra}
    context_token = _CONTEXT_VAR.set(new_context)

    active_trace = trace_id or uuid4().hex
    trace_token = _TRACE_ID_VAR.set(active_trace)

    try:
        yield active_trace
    finally:
        _TRACE_ID_VAR.reset(trace_token)
        _CONTEXT_VAR.reset(context_token)


def current_trace_id() -> str:
    """Return the currently active trace id, generating one if required."""

    return _ensure_trace_id()


configure_logging()


__all__ = [
    "StructuredLogger",
    "bind",
    "configure_logging",
    "current_trace_id",
    "get_logger",
    "log_context",
    "logger",
]
