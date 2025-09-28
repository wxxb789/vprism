"""Symbol related CLI commands."""

from __future__ import annotations

from typing import Mapping

import typer

from vprism.core.exceptions.base import UnresolvedSymbolError
from vprism.core.models.market import AssetType, MarketType
from vprism.core.models.symbols import CanonicalSymbol
from vprism.core.services.symbols import SymbolService

from .constants import VALIDATION_EXIT_CODE
from .utils import emit_error, prepare_output


symbol_app = typer.Typer(help="Symbol utilities.")

SYMBOL_COLUMNS = ["raw_symbol", "canonical", "market", "asset_type", "rule_id"]


def register(app: typer.Typer) -> None:
    """Register symbol commands on the root CLI application."""

    app.add_typer(symbol_app, name="symbol", help="Resolve and inspect symbols")


def get_symbol_service() -> SymbolService:
    """Factory hook returning a :class:`SymbolService` instance."""

    return SymbolService()


@symbol_app.command("resolve")
def resolve_command(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="Symbol to resolve."),
    market: str = typer.Option("cn", "--market", help="Market to resolve against."),
    asset: str = typer.Option("stock", "--asset", help="Asset type context."),
) -> None:
    """Resolve a raw symbol into its canonical representation."""

    formatter, stream, stack, _ = prepare_output(ctx)

    asset_type = _parse_asset(asset)
    market_type = _parse_market(market)

    service = get_symbol_service()
    try:
        canonical = service.normalize(symbol, market_type, asset_type)
    except UnresolvedSymbolError as error:
        emit_error(error.message, error.error_code, details=error.details)
        raise typer.Exit(code=VALIDATION_EXIT_CODE) from error

    rows = [_canonical_to_row(canonical)]
    try:
        formatter.render(rows, stream=stream, columns=SYMBOL_COLUMNS)
    finally:
        stack.close()


def _parse_asset(value: str) -> AssetType:
    try:
        return AssetType(value.lower())
    except ValueError as exc:
        allowed = ", ".join(sorted(asset.value for asset in AssetType))
        raise typer.BadParameter(
            f"Unsupported asset '{value}'. Allowed values: {allowed}",
            param_hint="--asset",
        ) from exc


def _parse_market(value: str) -> MarketType:
    try:
        return MarketType(value.lower())
    except ValueError as exc:
        allowed = ", ".join(sorted(market.value for market in MarketType))
        raise typer.BadParameter(
            f"Unsupported market '{value}'. Allowed values: {allowed}",
            param_hint="--market",
        ) from exc


def _canonical_to_row(canonical: CanonicalSymbol) -> Mapping[str, object]:
    return {
        "raw_symbol": canonical.raw_symbol,
        "canonical": canonical.canonical,
        "market": canonical.market.value,
        "asset_type": canonical.asset_type.value,
        "rule_id": canonical.rule_id,
    }


__all__ = ["register", "symbol_app", "resolve_command", "get_symbol_service"]
