"""Tests for the DomainError hierarchy."""

from __future__ import annotations

import pytest

from vprism.core.exceptions.codes import ErrorCode
from vprism.core.exceptions.domain import DomainError


@pytest.mark.parametrize(
    "code",
    [
        ErrorCode.VALIDATION,
        ErrorCode.ROUTING,
        ErrorCode.PROVIDER,
        ErrorCode.DATA_QUALITY,
        ErrorCode.RECONCILE,
        ErrorCode.SYSTEM,
    ],
)
def test_domain_error_preserves_error_code(code: ErrorCode) -> None:
    """DomainError should expose the code and propagate it to base attributes."""

    error = DomainError("boom", code=code, layer="ingest", retryable=False, context=None)

    assert error.code is code
    assert error.error_code == code.value
    assert error.details["layer"] == "ingest"
    assert error.details["retryable"] is False


def test_domain_error_context_is_copied() -> None:
    """Mutating input context after construction must not affect stored context."""

    context = {"symbol": "AAPL", "market": "NASDAQ"}
    error = DomainError("validation failed", ErrorCode.VALIDATION, layer="normalizer", retryable=True, context=context)

    # mutate original context to ensure defensive copy
    context["symbol"] = "TSLA"

    assert error.context == {"symbol": "AAPL", "market": "NASDAQ"}
    assert error.details["symbol"] == "AAPL"
    assert error.details["retryable"] is True
    assert error.layer == "normalizer"
    assert error.retryable is True
