from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # only for type hints
    from collections.abc import Iterable, Sequence
    from datetime import datetime

    from duckdb import DuckDBPyConnection


@dataclass(slots=True)
class RawRecord:
    symbol: str
    market: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    source_system: str
    upstream_origin: str | None = None


@dataclass(slots=True)
class ValidationIssue:
    field: str
    code: str
    message: str


@dataclass(slots=True)
class IngestionResult:
    written_rows: int
    rejected_rows: int
    batch_id: str
    duration_ms: float
    issues: list[ValidationIssue]


def validate_records(records: Sequence[RawRecord]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    last_ts: datetime | None = None
    seen: set[tuple[str, str, datetime]] = set()
    for r in records:
        key = (r.symbol, r.market, r.ts)
        if key in seen:
            issues.append(ValidationIssue("duplicate", "DUPLICATE_ROW", "duplicate symbol/market/timestamp"))
        else:
            seen.add(key)
        if r.open is None or r.high is None or r.low is None or r.close is None:
            issues.append(ValidationIssue("price", "NULL_PRICE", "price field is null"))
        if r.low is not None and r.high is not None and r.low > r.high:
            issues.append(ValidationIssue("ohlc", "LOW_GT_HIGH", "low greater than high"))
        if r.open is not None and r.high is not None and r.open > r.high:
            issues.append(ValidationIssue("ohlc", "OPEN_GT_HIGH", "open greater than high"))
        if r.close is not None and r.high is not None and r.close > r.high:
            issues.append(ValidationIssue("ohlc", "CLOSE_GT_HIGH", "close greater than high"))
        if last_ts and r.ts < last_ts:
            issues.append(ValidationIssue("timestamp", "NON_MONOTONIC", "timestamp non monotonic"))
        last_ts = r.ts
    return issues


def ingest_raw(conn: DuckDBPyConnection, records: Iterable[RawRecord], batch_id: str) -> IngestionResult:
    from datetime import datetime
    from time import perf_counter
    start = perf_counter()
    rec_list = list(records)
    issues = validate_records(rec_list)
    valid = len(issues) == 0
    written = 0
    if valid and rec_list:
        data = [
            (
                r.symbol,
                r.market,
                r.ts,
                r.open,
                r.high,
                r.low,
                r.close,
                r.volume if r.volume is not None else 0.0,
                r.source_system,
                r.upstream_origin,
                batch_id,
            )
            for r in rec_list
        ]
        conn.executemany(
            (
                "INSERT INTO raw_ohlcv_daily (symbol,market,ts,open,high,low,close,volume,source_system,upstream_origin,provider_batch_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)"
            ),
            data,
        )
        written = len(data)
        groups: dict[tuple[str, str], list[RawRecord]] = {}
        for r in rec_list:
            groups.setdefault((r.symbol, r.market), []).append(r)
        rows = []
        for (symbol, market), items in groups.items():
            total = len(items)
            missing = sum(1 for x in items if any(getattr(x, f) is None for f in ["open", "high", "low", "close"]))
            price_issue_codes = {"LOW_GT_HIGH", "OPEN_GT_HIGH", "CLOSE_GT_HIGH"}
            anomalies = sum(1 for i in issues if i.code in price_issue_codes)
            completeness_score = 0.0 if total == 0 else 1 - (missing / total)
            accuracy_score = 0.0 if total == 0 else 1 - (anomalies / total)
            consistency_score = 1.0
            start_date = min(x.ts for x in items).date()
            end_date = max(x.ts for x in items).date()
            provider = items[0].source_system
            rows.append(
                [
                    symbol,
                    market,
                    str(end_date),
                    symbol,
                    market,
                    start_date,
                    end_date,
                    completeness_score,
                    accuracy_score,
                    consistency_score,
                    total,
                    missing,
                    anomalies,
                    provider,
                    datetime.now(),
                ]
            )
        if rows:
            conn.executemany(
                (
                    "INSERT OR REPLACE INTO data_quality (id, symbol, market, date_range_start, date_range_end, "
                    "completeness_score, accuracy_score, consistency_score, total_records, missing_records, "
                    "anomaly_count, provider, checked_at) "
                    "VALUES (md5(concat(?, ?, ?)), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                ),
                rows,
            )
    end = perf_counter()
    return IngestionResult(written_rows=written, rejected_rows=0 if valid else len(rec_list), batch_id=batch_id, duration_ms=(end-start)*1000, issues=issues)
