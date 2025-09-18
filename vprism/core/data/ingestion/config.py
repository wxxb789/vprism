"""Configuration primitives for the ingestion service."""

from __future__ import annotations

from dataclasses import dataclass

from vprism.core.exceptions.base import VPrismError


class IngestionConfigError(VPrismError):
    """Raised when ingestion configuration is invalid for a batch."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "INGESTION_CONFIG_ERROR")


@dataclass(slots=True, frozen=True)
class IngestionConfig:
    """Runtime configuration toggles controlling ingestion behaviour."""

    max_batch_rows: int | None = None
    enforce_monotonic_ts: bool = True
    allow_duplicates: bool = False

    def validate_batch_size(self, batch_size: int) -> None:
        """Ensure the configured batch size limit is respected."""

        if self.max_batch_rows is None:
            return
        if self.max_batch_rows <= 0:
            raise IngestionConfigError("max_batch_rows must be positive when provided")
        if batch_size > self.max_batch_rows:
            raise IngestionConfigError(f"batch size {batch_size} exceeds configured limit {self.max_batch_rows}")
