from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

import typer

from vprism.core.exceptions import DriftComputationError, VPrismError
from vprism.core.models.base import DataPoint
from vprism.core.models.market import MarketType, TimeFrame
from vprism.core.services.data import DataService
from vprism.core.services.drift import DriftResult, DriftService

from .constants import DATA_QUALITY_EXIT_CODE, SYSTEM_EXIT_CODE, VALIDATION_EXIT_CODE
from .utils import emit_error, prepare_output


drift_app = typer.Typer(help="Data drift diagnostics.")

DRIFT_COLUMNS = [
    "symbol",
    "market",
    "metric",
    "value",
    "status",
    "window",
    "run_id",
    "timestamp",
]


def register(app: typer.Typer) -> None:
    """Register drift commands on the root CLI application."""

    app.add_typer(drift_app, name="drift", help="Analyze price drift metrics")


def get_drift_service() -> DriftService:
    """Factory hook returning a configured :class:`DriftService`."""

    return DriftService(_load_price_history)


def _load_price_history(symbol: str, market: MarketType, window: int) -> Sequence[DataPoint]:
    service = DataService()
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=window * 4)
    response = asyncio.run(
        service.get(
            symbols=symbol,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            market=market,
            timeframe=TimeFrame.DAY_1,
        )
    )
    return response.data


@drift_app.command("report")
def report_command(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="Symbol to analyse for drift."),
    market: str = typer.Option("cn", "--market", help="Market for the symbol."),
    window: int = typer.Option(30, "--window", help="Lookback window size."),
) -> None:
    """Compute drift metrics for a symbol and render the result."""

    formatter, stream, stack, _ = prepare_output(ctx)

    try:
        market_type = MarketType(market.lower())
    except ValueError as exc:
        allowed = ", ".join(sorted(value.value for value in MarketType))
        raise typer.BadParameter(
            f"Unsupported market '{market}'. Allowed values: {allowed}",
            param_hint="--market",
        ) from exc

    if window < 2:
        emit_error(
            "Window must be at least 2 trading days.",
            "INVALID_WINDOW",
            details={"window": window},
        )
        raise typer.Exit(code=VALIDATION_EXIT_CODE)

    service = get_drift_service()
    try:
        result = service.compute(symbol=symbol, market=market_type, window=window)
    except DriftComputationError as error:
        emit_error(error.message, error.error_code, details=error.details)
        raise typer.Exit(code=DATA_QUALITY_EXIT_CODE) from error
    except VPrismError as error:
        emit_error(error.message, error.error_code, details=error.details)
        raise typer.Exit(code=SYSTEM_EXIT_CODE) from error
    except Exception as error:  # pragma: no cover - defensive guard
        emit_error(str(error), "UNEXPECTED_ERROR")
        raise typer.Exit(code=SYSTEM_EXIT_CODE) from error

    rows = _result_to_rows(result)
    try:
        formatter.render(rows, stream=stream, columns=DRIFT_COLUMNS)
    finally:
        stack.close()


def _result_to_rows(result: DriftResult) -> list[Mapping[str, object]]:
    rows: list[Mapping[str, object]] = []
    for metric in result.metrics:
        rows.append(
            {
                "symbol": result.symbol,
                "market": result.market.value,
                "metric": metric.name,
                "value": metric.value,
                "status": metric.status.value,
                "window": result.window,
                "run_id": result.run_id,
                "timestamp": result.latest_timestamp.isoformat(),
            }
        )
    return rows


__all__ = ["DRIFT_COLUMNS", "drift_app", "get_drift_service", "register", "report_command"]
