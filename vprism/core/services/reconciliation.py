"""Reconciliation service implementing PRD-6 sampling and classification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, date
from decimal import Decimal, DivisionByZero, InvalidOperation
from enum import Enum
from random import Random
from typing import TYPE_CHECKING, Callable, Sequence
from uuid import uuid4

from vprism.core.data.schema import ensure_reconciliation_tables
from vprism.core.exceptions.base import ReconciliationError
from vprism.core.models.base import DataPoint
from vprism.core.models.market import MarketType

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

PriceSeriesLoader = Callable[[str, MarketType, date, date], Sequence[DataPoint]]
RunWriter = Callable[["ReconciliationRunRow"], None]
DiffWriter = Callable[["ReconciliationDiffRow"], None]


class ReconciliationStatus(str, Enum):
    """Classification of reconciliation results."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ReconciliationThresholds:
    """Threshold configuration for reconciliation classification."""

    close_warn: Decimal = Decimal("5")
    close_fail: Decimal = Decimal("10")
    volume_warn: Decimal = Decimal("1.2")
    volume_fail: Decimal = Decimal("1.5")


@dataclass(frozen=True)
class ReconciliationSample:
    """Single reconciliation comparison for a symbol/date."""

    symbol: str
    date: date
    close_a: Decimal | None
    close_b: Decimal | None
    close_bp_diff: Decimal | None
    volume_a: Decimal | None
    volume_b: Decimal | None
    volume_ratio: Decimal | None
    status: ReconciliationStatus


@dataclass(frozen=True)
class ReconciliationSummary:
    """Aggregated reconciliation run statistics."""

    market: MarketType
    start: date
    end: date
    source_a: str
    source_b: str
    sample_size: int
    pass_count: int
    warn_count: int
    fail_count: int
    p95_close_bp_diff: Decimal


@dataclass(frozen=True)
class ReconcileResult:
    """Reconciliation result set including samples and summary."""

    run_id: str
    created_at: datetime
    summary: ReconciliationSummary
    sampled_symbols: tuple[str, ...]
    samples: tuple[ReconciliationSample, ...]


@dataclass(frozen=True)
class ReconciliationRunRow:
    """Row persisted into the ``reconciliation_runs`` DuckDB table."""

    run_id: str
    market: str
    start: date
    end: date
    source_a: str
    source_b: str
    sample_size: int
    created_at: datetime
    pass_count: int
    warn_count: int
    fail_count: int
    p95_bp_diff: Decimal


@dataclass(frozen=True)
class ReconciliationDiffRow:
    """Row persisted into the ``reconciliation_diffs`` DuckDB table."""

    run_id: str
    symbol: str
    date: date
    close_a: Decimal | None
    close_b: Decimal | None
    close_bp_diff: Decimal | None
    volume_a: Decimal | None
    volume_b: Decimal | None
    volume_ratio: Decimal | None
    status: ReconciliationStatus


class ReconciliationService:
    """Sample symbols from two providers and classify reconciliation outcomes."""

    def __init__(
        self,
        provider_a_loader: PriceSeriesLoader,
        provider_b_loader: PriceSeriesLoader,
        *,
        source_a: str,
        source_b: str,
        default_sample_size: int = 50,
        thresholds: ReconciliationThresholds | None = None,
        rng: Random | None = None,
        run_writer: RunWriter | None = None,
        diff_writer: DiffWriter | None = None,
        clock: Callable[[], datetime] | None = None,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if default_sample_size <= 0:
            raise ReconciliationError("default sample size must be positive")
        self._provider_a_loader = provider_a_loader
        self._provider_b_loader = provider_b_loader
        self._source_a = source_a
        self._source_b = source_b
        self._default_sample_size = default_sample_size
        self._thresholds = thresholds or ReconciliationThresholds()
        self._rng = rng or Random()
        self._run_writer = run_writer
        self._diff_writer = diff_writer
        self._clock = clock or (lambda: datetime.now(UTC))
        self._run_id_factory = run_id_factory or (lambda: uuid4().hex)

    def reconcile(
        self,
        symbols: Sequence[str],
        market: MarketType,
        date_range: tuple[date, date],
        sample_size: int | None = None,
    ) -> ReconcileResult:
        if not symbols:
            raise ReconciliationError("symbols list must not be empty")
        start, end = date_range
        if start > end:
            raise ReconciliationError("start date must be on or before end date")
        if sample_size is not None and sample_size <= 0:
            raise ReconciliationError("sample size must be positive")

        unique_symbols = list(dict.fromkeys(symbols))
        requested_size = sample_size or self._default_sample_size
        sample_count = min(len(unique_symbols), requested_size)
        if sample_count == len(unique_symbols):
            sampled = tuple(unique_symbols)
        else:
            sampled = tuple(self._rng.sample(unique_symbols, sample_count))

        samples: list[ReconciliationSample] = []
        pass_count = warn_count = fail_count = 0
        abs_close_diffs: list[Decimal] = []

        for symbol in sampled:
            symbol_samples = self._reconcile_symbol(symbol, market, start, end)
            for sample in symbol_samples:
                samples.append(sample)
                if sample.status is ReconciliationStatus.PASS:
                    pass_count += 1
                elif sample.status is ReconciliationStatus.WARN:
                    warn_count += 1
                else:
                    fail_count += 1
                if sample.close_bp_diff is not None:
                    abs_close_diffs.append(abs(sample.close_bp_diff))

        p95 = self._percentile(abs_close_diffs, Decimal("0.95")) if abs_close_diffs else Decimal("0")

        summary = ReconciliationSummary(
            market=market,
            start=start,
            end=end,
            source_a=self._source_a,
            source_b=self._source_b,
            sample_size=len(sampled),
            pass_count=pass_count,
            warn_count=warn_count,
            fail_count=fail_count,
            p95_close_bp_diff=p95,
        )
        run_id = self._run_id_factory()
        created_at = self._clock()

        if self._run_writer is not None:
            run_row = ReconciliationRunRow(
                run_id=run_id,
                market=market.value,
                start=start,
                end=end,
                source_a=self._source_a,
                source_b=self._source_b,
                sample_size=len(sampled),
                created_at=created_at,
                pass_count=pass_count,
                warn_count=warn_count,
                fail_count=fail_count,
                p95_bp_diff=p95,
            )
            self._run_writer(run_row)

        if self._diff_writer is not None:
            for sample in samples:
                diff_row = ReconciliationDiffRow(
                    run_id=run_id,
                    symbol=sample.symbol,
                    date=sample.date,
                    close_a=sample.close_a,
                    close_b=sample.close_b,
                    close_bp_diff=sample.close_bp_diff,
                    volume_a=sample.volume_a,
                    volume_b=sample.volume_b,
                    volume_ratio=sample.volume_ratio,
                    status=sample.status,
                )
                self._diff_writer(diff_row)

        return ReconcileResult(
            run_id=run_id,
            created_at=created_at,
            summary=summary,
            sampled_symbols=sampled,
            samples=tuple(samples),
        )

    def _reconcile_symbol(
        self,
        symbol: str,
        market: MarketType,
        start: date,
        end: date,
    ) -> list[ReconciliationSample]:
        series_a = self._provider_a_loader(symbol, market, start, end)
        series_b = self._provider_b_loader(symbol, market, start, end)
        indexed_a = self._index_by_date(series_a, start, end)
        indexed_b = self._index_by_date(series_b, start, end)
        dates = sorted(set(indexed_a) | set(indexed_b))

        samples: list[ReconciliationSample] = []
        for record_date in dates:
            point_a = indexed_a.get(record_date)
            point_b = indexed_b.get(record_date)
            close_a = self._extract_decimal(point_a.close_price) if point_a else None
            close_b = self._extract_decimal(point_b.close_price) if point_b else None
            volume_a = self._extract_decimal(point_a.volume) if point_a else None
            volume_b = self._extract_decimal(point_b.volume) if point_b else None
            close_bp_diff = self._compute_close_bp_diff(close_a, close_b)
            volume_ratio = self._compute_volume_ratio(volume_a, volume_b)
            status = self._classify(close_bp_diff, volume_ratio, point_a is None, point_b is None)
            samples.append(
                ReconciliationSample(
                    symbol=symbol,
                    date=record_date,
                    close_a=close_a,
                    close_b=close_b,
                    close_bp_diff=close_bp_diff,
                    volume_a=volume_a,
                    volume_b=volume_b,
                    volume_ratio=volume_ratio,
                    status=status,
                )
            )
        return samples

    @staticmethod
    def _index_by_date(points: Sequence[DataPoint], start: date, end: date) -> dict[date, DataPoint]:
        indexed: dict[date, DataPoint] = {}
        for point in points:
            point_date = point.timestamp.date()
            if start <= point_date <= end:
                indexed[point_date] = point
        return indexed

    @staticmethod
    def _extract_decimal(value: Decimal | float | int | None) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    @staticmethod
    def _compute_close_bp_diff(close_a: Decimal | None, close_b: Decimal | None) -> Decimal | None:
        if close_a is None or close_b is None:
            return None
        if close_b == 0:
            return None
        try:
            return (close_a - close_b) / close_b * Decimal("10000")
        except (InvalidOperation, DivisionByZero):
            return None

    @staticmethod
    def _compute_volume_ratio(volume_a: Decimal | None, volume_b: Decimal | None) -> Decimal | None:
        if volume_a is None or volume_b is None:
            return None
        if volume_b == 0:
            return None
        try:
            return volume_a / volume_b
        except (InvalidOperation, DivisionByZero):
            return None

    def _classify(
        self,
        close_bp_diff: Decimal | None,
        volume_ratio: Decimal | None,
        missing_a: bool,
        missing_b: bool,
    ) -> ReconciliationStatus:
        if missing_a or missing_b:
            return ReconciliationStatus.FAIL

        status = ReconciliationStatus.PASS

        if close_bp_diff is None:
            return ReconciliationStatus.FAIL
        magnitude = abs(close_bp_diff)
        if magnitude >= self._thresholds.close_fail:
            status = ReconciliationStatus.FAIL
        elif magnitude >= self._thresholds.close_warn:
            status = ReconciliationStatus.WARN

        if volume_ratio is None or volume_ratio <= 0:
            return ReconciliationStatus.FAIL

        deviation = max(volume_ratio, Decimal("1") / volume_ratio)
        if deviation >= self._thresholds.volume_fail:
            return ReconciliationStatus.FAIL
        if deviation >= self._thresholds.volume_warn and status is ReconciliationStatus.PASS:
            status = ReconciliationStatus.WARN
        return status

    @staticmethod
    def _percentile(values: Sequence[Decimal], percentile: Decimal) -> Decimal:
        if not values:
            return Decimal("0")
        sorted_values = sorted(values)
        if len(sorted_values) == 1:
            return sorted_values[0]
        rank = (len(sorted_values) - 1) * percentile
        lower_index = int(rank)
        upper_index = min(lower_index + 1, len(sorted_values) - 1)
        lower_value = sorted_values[lower_index]
        upper_value = sorted_values[upper_index]
        fraction = rank - Decimal(lower_index)
        return lower_value + (upper_value - lower_value) * fraction


class DuckDBReconciliationWriter:
    """Persist reconciliation run summaries and diffs into DuckDB."""

    def __init__(self, connection: DuckDBPyConnection) -> None:
        self._connection = connection
        ensure_reconciliation_tables(connection)

    def write_run(self, row: ReconciliationRunRow) -> None:
        self._connection.execute(
            """
            INSERT INTO reconciliation_runs
            (run_id, market, "start", "end", source_a, source_b, sample_size, created_at,
             "pass", "warn", "fail", p95_bp_diff)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row.run_id,
                row.market,
                row.start,
                row.end,
                row.source_a,
                row.source_b,
                row.sample_size,
                row.created_at,
                row.pass_count,
                row.warn_count,
                row.fail_count,
                float(row.p95_bp_diff),
            ],
        )

    def write_diff(self, row: ReconciliationDiffRow) -> None:
        self._connection.execute(
            """
            INSERT INTO reconciliation_diffs
            (run_id, symbol, date, close_a, close_b, close_bp_diff, volume_a, volume_b, volume_ratio, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row.run_id,
                row.symbol,
                row.date,
                _to_float(row.close_a),
                _to_float(row.close_b),
                _to_float(row.close_bp_diff),
                _to_float(row.volume_a),
                _to_float(row.volume_b),
                _to_float(row.volume_ratio),
                row.status.value,
            ],
        )


def _to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


__all__ = [
    "PriceSeriesLoader",
    "ReconcileResult",
    "ReconciliationDiffRow",
    "ReconciliationRunRow",
    "ReconciliationSample",
    "ReconciliationService",
    "ReconciliationStatus",
    "ReconciliationSummary",
    "ReconciliationThresholds",
    "DuckDBReconciliationWriter",
]
