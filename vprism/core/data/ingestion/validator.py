"""Validation utilities for raw OHLCV ingestion batches."""

from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING

from vprism.core.data.ingestion.models import RawRecord

_DEFAULT_VOLUME = -1.0
_EPSILON = 1e-12

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(slots=True, frozen=True)
class ValidationIssue:
    """Represents a single validation issue detected during ingestion."""

    index: int
    field: str
    code: str
    message: str
    fatal: bool = True


@dataclass(slots=True)
class ValidatedRecord:
    """Container mapping an input index to its sanitised record."""

    index: int
    record: RawRecord


def _is_missing(value: object) -> bool:
    return value is None


def _ensure_finite(value: float) -> bool:
    return isfinite(value)


def _violates_low_high(low: float, high: float) -> bool:
    return (low - high) > _EPSILON


def _above_high(value: float, high: float) -> bool:
    return (value - high) > _EPSILON


def _below_low(value: float, low: float) -> bool:
    return (low - value) > _EPSILON


def validate_batch(
    records: Sequence[RawRecord],
    *,
    market: str,
    enforce_monotonic_ts: bool = True,
) -> tuple[list[ValidatedRecord], list[ValidationIssue]]:
    """Validate a batch of records and return sanitised successes with issues."""

    issues: list[ValidationIssue] = []
    validated: list[ValidatedRecord] = []
    last_ts_by_symbol: dict[tuple[str, str], datetime] = {}

    for index, record in enumerate(records):
        fatal = False
        symbol = record.supplier_symbol
        timestamp = record.timestamp

        if not symbol:
            issues.append(
                ValidationIssue(
                    index=index,
                    field="supplier_symbol",
                    code="MISSING_FIELD",
                    message="supplier_symbol is required",
                )
            )
            fatal = True

        if timestamp is None:
            issues.append(
                ValidationIssue(
                    index=index,
                    field="timestamp",
                    code="MISSING_FIELD",
                    message="timestamp is required",
                )
            )
            fatal = True

        numeric_fields = {
            "open": record.open,
            "high": record.high,
            "low": record.low,
            "close": record.close,
        }
        for field, value in numeric_fields.items():
            if _is_missing(value):
                issues.append(
                    ValidationIssue(
                        index=index,
                        field=field,
                        code="MISSING_FIELD",
                        message=f"{field} is required",
                    )
                )
                fatal = True
                continue
            if not _ensure_finite(value):
                issues.append(
                    ValidationIssue(
                        index=index,
                        field=field,
                        code="NON_FINITE_VALUE",
                        message=f"{field} must be finite",
                    )
                )
                fatal = True

        if not fatal:
            assert record.low is not None
            assert record.high is not None
            assert record.open is not None
            assert record.close is not None

            low = record.low
            high = record.high
            open_ = record.open
            close = record.close

            if _violates_low_high(low, high):
                issues.append(
                    ValidationIssue(
                        index=index,
                        field="low_high",
                        code="LOW_ABOVE_HIGH",
                        message="low price cannot exceed high price",
                    )
                )
                fatal = True
            else:
                if _above_high(open_, high) or _below_low(open_, low):
                    issues.append(
                        ValidationIssue(
                            index=index,
                            field="open",
                            code="OPEN_OUT_OF_RANGE",
                            message="open price must lie within [low, high]",
                        )
                    )
                    fatal = True
                if _above_high(close, high) or _below_low(close, low):
                    issues.append(
                        ValidationIssue(
                            index=index,
                            field="close",
                            code="CLOSE_OUT_OF_RANGE",
                            message="close price must lie within [low, high]",
                        )
                    )
                    fatal = True

        volume = record.volume
        if volume is None:
            issues.append(
                ValidationIssue(
                    index=index,
                    field="volume",
                    code="MISSING_VOLUME_DEFAULTED",
                    message="volume missing; defaulted to -1",
                    fatal=False,
                )
            )
            volume = _DEFAULT_VOLUME
        else:
            if not _ensure_finite(volume) or volume < 0 and abs(volume - _DEFAULT_VOLUME) > _EPSILON:
                issues.append(
                    ValidationIssue(
                        index=index,
                        field="volume",
                        code="NEGATIVE_VOLUME",
                        message="volume must be non-negative",
                    )
                )
                fatal = True

        symbol_key = (market, symbol) if symbol else None

        if enforce_monotonic_ts and not fatal and symbol_key:
            previous = last_ts_by_symbol.get(symbol_key)
            if previous is not None and timestamp < previous:
                issues.append(
                    ValidationIssue(
                        index=index,
                        field="timestamp",
                        code="NON_MONOTONIC_TIMESTAMP",
                        message="timestamps must be non-decreasing per symbol",
                    )
                )
                fatal = True
            else:
                last_ts_by_symbol[symbol_key] = timestamp
        elif symbol_key and timestamp is not None:
            last_ts_by_symbol[symbol_key] = timestamp

        if not fatal:
            sanitised = RawRecord(
                supplier_symbol=symbol,
                timestamp=timestamp,
                open=record.open,
                high=record.high,
                low=record.low,
                close=record.close,
                volume=volume,
                provider=record.provider,
            )
            validated.append(ValidatedRecord(index=index, record=sanitised))

    return validated, issues
