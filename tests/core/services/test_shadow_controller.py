from __future__ import annotations

from datetime import UTC, datetime, timedelta, date

import pytest

from vprism.core.exceptions import DomainError
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
        self._current += timedelta(milliseconds=50)
        return value


def _make_record(offset: int, close: float) -> ShadowRecord:
    timestamp = datetime(2024, 1, 1 + offset, tzinfo=UTC)
    return ShadowRecord(symbol="asset-1", market="cn", timestamp=timestamp, close=close)


def _primary_executor(_: ShadowRunConfig) -> tuple[ShadowRecord, ...]:
    return (
        _make_record(0, 10.0),
        _make_record(1, 10.5),
    )


def _candidate_executor(_: ShadowRunConfig) -> tuple[ShadowRecord, ...]:
    return (
        _make_record(0, 10.1),
        _make_record(1, 10.45),
    )


def test_shadow_controller_run_waits_and_persists() -> None:
    clock = FakeClock()
    summaries: list[ShadowRunSummary] = []
    controller = ShadowController(
        _primary_executor,
        _candidate_executor,
        diff_engine=DiffEngine(),
        sampling_policy=ShadowSamplingPolicy(default_sample_percent=100.0),
        run_writer=summaries.append,
        promote_guard=ShadowPromoteGuard(required_passes=2),
        clock=clock,
    )

    config = ShadowRunConfig(
        asset="asset-1",
        markets=("cn",),
        start=date(2024, 1, 1),
        end=date(2024, 1, 5),
        sample_percent=100.0,
    )

    result = controller.run(config, wait_for_shadow=True)

    assert result.sampled is True
    assert result.summary is not None
    assert result.diff is not None
    assert summaries and summaries[0].run_id == result.run_id
    state = controller.state()
    assert state.consecutive_passes == 1
    assert state.ready_for_promote is False


def test_shadow_controller_handles_non_sampled_runs() -> None:
    controller = ShadowController(
        _primary_executor,
        _candidate_executor,
        diff_engine=DiffEngine(),
        sampling_policy=ShadowSamplingPolicy(default_sample_percent=0.0),
        promote_guard=ShadowPromoteGuard(required_passes=1),
    )

    config = ShadowRunConfig(
        asset="asset-2",
        markets=("us",),
        start=date(2024, 2, 1),
        end=date(2024, 2, 2),
        sample_percent=0.0,
    )

    result = controller.run(config, wait_for_shadow=True)

    assert result.sampled is False
    assert result.summary is not None
    assert result.diff is None


def test_shadow_controller_async_completion_and_promote_guard() -> None:
    clock = FakeClock()
    summaries: list[ShadowRunSummary] = []
    guard = ShadowPromoteGuard(required_passes=2)
    controller = ShadowController(
        _primary_executor,
        _candidate_executor,
        diff_engine=DiffEngine(),
        sampling_policy=ShadowSamplingPolicy(default_sample_percent=100.0),
        run_writer=summaries.append,
        promote_guard=guard,
        clock=clock,
    )

    config = ShadowRunConfig(
        asset="asset-3",
        markets=("cn",),
        start=date(2024, 3, 1),
        end=date(2024, 3, 2),
        sample_percent=100.0,
    )

    result = controller.run(config, wait_for_shadow=False)

    assert result.summary is None
    controller.wait_for_run(result.run_id)
    assert summaries and summaries[0].run_id == result.run_id

    with pytest.raises(DomainError):
        controller.promote()

    controller.promote(force=True)
    assert controller.state().active_mode == "candidate"
    controller.rollback()
    assert controller.state().active_mode == "primary"
