from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

import typer

from vprism.core.exceptions.base import ReconciliationError, VPrismError
from vprism.core.models.market import MarketType
from vprism.core.services.reconciliation import (
    ReconcileResult,
    ReconciliationService,
    ReconciliationSample,
    ReconciliationStatus,
)

from .constants import RECONCILE_EXIT_CODE, SYSTEM_EXIT_CODE, VALIDATION_EXIT_CODE
from .utils import emit_error, prepare_output


reconcile_app = typer.Typer(help="Reconciliation operations.")

SUMMARY_COLUMNS = ["metric", "value"]
DIFF_COLUMNS = ["symbol", "date", "close_bp_diff", "volume_ratio", "status"]


def register(app: typer.Typer) -> None:
    """Register reconciliation commands on the provided application."""

    app.add_typer(reconcile_app, name="reconcile", help="Run reconciliation sampling")


def get_reconciliation_service() -> ReconciliationService:
    """Factory hook for obtaining a reconciliation service instance."""

    raise NotImplementedError("Reconciliation service wiring not configured.")


@reconcile_app.command("run")
def run_command(
    ctx: typer.Context,
    symbols: list[str] = typer.Argument(..., metavar="SYMBOL...", help="Symbols to sample during reconciliation."),
    market: str = typer.Option("cn", "--market", help="Market identifier."),
    start: str = typer.Option(..., "--start", help="Start date (YYYY-MM-DD)."),
    end: str = typer.Option(..., "--end", help="End date (YYYY-MM-DD)."),
    sample_size: int = typer.Option(50, "--sample-size", help="Number of symbols to sample."),
    limit: int = typer.Option(10, "--limit", help="Number of failing samples to display."),
) -> None:
    """Execute a reconciliation run and render summary statistics."""

    formatter, stream, stack, _ = prepare_output(ctx)

    if not symbols:
        emit_error("At least one symbol is required for reconciliation.", "SYMBOLS_MISSING")
        raise typer.Exit(code=VALIDATION_EXIT_CODE)

    try:
        market_type = MarketType(market.lower())
    except ValueError as exc:
        allowed = ", ".join(sorted(value.value for value in MarketType))
        raise typer.BadParameter(
            f"Unsupported market '{market}'. Allowed values: {allowed}",
            param_hint="--market",
        ) from exc

    try:
        start_date = _parse_date(start)
    except ValueError as exc:
        emit_error(str(exc), "INVALID_START_DATE", details={"start": start})
        raise typer.Exit(code=VALIDATION_EXIT_CODE) from exc

    try:
        end_date = _parse_date(end)
    except ValueError as exc:
        emit_error(str(exc), "INVALID_END_DATE", details={"end": end})
        raise typer.Exit(code=VALIDATION_EXIT_CODE) from exc

    if start_date > end_date:
        emit_error(
            "Start date must be on or before end date.",
            "INVALID_DATE_RANGE",
            details={"start": start, "end": end},
        )
        raise typer.Exit(code=VALIDATION_EXIT_CODE)

    if sample_size <= 0:
        emit_error("Sample size must be positive.", "INVALID_SAMPLE_SIZE", details={"sample_size": sample_size})
        raise typer.Exit(code=VALIDATION_EXIT_CODE)

    if limit <= 0:
        emit_error("Limit must be positive.", "INVALID_LIMIT", details={"limit": limit})
        raise typer.Exit(code=VALIDATION_EXIT_CODE)

    try:
        service = get_reconciliation_service()
    except NotImplementedError as error:
        emit_error(str(error), "SERVICE_NOT_CONFIGURED")
        raise typer.Exit(code=SYSTEM_EXIT_CODE) from error
    try:
        result = service.reconcile(
            symbols=symbols,
            market=market_type,
            date_range=(start_date, end_date),
            sample_size=sample_size,
        )
    except ReconciliationError as error:
        emit_error(error.message, error.error_code, details=error.details)
        raise typer.Exit(code=RECONCILE_EXIT_CODE) from error
    except VPrismError as error:
        emit_error(error.message, error.error_code, details=error.details)
        raise typer.Exit(code=SYSTEM_EXIT_CODE) from error
    except Exception as error:  # pragma: no cover - defensive fallback
        emit_error(str(error), "UNEXPECTED_ERROR")
        raise typer.Exit(code=SYSTEM_EXIT_CODE) from error

    summary_rows = _build_summary_rows(result)
    failing_rows = _build_failing_rows(result.samples, limit)

    try:
        formatter.render(summary_rows, stream=stream, columns=SUMMARY_COLUMNS)
        if failing_rows:
            formatter.render(failing_rows, stream=stream, columns=DIFF_COLUMNS)
        else:
            typer.echo("No failing samples detected.", file=stream)
    finally:
        stack.close()


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from exc


def _build_summary_rows(result: ReconcileResult) -> list[Mapping[str, object]]:
    summary = result.summary
    return [
        {"metric": "run_id", "value": result.run_id},
        {"metric": "market", "value": summary.market.value},
        {"metric": "start", "value": summary.start.isoformat()},
        {"metric": "end", "value": summary.end.isoformat()},
        {"metric": "sample_size", "value": summary.sample_size},
        {"metric": "pass", "value": summary.pass_count},
        {"metric": "warn", "value": summary.warn_count},
        {"metric": "fail", "value": summary.fail_count},
        {"metric": "p95_close_bp_diff", "value": summary.p95_close_bp_diff},
    ]


def _build_failing_rows(samples: Sequence[ReconciliationSample], limit: int) -> list[Mapping[str, object]]:
    failing = [sample for sample in samples if sample.status is ReconciliationStatus.FAIL]
    if not failing:
        return []
    failing.sort(key=_sample_sort_key, reverse=True)
    rows: list[Mapping[str, object]] = []
    for sample in failing[:limit]:
        rows.append(
            {
                "symbol": sample.symbol,
                "date": sample.date.isoformat(),
                "close_bp_diff": _format_decimal(sample.close_bp_diff),
                "volume_ratio": _format_decimal(sample.volume_ratio),
                "status": sample.status.value,
            }
        )
    return rows


def _sample_sort_key(sample: ReconciliationSample) -> float:
    value = sample.close_bp_diff
    if value is None:
        return 0.0
    return abs(float(value))


def _format_decimal(value: Decimal | None) -> object:
    if value is None:
        return None
    return value


__all__ = [
    "DIFF_COLUMNS",
    "SUMMARY_COLUMNS",
    "get_reconciliation_service",
    "reconcile_app",
    "register",
    "run_command",
]
