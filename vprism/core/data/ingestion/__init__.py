"""Raw data ingestion models and helpers."""

from __future__ import annotations

from vprism.core.data.ingestion.config import IngestionConfig, IngestionConfigError
from vprism.core.data.ingestion.models import RawRecord
from vprism.core.data.ingestion.service import FailureSummary, IngestionResult, ingest
from vprism.core.data.ingestion.validator import ValidationIssue

__all__ = [
    "FailureSummary",
    "IngestionConfig",
    "IngestionConfigError",
    "IngestionResult",
    "RawRecord",
    "ValidationIssue",
    "ingest",
]
