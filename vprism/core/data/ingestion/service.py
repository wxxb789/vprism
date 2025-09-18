"""Ingestion service that validates and persists raw OHLCV batches."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence  # noqa: TC003
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import TYPE_CHECKING
from uuid import uuid4

try:  # pragma: no cover - optional at runtime for typing.
    from duckdb import DuckDBPyConnection
except Exception:  # pragma: no cover
    DuckDBPyConnection = "DuckDBPyConnection"  # type: ignore[misc,assignment]

from vprism.core.data.ingestion.config import IngestionConfig
from vprism.core.data.ingestion.validator import (
    ValidatedRecord,
    ValidationIssue,
    validate_batch,
)
from vprism.core.data.schema import RAW_OHLCV_TABLE

if TYPE_CHECKING:
    from vprism.core.data.ingestion.models import RawRecord


@dataclass(slots=True, frozen=True)
class FailureSummary:
    """Aggregated failure counts grouped by validation code."""

    code: str
    count: int


@dataclass(slots=True, frozen=True)
class IngestionResult:
    """Result payload returned after running an ingestion batch."""

    batch_id: str
    written_rows: int
    rejected_rows: int
    duration_ms: float
    fail_reasons: tuple[FailureSummary, ...]
    issues: tuple[ValidationIssue, ...]
    duplicates_dropped: int = 0


def _prepare_rows(
    records: Sequence[ValidatedRecord],
    *,
    market: str,
    provider: str,
    batch_id: str,
    ingest_time: datetime,
) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    for validated in records:
        record = validated.record
        rows.append(
            (
                record.supplier_symbol,
                market,
                record.timestamp,
                record.open,
                record.high,
                record.low,
                record.close,
                record.volume,
                record.provider or provider,
                batch_id,
                ingest_time,
            )
        )
    return rows


def _summarise(counter: Counter[str]) -> tuple[FailureSummary, ...]:
    summaries = [FailureSummary(code=code, count=count) for code, count in counter.items()]
    summaries.sort(key=lambda item: (-item.count, item.code))
    return tuple(summaries)


def ingest(
    conn: DuckDBPyConnection,
    records: Iterable[RawRecord],
    *,
    provider: str,
    market: str,
    config: IngestionConfig | None = None,
) -> IngestionResult:
    """Validate incoming records and persist successful rows into DuckDB."""

    config = config or IngestionConfig()

    batch_records = list(records)
    config.validate_batch_size(len(batch_records))

    start = perf_counter()
    batch_id = uuid4().hex
    ingest_time = datetime.now(UTC)

    validated, issues = validate_batch(
        batch_records,
        market=market,
        enforce_monotonic_ts=config.enforce_monotonic_ts,
    )

    issue_counter: Counter[str] = Counter(issue.code for issue in issues)
    fatal_indexes = {issue.index for issue in issues if issue.fatal}

    deduped: list[ValidatedRecord] = []
    duplicates_dropped = 0
    seen_keys: set[tuple[str, str, datetime]] = set()
    for validated_record in validated:
        record = validated_record.record
        key = (record.supplier_symbol, market, record.timestamp)
        if key in seen_keys:
            duplicates_dropped += 1
            issue_counter["DUPLICATE_ROW"] += 1
            is_fatal = not config.allow_duplicates
            if is_fatal:
                fatal_indexes.add(validated_record.index)
            issues.append(
                ValidationIssue(
                    index=validated_record.index,
                    field="timestamp",
                    code="DUPLICATE_ROW",
                    message="duplicate supplier_symbol/market/timestamp within batch",
                    fatal=is_fatal,
                )
            )
            continue
        seen_keys.add(key)
        deduped.append(validated_record)

    rows_to_insert = _prepare_rows(
        [record for record in deduped if record.index not in fatal_indexes],
        market=market,
        provider=provider,
        batch_id=batch_id,
        ingest_time=ingest_time,
    )

    written_rows = 0
    if rows_to_insert:
        RAW_OHLCV_TABLE.ensure(conn)
        conn.executemany(
            (
                "INSERT INTO raw_ohlcv (supplier_symbol, market, ts, open, high, low, close, volume, provider, batch_id, ingest_time) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            rows_to_insert,
        )
        written_rows = len(rows_to_insert)

    rejected_rows = len(fatal_indexes)
    duration_ms = (perf_counter() - start) * 1000

    return IngestionResult(
        batch_id=batch_id,
        written_rows=written_rows,
        rejected_rows=rejected_rows,
        duration_ms=duration_ms,
        fail_reasons=_summarise(issue_counter),
        issues=tuple(issues),
        duplicates_dropped=duplicates_dropped,
    )
