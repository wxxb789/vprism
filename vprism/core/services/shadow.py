"""Shadow controller orchestrating dual-path execution and persistence."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from threading import Lock
from uuid import uuid4

from vprism.core.data.schema import vprism_shadow_runs_table
from vprism.core.exceptions import DomainError
from vprism.core.exceptions.codes import ErrorCode

from .shadow_diff import DiffEngine, ShadowDiffResult, ShadowDiffStatus, ShadowRecord

try:  # pragma: no cover - duckdb is optional during import time
    from duckdb import DuckDBPyConnection
except Exception:  # pragma: no cover
    DuckDBPyConnection = "DuckDBPyConnection"  # type: ignore[misc,assignment]


ShadowExecutor = Callable[["ShadowRunConfig"], Sequence[ShadowRecord]]
ShadowRunWriter = Callable[["ShadowRunSummary"], None]
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class ShadowRunConfig:
    """Parameters describing a single shadow comparison run."""

    asset: str
    markets: Sequence[str]
    start: date
    end: date
    sample_percent: float = 100.0
    lookback_days: int = 30
    force_full_run: bool = False
    run_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "markets", tuple(self.markets))


@dataclass(frozen=True)
class ShadowRunSummary:
    """Persisted metrics summarising a shadow run."""

    run_id: str
    start: date
    end: date
    asset: str
    markets: tuple[str, ...]
    created_at: datetime
    row_diff_pct: float
    price_diff_bp_p95: float
    gap_ratio: float
    status: ShadowDiffStatus
    sample_percent: float
    lookback_days: int
    force_full_run: bool
    primary_duration_ms: float
    candidate_duration_ms: float


@dataclass(frozen=True)
class ShadowRunResult:
    """Return value for :meth:`ShadowController.run`."""

    run_id: str
    sampled: bool
    primary_result: Sequence[ShadowRecord]
    summary: ShadowRunSummary | None
    diff: ShadowDiffResult | None


@dataclass(frozen=True)
class ShadowControllerState:
    """Snapshot describing controller state for CLI consumption."""

    active_mode: str
    ready_for_promote: bool
    consecutive_passes: int
    last_summary: ShadowRunSummary | None


class ShadowSamplingPolicy:
    """Determine when requests should execute in shadow mode."""

    def __init__(
        self,
        *,
        default_sample_percent: float = 10.0,
        random_func: Callable[[], float] | None = None,
    ) -> None:
        self._default = max(0.0, min(default_sample_percent, 100.0))
        self._random = random_func or __import__("random").random

    def should_sample(self, config: ShadowRunConfig) -> bool:
        if config.force_full_run:
            return True
        percent = max(0.0, min(config.sample_percent, 100.0))
        if percent >= 100.0:
            return True
        if percent <= 0.0:
            return False
        return self._random() * 100.0 < percent


class ShadowPromoteGuard:
    """Track consecutive PASS runs before allowing promotion."""

    def __init__(self, required_passes: int = 3) -> None:
        if required_passes < 1:
            msg = "required_passes must be at least one"
            raise ValueError(msg)
        self._required = required_passes
        self._consecutive = 0
        self._ready = False
        self._lock = Lock()

    def observe(self, status: ShadowDiffStatus) -> None:
        with self._lock:
            if status is ShadowDiffStatus.PASS:
                self._consecutive += 1
            else:
                self._consecutive = 0
            self._ready = self._consecutive >= self._required

    def configure(self, required_passes: int) -> None:
        if required_passes < 1:
            msg = "required_passes must be at least one"
            raise ValueError(msg)
        with self._lock:
            self._required = required_passes
            self._consecutive = 0
            self._ready = False

    @property
    def ready(self) -> bool:
        with self._lock:
            return self._ready

    @property
    def consecutive_passes(self) -> int:
        with self._lock:
            return self._consecutive


class DuckDBShadowRunWriter:
    """Persist :class:`ShadowRunSummary` rows into DuckDB."""

    def __init__(self, connection: DuckDBPyConnection) -> None:
        self._connection = connection
        vprism_shadow_runs_table.ensure(connection)

    def __call__(self, summary: ShadowRunSummary) -> None:
        markets = ",".join(summary.markets)
        self._connection.execute(
            """
            INSERT INTO shadow_runs
            (run_id, "start", "end", asset, markets, created_at, row_diff_pct,
             price_diff_bp_p95, gap_ratio, status, sample_percent, lookback_days, force_full_run,
             primary_duration_ms, candidate_duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                summary.run_id,
                summary.start,
                summary.end,
                summary.asset,
                markets,
                summary.created_at,
                summary.row_diff_pct,
                summary.price_diff_bp_p95,
                summary.gap_ratio,
                summary.status.value,
                summary.sample_percent,
                summary.lookback_days,
                summary.force_full_run,
                summary.primary_duration_ms,
                summary.candidate_duration_ms,
            ],
        )


class ShadowController:
    """Coordinate dual-path execution, diffing, and persistence."""

    def __init__(
        self,
        primary_executor: ShadowExecutor,
        candidate_executor: ShadowExecutor,
        *,
        diff_engine: DiffEngine | None = None,
        sampling_policy: ShadowSamplingPolicy | None = None,
        run_writer: ShadowRunWriter | None = None,
        promote_guard: ShadowPromoteGuard | None = None,
        executor: Executor | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._baseline_executor = primary_executor
        self._candidate_executor = candidate_executor
        self._diff_engine = diff_engine or DiffEngine()
        self._sampling_policy = sampling_policy or ShadowSamplingPolicy()
        self._run_writer = run_writer
        self._promote_guard = promote_guard or ShadowPromoteGuard()
        self._executor = executor or ThreadPoolExecutor(max_workers=2)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = Lock()
        self._last_summary: ShadowRunSummary | None = None
        self._pending_runs: dict[str, Future[ShadowDiffResult | None]] = {}
        self._active_mode = "primary"

    def run(
        self,
        config: ShadowRunConfig,
        *,
        wait_for_shadow: bool = False,
    ) -> ShadowRunResult:
        run_id = config.run_id or uuid4().hex
        active_executor = self._resolve_active_executor()
        shadow_executor = self._resolve_shadow_executor()

        primary_start = self._clock()
        primary_result = tuple(active_executor(config))
        primary_duration_ms = (self._clock() - primary_start).total_seconds() * 1000.0

        should_sample = self._sampling_policy.should_sample(config)
        diff_result: ShadowDiffResult | None = None
        summary: ShadowRunSummary | None = None

        if should_sample:
            if wait_for_shadow:
                candidate_result, candidate_duration_ms = self._execute_shadow(shadow_executor, config)
                diff_result, summary = self._finalize_run(
                    run_id,
                    config,
                    primary_result,
                    candidate_result,
                    primary_duration_ms,
                    candidate_duration_ms,
                )
            else:
                future = self._executor.submit(
                    self._async_shadow,
                    run_id,
                    config,
                    primary_result,
                    primary_duration_ms,
                    shadow_executor,
                )
                with self._lock:
                    self._pending_runs[run_id] = future
        else:
            summary = self._build_summary(
                run_id,
                config,
                primary_duration_ms=primary_duration_ms,
                candidate_duration_ms=0.0,
                diff_result=None,
            )
            self._update_state(summary, diff_result=None)

        return ShadowRunResult(
            run_id=run_id,
            sampled=should_sample,
            primary_result=primary_result,
            summary=summary if summary is not None else None,
            diff=diff_result,
        )

    def wait_for_run(self, run_id: str, timeout: float | None = None) -> ShadowRunSummary | None:
        with self._lock:
            future = self._pending_runs.get(run_id)
        if future is None:
            return None
        future.result(timeout)
        with self._lock:
            return self._last_summary

    def promote(self, *, force: bool = False) -> None:
        if not force and not self._promote_guard.ready:
            raise DomainError(
                "Shadow controller is not ready for promotion.",
                ErrorCode.VALIDATION,
                layer="shadow.promote",
            )
        self._active_mode = "candidate"

    def rollback(self) -> None:
        self._active_mode = "primary"

    def state(self) -> ShadowControllerState:
        with self._lock:
            summary = self._last_summary
        return ShadowControllerState(
            active_mode=self._active_mode,
            ready_for_promote=self._promote_guard.ready,
            consecutive_passes=self._promote_guard.consecutive_passes,
            last_summary=summary,
        )

    def _async_shadow(
        self,
        run_id: str,
        config: ShadowRunConfig,
        primary_result: Sequence[ShadowRecord],
        primary_duration_ms: float,
        shadow_executor: ShadowExecutor,
    ) -> ShadowDiffResult | None:
        candidate_result, candidate_duration_ms = self._execute_shadow(shadow_executor, config)
        diff_result, summary = self._finalize_run(
            run_id,
            config,
            primary_result,
            candidate_result,
            primary_duration_ms,
            candidate_duration_ms,
        )
        with self._lock:
            self._pending_runs.pop(run_id, None)
        return diff_result

    def _execute_shadow(
        self,
        executor: ShadowExecutor,
        config: ShadowRunConfig,
    ) -> tuple[tuple[ShadowRecord, ...], float]:
        start_time = self._clock()
        result = tuple(executor(config))
        duration_ms = (self._clock() - start_time).total_seconds() * 1000.0
        return result, duration_ms

    def _finalize_run(
        self,
        run_id: str,
        config: ShadowRunConfig,
        primary_result: Sequence[ShadowRecord],
        candidate_result: Sequence[ShadowRecord],
        primary_duration_ms: float,
        candidate_duration_ms: float,
    ) -> tuple[ShadowDiffResult, ShadowRunSummary]:
        diff_result = self._diff_engine.compare(primary_result, candidate_result)
        summary = self._build_summary(
            run_id,
            config,
            primary_duration_ms=primary_duration_ms,
            candidate_duration_ms=candidate_duration_ms,
            diff_result=diff_result,
        )
        self._update_state(summary, diff_result=diff_result)
        return diff_result, summary

    def _build_summary(
        self,
        run_id: str,
        config: ShadowRunConfig,
        *,
        primary_duration_ms: float,
        candidate_duration_ms: float,
        diff_result: ShadowDiffResult | None,
    ) -> ShadowRunSummary:
        status = diff_result.status if diff_result else ShadowDiffStatus.PASS
        return ShadowRunSummary(
            run_id=run_id,
            start=config.start,
            end=config.end,
            asset=config.asset,
            markets=tuple(config.markets),
            created_at=self._clock(),
            row_diff_pct=diff_result.row_diff_pct if diff_result else 0.0,
            price_diff_bp_p95=diff_result.price_diff_bp_p95 if diff_result else 0.0,
            gap_ratio=diff_result.gap_ratio if diff_result else 0.0,
            status=status,
            sample_percent=max(0.0, min(config.sample_percent, 100.0)),
            lookback_days=config.lookback_days,
            force_full_run=config.force_full_run,
            primary_duration_ms=primary_duration_ms,
            candidate_duration_ms=candidate_duration_ms,
        )

    def _update_state(
        self,
        summary: ShadowRunSummary,
        *,
        diff_result: ShadowDiffResult | None,
    ) -> None:
        with self._lock:
            self._last_summary = summary
        if diff_result is not None:
            self._promote_guard.observe(diff_result.status)
        if self._run_writer and diff_result is not None:
            self._run_writer(summary)

    def _resolve_active_executor(self) -> ShadowExecutor:
        if self._active_mode == "candidate":
            return self._candidate_executor
        return self._baseline_executor

    def _resolve_shadow_executor(self) -> ShadowExecutor:
        if self._active_mode == "candidate":
            return self._baseline_executor
        return self._candidate_executor


def get_shadow_controller() -> ShadowController:
    """Factory method intended for dependency injection."""

    raise RuntimeError("Shadow controller is not configured")


__all__ = [
    "Clock",
    "DuckDBShadowRunWriter",
    "ShadowController",
    "ShadowControllerState",
    "ShadowExecutor",
    "ShadowPromoteGuard",
    "ShadowRunConfig",
    "ShadowRunResult",
    "ShadowRunSummary",
    "ShadowSamplingPolicy",
    "get_shadow_controller",
]
