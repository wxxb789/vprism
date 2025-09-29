from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from vprism.cli import drift as drift_module
from vprism.cli.main import create_app
from vprism.core.data.schema import VPrismQualityMetricStatus
from vprism.core.exceptions import DriftComputationError
from vprism.core.models.market import MarketType
from vprism.core.services.drift import DriftMetric, DriftResult


class StubDriftService:
    def __init__(self, result: DriftResult, *, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[dict[str, object]] = []

    def compute(
        self,
        *,
        symbol: str,
        market: MarketType,
        window: int,
        run_id: str | None = None,
    ) -> DriftResult:
        self.calls.append({"symbol": symbol, "market": market, "window": window, "run_id": run_id})
        if self._error:
            raise self._error
        return self._result


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _build_result() -> DriftResult:
    metrics = (
        DriftMetric("close_mean", Decimal("10"), VPrismQualityMetricStatus.OK),
        DriftMetric("close_std", Decimal("1"), VPrismQualityMetricStatus.OK),
        DriftMetric("volume_mean", Decimal("100"), VPrismQualityMetricStatus.OK),
        DriftMetric("volume_std", Decimal("10"), VPrismQualityMetricStatus.OK),
        DriftMetric("zscore_latest_close", Decimal("2"), VPrismQualityMetricStatus.WARN),
        DriftMetric("zscore_latest_volume", Decimal("0.5"), VPrismQualityMetricStatus.OK),
    )
    return DriftResult(
        symbol="000001",
        market=MarketType.CN,
        window=5,
        metrics=metrics,
        latest_timestamp=datetime(2024, 1, 5, 15, 30, 0),
        run_id="run-123",
    )


def test_report_table_output(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _build_result()
    stub = StubDriftService(result)
    monkeypatch.setattr(drift_module, "get_drift_service", lambda: stub)

    app = create_app()
    cli_result = runner.invoke(app, ["drift", "report", "000001", "--market", "cn", "--window", "5"])

    assert cli_result.exit_code == 0, cli_result.output
    assert "zscore_latest_close" in cli_result.output
    assert "WARN" in cli_result.output
    assert stub.calls == [
        {"symbol": "000001", "market": MarketType.CN, "window": 5, "run_id": None}
    ]


def test_report_jsonl_output(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _build_result()
    stub = StubDriftService(result)
    monkeypatch.setattr(drift_module, "get_drift_service", lambda: stub)

    app = create_app()
    cli_result = runner.invoke(app, ["--format", "jsonl", "drift", "report", "000001"])

    assert cli_result.exit_code == 0, cli_result.output
    payloads = [json.loads(line) for line in cli_result.output.strip().splitlines()]
    assert any(item["metric"] == "zscore_latest_close" for item in payloads)
    assert all(item["run_id"] == "run-123" for item in payloads)


def test_report_handles_invalid_window(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _build_result()
    stub = StubDriftService(result)
    monkeypatch.setattr(drift_module, "get_drift_service", lambda: stub)

    app = create_app()
    cli_result = runner.invoke(app, ["drift", "report", "000001", "--window", "1"])

    assert cli_result.exit_code == 10
    assert "INVALID_WINDOW" in cli_result.stderr


def test_report_emits_data_quality_error(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    error = DriftComputationError(
        "insufficient data",
        symbol="000001",
        market=MarketType.CN.value,
        details={"window": 5},
    )
    result = _build_result()
    stub = StubDriftService(result, error=error)
    monkeypatch.setattr(drift_module, "get_drift_service", lambda: stub)

    app = create_app()
    cli_result = runner.invoke(app, ["drift", "report", "000001", "--window", "5"])

    assert cli_result.exit_code == 30
    assert "DRIFT_COMPUTATION_ERROR" in cli_result.stderr
