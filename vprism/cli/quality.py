"""Quality metric commands for the VPrism CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from vprism.core.data.schema import (
    VPrismQualityMetricStatus,
    vprism_quality_metrics_table,
)
from vprism.core.data.storage.duckdb_factory import VPrismDuckDBFactory

from .constants import SYSTEM_EXIT_CODE, VALIDATION_EXIT_CODE
from .utils import emit_error, prepare_output

if TYPE_CHECKING:  # pragma: no cover - typing-only imports
    from duckdb import DuckDBPyConnection


QUALITY_COLUMNS = [
    "date",
    "market",
    "symbol",
    "metric",
    "value",
    "status",
    "run_id",
    "created_at",
]

quality_app = typer.Typer(help="Quality metric reports.")


def register(app: typer.Typer) -> None:
    """Register the quality command group on the provided application."""

    app.add_typer(quality_app, name="quality", help="Inspect stored quality metrics")


def get_duckdb_factory() -> VPrismDuckDBFactory:
    """Factory hook for obtaining a DuckDB connection factory."""

    return VPrismDuckDBFactory()


@quality_app.command("report")
def report_command(
    ctx: typer.Context,
    symbol: str | None = typer.Option(None, "--symbol", help="Filter by supplier symbol."),
    market: str | None = typer.Option(None, "--market", help="Filter by market identifier."),
    metric: str | None = typer.Option(None, "--metric", help="Filter by metric name."),
    status: str | None = typer.Option(
        None,
        "--status",
        help="Filter by metric status (OK, WARN, FAIL).",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Maximum number of rows to return.",
    ),
) -> None:
    """Render quality metrics stored in DuckDB."""

    formatter, stream, stack, _ = prepare_output(ctx)
    try:
        normalized_status = _normalize_status(status)
        if limit is not None and limit <= 0:
            emit_error(
                "Limit must be a positive integer.",
                "INVALID_LIMIT",
                details={"limit": limit},
            )
            raise typer.Exit(code=VALIDATION_EXIT_CODE)

        factory = get_duckdb_factory()
        with factory.connection() as connection:
            vprism_quality_metrics_table.ensure(connection)
            rows = _fetch_quality_metrics(
                connection,
                symbol=symbol,
                market=market,
                metric=metric,
                status=normalized_status,
                limit=limit,
            )

        if not rows:
            filters = _build_filter_details(
                symbol=symbol,
                market=market,
                metric=metric,
                status=normalized_status,
            )
            emit_error(
                "No quality metrics found for the provided filters.",
                "QUALITY_METRICS_NOT_FOUND",
                details=filters or None,
            )
            raise typer.Exit(code=VALIDATION_EXIT_CODE)

        formatter.render(rows, stream=stream, columns=QUALITY_COLUMNS)
    except typer.Exit:
        raise
    except Exception as error:  # pragma: no cover - defensive safeguard
        emit_error(str(error), "QUALITY_METRIC_QUERY_ERROR")
        raise typer.Exit(code=SYSTEM_EXIT_CODE) from error
    finally:
        stack.close()


def _normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    allowed = {item.value for item in VPrismQualityMetricStatus}
    if normalized not in allowed:
        emit_error(
            f"Unsupported status '{value}'.",
            "INVALID_STATUS",
            details={"allowed": sorted(allowed)},
        )
        raise typer.Exit(code=VALIDATION_EXIT_CODE)
    return normalized


def _fetch_quality_metrics(
    connection: "DuckDBPyConnection",
    *,
    symbol: str | None,
    market: str | None,
    metric: str | None,
    status: str | None,
    limit: int | None,
) -> list[dict[str, object]]:
    base_query = "SELECT date, market, supplier_symbol, metric, value, status, run_id, created_at FROM quality_metrics"
    filters: list[str] = []
    params: list[object] = []

    if symbol:
        filters.append("supplier_symbol = ?")
        params.append(symbol)
    if market:
        filters.append("market = ?")
        params.append(market)
    if metric:
        filters.append("metric = ?")
        params.append(metric)
    if status:
        filters.append("status = ?")
        params.append(status)

    if filters:
        base_query += " WHERE " + " AND ".join(filters)

    base_query += " ORDER BY date DESC, created_at DESC"

    if limit is not None:
        base_query += " LIMIT ?"
        params.append(limit)

    cursor = connection.execute(base_query, params)
    results = cursor.fetchall()
    rows: list[dict[str, object]] = []
    for row in results:
        rows.append(
            {
                "date": row[0],
                "market": row[1],
                "symbol": row[2],
                "metric": row[3],
                "value": row[4],
                "status": row[5],
                "run_id": row[6],
                "created_at": row[7],
            }
        )
    return rows


def _build_filter_details(
    *,
    symbol: str | None,
    market: str | None,
    metric: str | None,
    status: str | None,
) -> dict[str, object]:
    details: dict[str, object] = {}
    if symbol is not None:
        details["symbol"] = symbol
    if market is not None:
        details["market"] = market
    if metric is not None:
        details["metric"] = metric
    if status is not None:
        details["status"] = status
    return details


__all__ = [
    "QUALITY_COLUMNS",
    "get_duckdb_factory",
    "quality_app",
    "register",
    "report_command",
]
