from __future__ import annotations

from datetime import UTC, datetime
from math import inf, nan

from vprism.core.data.ingestion.models import RawRecord
from vprism.core.data.ingestion.validator import validate_batch


def _make_record(**overrides: object) -> RawRecord:
    base = RawRecord(
        supplier_symbol="000001",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        open=10.0,
        high=11.0,
        low=9.5,
        close=10.5,
        volume=100.0,
        provider="akshare",
    )
    for field, value in overrides.items():
        setattr(base, field, value)
    return base


def test_validate_batch_accepts_valid_rows() -> None:
    record = _make_record()

    validated, issues = validate_batch([record], market="CN")

    assert len(validated) == 1
    assert not issues


def test_missing_volume_defaulted_to_minus_one() -> None:
    record = _make_record(volume=None)

    validated, issues = validate_batch([record], market="CN")

    assert len(validated) == 1
    assert validated[0].record.volume == -1.0
    assert any(issue.code == "MISSING_VOLUME_DEFAULTED" and not issue.fatal for issue in issues)


def test_missing_numeric_field_is_fatal() -> None:
    record = _make_record(open=None)

    validated, issues = validate_batch([record], market="CN")

    assert not validated
    assert any(issue.code == "MISSING_FIELD" and issue.field == "open" for issue in issues)


def test_non_finite_values_are_rejected() -> None:
    record_nan = _make_record(close=nan)
    record_inf = _make_record(low=-inf)

    validated, issues = validate_batch([record_nan, record_inf], market="CN")

    assert not validated
    assert sum(1 for issue in issues if issue.code == "NON_FINITE_VALUE") == 2


def test_ohlc_relationship_violations_detected() -> None:
    record = _make_record(low=11.2)

    validated, issues = validate_batch([record], market="CN")

    assert not validated
    assert any(issue.code == "LOW_ABOVE_HIGH" for issue in issues)


def test_negative_volume_rejected() -> None:
    record = _make_record(volume=-2.0)

    validated, issues = validate_batch([record], market="CN")

    assert not validated
    assert any(issue.code == "NEGATIVE_VOLUME" for issue in issues)


def test_non_monotonic_timestamp_rejected_when_enforced() -> None:
    first = _make_record(timestamp=datetime(2024, 1, 2, tzinfo=UTC))
    second = _make_record(timestamp=datetime(2024, 1, 1, tzinfo=UTC))

    validated, issues = validate_batch([first, second], market="CN", enforce_monotonic_ts=True)

    assert len(validated) == 1
    assert any(issue.code == "NON_MONOTONIC_TIMESTAMP" for issue in issues)


def test_non_monotonic_timestamp_allowed_when_not_enforced() -> None:
    first = _make_record(timestamp=datetime(2024, 1, 2, tzinfo=UTC))
    second = _make_record(timestamp=datetime(2024, 1, 1, tzinfo=UTC))

    validated, issues = validate_batch([first, second], market="CN", enforce_monotonic_ts=False)

    assert len(validated) == 2
    assert not any(issue.code == "NON_MONOTONIC_TIMESTAMP" for issue in issues)
