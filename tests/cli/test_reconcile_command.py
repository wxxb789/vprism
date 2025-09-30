from datetime import UTC, datetime, date
from decimal import Decimal
from typing import Sequence

import pytest
from typer.testing import CliRunner

from vprism.cli import reconciliation as reconciliation_module
from vprism.cli.main import create_app
from vprism.core.exceptions.base import ReconciliationError
from vprism.core.models.market import MarketType
from vprism.core.services.reconciliation import (
    ReconcileResult,
    ReconciliationSample,
    ReconciliationStatus,
    ReconciliationSummary,
)


class StubReconciliationService:
    def __init__(self, result: ReconcileResult, *, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[dict[str, object]] = []

    def reconcile(
        self,
        symbols: Sequence[str],
        market: MarketType,
        date_range: tuple[date, date],
        sample_size: int | None = None,
    ) -> ReconcileResult:
        self.calls.append(
            {
                "symbols": list(symbols),
                "market": market,
                "date_range": date_range,
                "sample_size": sample_size,
            }
        )
        if self._error:
            raise self._error
        return self._result


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _build_result() -> ReconcileResult:
    summary = ReconciliationSummary(
        market=MarketType.CN,
        start=date(2024, 1, 1),
        end=date(2024, 1, 3),
        source_a="akshare",
        source_b="yfinance",
        sample_size=2,
        pass_count=1,
        warn_count=0,
        fail_count=1,
        p95_close_bp_diff=Decimal("12.5"),
    )
    samples = (
        ReconciliationSample(
            symbol="AAA",
            date=date(2024, 1, 1),
            close_a=Decimal("100"),
            close_b=Decimal("101"),
            close_bp_diff=Decimal("-99.0"),
            volume_a=Decimal("1000"),
            volume_b=Decimal("900"),
            volume_ratio=Decimal("1.11"),
            status=ReconciliationStatus.FAIL,
        ),
        ReconciliationSample(
            symbol="BBB",
            date=date(2024, 1, 2),
            close_a=Decimal("100"),
            close_b=Decimal("100"),
            close_bp_diff=Decimal("0"),
            volume_a=Decimal("1000"),
            volume_b=Decimal("1000"),
            volume_ratio=Decimal("1"),
            status=ReconciliationStatus.PASS,
        ),
    )
    return ReconcileResult(
        run_id="run-xyz",
        created_at=datetime(2024, 1, 3, 12, 0, tzinfo=UTC),
        summary=summary,
        sampled_symbols=("AAA", "BBB"),
        samples=samples,
    )


def test_run_command_outputs_summary_and_failures(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _build_result()
    stub = StubReconciliationService(result)
    monkeypatch.setattr(reconciliation_module, "get_reconciliation_service", lambda: stub)

    app = create_app()
    cli_result = runner.invoke(
        app,
        [
            "reconcile",
            "run",
            "AAA",
            "BBB",
            "--market",
            "cn",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-03",
            "--sample-size",
            "25",
            "--limit",
            "5",
        ],
    )

    assert cli_result.exit_code == 0, cli_result.output
    assert "run-xyz" in cli_result.output
    assert "p95_close_bp_diff" in cli_result.output
    assert "FAIL" in cli_result.output
    assert stub.calls == [
        {
            "symbols": ["AAA", "BBB"],
            "market": MarketType.CN,
            "date_range": (date(2024, 1, 1), date(2024, 1, 3)),
            "sample_size": 25,
        }
    ]


def test_run_command_validates_dates(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _build_result()
    stub = StubReconciliationService(result)
    monkeypatch.setattr(reconciliation_module, "get_reconciliation_service", lambda: stub)

    app = create_app()
    cli_result = runner.invoke(
        app,
        [
            "reconcile",
            "run",
            "AAA",
            "--start",
            "2024-02-02",
            "--end",
            "2024-01-01",
        ],
    )

    assert cli_result.exit_code == 10
    assert "INVALID_DATE_RANGE" in cli_result.stderr


def test_run_command_handles_reconciliation_error(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    error = ReconciliationError("failed", symbol="AAA", details={"reason": "missing"})
    result = _build_result()
    stub = StubReconciliationService(result, error=error)
    monkeypatch.setattr(reconciliation_module, "get_reconciliation_service", lambda: stub)

    app = create_app()
    cli_result = runner.invoke(
        app,
        [
            "reconcile",
            "run",
            "AAA",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-02",
        ],
    )

    assert cli_result.exit_code == 40
    assert "RECONCILIATION_ERROR" in cli_result.stderr
