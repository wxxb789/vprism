from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, date

import pytest
from typer.testing import CliRunner

from vprism.cli import shadow as shadow_module
from vprism.cli.main import create_app
from vprism.cli.constants import VALIDATION_EXIT_CODE
from vprism.core.services.shadow import (
    ShadowController,
    ShadowPromoteGuard,
    ShadowRunConfig,
    ShadowRunSummary,
    ShadowSamplingPolicy,
)
from vprism.core.services.shadow_diff import DiffEngine, ShadowRecord


class FakeClock:
    def __init__(self) -> None:
        self._current = datetime(2024, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        value = self._current
        self._current += timedelta(milliseconds=25)
        return value


def _make_record(offset: int, close: float) -> ShadowRecord:
    timestamp = datetime(2024, 1, 1 + offset, tzinfo=UTC)
    return ShadowRecord(symbol="asset-1", market="cn", timestamp=timestamp, close=close)


def _primary(_: ShadowRunConfig) -> tuple[ShadowRecord, ...]:
    return (_make_record(0, 10.0), _make_record(1, 10.2))


def _candidate(_: ShadowRunConfig) -> tuple[ShadowRecord, ...]:
    return (_make_record(0, 10.05), _make_record(1, 10.25))


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def configure_controller(monkeypatch: pytest.MonkeyPatch) -> Callable[..., ShadowController]:
    def _configure(*, guard_passes: int = 1) -> ShadowController:
        summaries: list[ShadowRunSummary] = []
        controller = ShadowController(
            _primary,
            _candidate,
            diff_engine=DiffEngine(),
            sampling_policy=ShadowSamplingPolicy(default_sample_percent=100.0),
            run_writer=summaries.append,
            promote_guard=ShadowPromoteGuard(required_passes=guard_passes),
            clock=FakeClock(),
        )
        monkeypatch.setattr(shadow_module, "get_shadow_controller", lambda: controller)
        return controller

    return _configure


def test_shadow_run_command_outputs_summary(runner: CliRunner, configure_controller: Callable[..., ShadowController]) -> None:
    configure_controller()
    app = create_app()

    result = runner.invoke(
        app,
        [
            "--format",
            "jsonl",
            "shadow",
            "run",
            "asset-1",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-02",
        ],
    )

    assert result.exit_code == 0, result.output
    payloads = [json.loads(line) for line in result.output.strip().splitlines()]
    assert payloads
    assert payloads[0]["status"] == "PASS"
    assert "row_diff_pct" in payloads[0]


def test_shadow_status_command_shows_state(
    runner: CliRunner, configure_controller: Callable[..., ShadowController]
) -> None:
    controller = configure_controller()
    controller.run(
        ShadowRunConfig(
            asset="asset-1",
            markets=("cn",),
            start=date(2024, 1, 1),
            end=date(2024, 1, 2),
            sample_percent=100.0,
        ),
        wait_for_shadow=True,
    )
    app = create_app()

    result = runner.invoke(app, ["--format", "jsonl", "shadow", "status"])

    assert result.exit_code == 0
    json_payloads: list[dict[str, object]] = []
    state_lines: list[str] = []
    for line in result.output.strip().splitlines():
        if line.startswith("active_mode=") or line.startswith("ready_for_promote=") or line.startswith("consecutive_passes="):
            state_lines.append(line)
        elif line:
            json_payloads.append(json.loads(line))
    assert json_payloads
    assert json_payloads[0]["status"] == "PASS"
    assert any(item.startswith("active_mode=") for item in state_lines)


def test_shadow_promote_command_respects_guard(
    runner: CliRunner, configure_controller: Callable[..., ShadowController]
) -> None:
    configure_controller(guard_passes=2)
    app = create_app()

    result = runner.invoke(app, ["shadow", "promote"])

    assert result.exit_code == VALIDATION_EXIT_CODE
    assert "Shadow controller is not ready" in result.stderr

    force_result = runner.invoke(app, ["shadow", "promote", "--force"])
    assert force_result.exit_code == 0
    assert "Shadow path promoted." in force_result.output
