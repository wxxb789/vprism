"""Data command implementations for the VPrism CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable, Mapping

import typer

from vprism.core.exceptions.base import (
    DataValidationError,
    ProviderError,
    UnresolvedSymbolError,
    VPrismError,
)
from vprism.core.models.market import AssetType, MarketType, TimeFrame
from vprism.core.models.response import DataResponse
from vprism.core.services.data import DataService
from vprism.core.services.symbol_normalization import get_symbol_normalizer

from .constants import PROVIDER_EXIT_CODE, SYSTEM_EXIT_CODE, VALIDATION_EXIT_CODE
from .utils import emit_error, prepare_output


data_app = typer.Typer(help="Data operations.")

DEFAULT_COLUMNS = [
    "symbol",
    "market",
    "timestamp",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    "amount",
    "provider",
]


def register(app: typer.Typer) -> None:
    """Register the data command group on the provided application."""

    app.add_typer(data_app, name="data", help="Interact with price data providers")


def get_data_service() -> DataService:
    """Factory hook for obtaining a :class:`DataService` instance."""

    return DataService()


@data_app.command("fetch")
def fetch_command(
    ctx: typer.Context,
    symbols: str = typer.Option(
        None,
        "--symbols",
        help="Comma separated list of symbols to fetch.",
    ),
    symbols_from: Path | None = typer.Option(
        None,
        "--symbols-from",
        help="Read newline-delimited symbols from a file.",
    ),
    asset: str = typer.Option("stock", "--asset", help="Asset type to query."),
    market: str = typer.Option("cn", "--market", help="Market to target."),
    start: str | None = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)."),
    end: str | None = typer.Option(None, "--end", help="End date (YYYY-MM-DD)."),
    timeframe: str = typer.Option("1d", "--timeframe", help="Requested timeframe."),
) -> None:
    """Fetch market data and render it with the configured formatter."""

    formatter, stream, stack, _ = prepare_output(ctx)
    try:
        collected = _collect_symbols(symbols, symbols_from)
    except OSError as exc:
        emit_error(str(exc), "SYMBOL_FILE_ERROR")
        raise typer.Exit(code=VALIDATION_EXIT_CODE) from exc

    if not collected:
        emit_error("No symbols supplied for fetch command.", "SYMBOLS_MISSING")
        raise typer.Exit(code=VALIDATION_EXIT_CODE)

    asset_type = _parse_asset(asset)
    market_type = _parse_market(market)
    timeframe_value = _parse_timeframe(timeframe)

    try:
        _ensure_symbols_resolvable(collected, market_type, asset_type)
    except UnresolvedSymbolError as error:
        emit_error(error.message, error.error_code, details=error.details)
        raise typer.Exit(code=VALIDATION_EXIT_CODE) from error

    service = get_data_service()
    try:
        response = asyncio.run(
            service.get(
                symbols=collected,
                start=start,
                end=end,
                market=market_type,
                asset_type=asset_type,
                timeframe=timeframe_value,
            )
        )
    except DataValidationError as error:
        emit_error(error.message, error.error_code, details=error.details)
        raise typer.Exit(code=VALIDATION_EXIT_CODE) from error
    except ProviderError as error:
        emit_error(error.message, error.error_code, details=error.details)
        raise typer.Exit(code=PROVIDER_EXIT_CODE) from error
    except VPrismError as error:
        emit_error(error.message, error.error_code, details=error.details)
        raise typer.Exit(code=SYSTEM_EXIT_CODE) from error
    except ValueError as error:
        emit_error(str(error), "VALIDATION_ERROR")
        raise typer.Exit(code=VALIDATION_EXIT_CODE) from error
    except Exception as error:  # pragma: no cover - safety net
        emit_error(str(error), "UNEXPECTED_ERROR")
        raise typer.Exit(code=SYSTEM_EXIT_CODE) from error

    rows = _response_to_rows(response)
    try:
        formatter.render(rows, stream=stream, columns=DEFAULT_COLUMNS)
    finally:
        stack.close()


def _collect_symbols(symbols: str | None, symbols_from: Path | None) -> list[str]:
    collected: list[str] = []
    if symbols:
        for candidate in symbols.split(","):
            value = candidate.strip()
            if value:
                collected.append(value)

    if symbols_from is not None:
        if not symbols_from.exists() or not symbols_from.is_file():
            msg = f"Symbols file '{symbols_from}' does not exist or is not a file."
            raise OSError(msg)
        try:
            contents = symbols_from.read_text(encoding="utf-8")
        except OSError as exc:
            raise OSError(f"Unable to read symbols file '{symbols_from}': {exc}") from exc
        for line in contents.splitlines():
            value = line.strip()
            if value:
                collected.append(value)

    unique: list[str] = []
    seen: set[str] = set()
    for symbol in collected:
        if symbol not in seen:
            seen.add(symbol)
            unique.append(symbol)
    return unique


def _parse_asset(value: str) -> AssetType:
    try:
        return AssetType(value.lower())
    except ValueError as exc:
        allowed = ", ".join(sorted(asset.value for asset in AssetType))
        raise typer.BadParameter(f"Unsupported asset '{value}'. Allowed values: {allowed}", param_hint="--asset") from exc


def _parse_market(value: str) -> MarketType:
    try:
        return MarketType(value.lower())
    except ValueError as exc:
        allowed = ", ".join(sorted(market.value for market in MarketType))
        raise typer.BadParameter(
            f"Unsupported market '{value}'. Allowed values: {allowed}",
            param_hint="--market",
        ) from exc


def _parse_timeframe(value: str) -> TimeFrame:
    try:
        return TimeFrame(value)
    except ValueError as exc:
        allowed = ", ".join(timeframe.value for timeframe in TimeFrame)
        raise typer.BadParameter(
            f"Unsupported timeframe '{value}'. Allowed values: {allowed}",
            param_hint="--timeframe",
        ) from exc


def _ensure_symbols_resolvable(
    symbols: Iterable[str], market: MarketType, asset: AssetType
) -> None:
    normalizer = get_symbol_normalizer()
    normalized = asyncio.run(normalizer.normalize(list(symbols), market=market))
    unresolved = [item.raw for item in normalized if getattr(item, "unresolved", False)]
    if unresolved:
        message = "Unable to resolve symbol(s): " + ", ".join(unresolved)
        details = {"symbols": unresolved, "market": market.value, "asset": asset.value}
        raise UnresolvedSymbolError(message, unresolved[0], market.value, asset.value, details=details)


def _response_to_rows(response: DataResponse) -> list[Mapping[str, object]]:
    rows: list[dict[str, object]] = []
    provider_name = response.source.name if response.source else "unknown"
    for point in response.data:
        record = point.model_dump(mode="json")
        record.setdefault("provider", point.provider or provider_name)
        row = {column: record.get(column) for column in DEFAULT_COLUMNS}
        rows.append(row)
    return rows


__all__ = ["register", "data_app", "fetch_command", "get_data_service"]
