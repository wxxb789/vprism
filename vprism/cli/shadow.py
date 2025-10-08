"""Shadow deployment management commands."""

from __future__ import annotations

from datetime import date

import typer

from vprism.core.exceptions import DomainError
from vprism.core.services.shadow import (
    ShadowController,
    ShadowRunConfig,
    ShadowRunSummary,
    get_shadow_controller,
)

from .constants import SYSTEM_EXIT_CODE, VALIDATION_EXIT_CODE
from .utils import emit_error, prepare_output


shadow_app = typer.Typer(help="Manage shadow runs and promotion workflow.")

SHADOW_RUN_COLUMNS = [
    "run_id",
    "status",
    "row_diff_pct",
    "price_diff_bp_p95",
    "gap_ratio",
    "sample_percent",
    "lookback_days",
    "force_full_run",
    "primary_duration_ms",
    "candidate_duration_ms",
    "created_at",
]


def register(app: typer.Typer) -> None:
    """Register shadow commands on the root CLI application."""

    app.add_typer(shadow_app, name="shadow", help="Operate the shadow controller")


def _parse_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - validated via typer error path
        raise typer.BadParameter(f"Invalid date format for {name}. Use YYYY-MM-DD.") from exc


@shadow_app.command("run")
def run_command(
    ctx: typer.Context,
    asset: str = typer.Argument(..., help="Asset identifier to execute shadow run for."),
    start: str = typer.Option(..., help="Inclusive start date (YYYY-MM-DD)."),
    end: str = typer.Option(..., help="Inclusive end date (YYYY-MM-DD)."),
    market: list[str] = typer.Option(
        ["cn"],
        "--market",
        "-m",
        help="Market codes to include. Multiple options allowed.",
    ),
    sample_percent: float = typer.Option(100.0, help="Sampling percentage for this run."),
    lookback_days: int = typer.Option(30, help="Lookback window in days."),
    force_full_run: bool = typer.Option(False, help="Force full run irrespective of sampling."),
    wait: bool = typer.Option(True, help="Wait for diff completion before returning."),
) -> None:
    """Trigger a shadow run and render the resulting metrics."""

    controller = _resolve_controller()
    formatter, stream, stack, _ = prepare_output(ctx)

    run_config = ShadowRunConfig(
        asset=asset,
        markets=tuple(market) if market else ("cn",),
        start=_parse_date(start, "start"),
        end=_parse_date(end, "end"),
        sample_percent=sample_percent,
        lookback_days=lookback_days,
        force_full_run=force_full_run,
    )

    result = controller.run(run_config, wait_for_shadow=wait)
    summary = result.summary
    if summary is None:
        summary = controller.wait_for_run(result.run_id)
    if summary is None:
        stack.close()
        typer.echo("Shadow run dispatched.")
        return

    try:
        formatter.render([
            _summary_to_row(summary),
        ], stream=stream, columns=SHADOW_RUN_COLUMNS)
    finally:
        stack.close()


@shadow_app.command("status")
def status_command(ctx: typer.Context) -> None:
    """Display current controller state and last run metrics."""

    controller = _resolve_controller()
    state = controller.state()
    formatter, stream, stack, _ = prepare_output(ctx)
    try:
        rows = []
        if state.last_summary is not None:
            rows.append(_summary_to_row(state.last_summary))
        formatter.render(rows, stream=stream, columns=SHADOW_RUN_COLUMNS)
    finally:
        stack.close()

    typer.echo(f"active_mode={state.active_mode}")
    typer.echo(f"ready_for_promote={state.ready_for_promote}")
    typer.echo(f"consecutive_passes={state.consecutive_passes}")


@shadow_app.command("promote")
def promote_command(
    force: bool = typer.Option(False, "--force", help="Bypass readiness guard."),
) -> None:
    """Promote the shadow path to active production."""

    controller = _resolve_controller()
    try:
        controller.promote(force=force)
    except DomainError as exc:
        emit_error(exc.message, exc.error_code, details=exc.details)
        raise typer.Exit(code=VALIDATION_EXIT_CODE) from exc

    typer.echo("Shadow path promoted.")


@shadow_app.command("rollback")
def rollback_command() -> None:
    """Rollback to the primary path."""

    controller = _resolve_controller()
    controller.rollback()
    typer.echo("Shadow path rolled back.")


@shadow_app.command("diff")
def diff_command(ctx: typer.Context) -> None:
    """Render the latest diff metrics if available."""

    controller = _resolve_controller()
    state = controller.state()
    if state.last_summary is None:
        typer.echo("No shadow runs recorded yet.")
        return

    formatter, stream, stack, _ = prepare_output(ctx)
    try:
        formatter.render([
            _summary_to_row(state.last_summary),
        ], stream=stream, columns=SHADOW_RUN_COLUMNS)
    finally:
        stack.close()


def _summary_to_row(summary: ShadowRunSummary) -> dict[str, object]:
    return {
        "run_id": summary.run_id,
        "status": summary.status.value,
        "row_diff_pct": summary.row_diff_pct,
        "price_diff_bp_p95": summary.price_diff_bp_p95,
        "gap_ratio": summary.gap_ratio,
        "sample_percent": summary.sample_percent,
        "lookback_days": summary.lookback_days,
        "force_full_run": summary.force_full_run,
        "primary_duration_ms": summary.primary_duration_ms,
        "candidate_duration_ms": summary.candidate_duration_ms,
        "created_at": summary.created_at.isoformat(),
    }


def _resolve_controller() -> ShadowController:
    controller = get_shadow_controller()
    if controller is None:  # pragma: no cover - defensive
        emit_error("Shadow controller not configured", "SHADOW_NOT_CONFIGURED")
        raise typer.Exit(code=SYSTEM_EXIT_CODE)
    return controller


__all__ = ["SHADOW_RUN_COLUMNS", "diff_command", "promote_command", "register", "rollback_command", "run_command", "status_command"]
