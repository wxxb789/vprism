"""Data models supporting raw ingestion pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(slots=True)
class RawRecord:
    """Represents a single OHLCV observation supplied by an upstream provider."""

    supplier_symbol: str
    timestamp: datetime
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None = None
    provider: str | None = None


__all__ = ["RawRecord"]
