#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "typer>=0.9.0",
#     "pandas>=2.0.0",
# ]
# ///
from __future__ import annotations

from pathlib import Path

import pandas as pd
import typer

import vprism

app = typer.Typer(add_completion=False)

CODES_FILE_ARG = typer.Argument(..., help="Text file with fund codes, one per line.")
OUTPUT_OPTION = typer.Option(Path("fund_data.csv"), "--output", "-o", help="Output CSV file.")
ASSET_OPTION = typer.Option("etf", help="Asset type for vprism.")
MARKET_OPTION = typer.Option("cn", help="Market identifier.")
TIMEFRAME_OPTION = typer.Option("1d", help="Timeframe for data.")
LIMIT_OPTION = typer.Option(100, help="Number of records to fetch per symbol.")


def fetch_symbol(symbol: str, asset: str, market: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Fetch OHLCV data for a single symbol via vprism."""
    result = vprism.get(asset=asset, market=market, symbols=[symbol], timeframe=timeframe, limit=limit)
    rows: list[dict[str, object]] = []
    if getattr(result, "data", None):
        for dp in result.data[:limit]:
            rows.append(
                {
                    "symbol": dp.symbol,
                    "timestamp": getattr(dp, "timestamp", None),
                    "open": getattr(dp, "open_price", None),
                    "high": getattr(dp, "high_price", None),
                    "low": getattr(dp, "low_price", None),
                    "close": getattr(dp, "close_price", None),
                    "volume": getattr(dp, "volume", None),
                }
            )
    return pd.DataFrame(rows)


@app.command()
def main(
    codes_file: Path = CODES_FILE_ARG,
    output: Path = OUTPUT_OPTION,
    asset: str = ASSET_OPTION,
    market: str = MARKET_OPTION,
    timeframe: str = TIMEFRAME_OPTION,
    limit: int = LIMIT_OPTION,
) -> None:
    """Fetch OHLCV data for all symbols listed in codes_file and save to CSV."""
    codes = [line.strip() for line in codes_file.read_text().splitlines() if line.strip()]
    frames: list[pd.DataFrame] = []
    for code in codes:
        try:
            df = fetch_symbol(code, asset, market, timeframe, limit)
            if df.empty:
                typer.echo(f"No data returned for {code}")
            else:
                frames.append(df)
                typer.echo(f"Fetched {len(df)} records for {code}")
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Failed to fetch {code}: {exc}")
    if frames:
        result = pd.concat(frames, ignore_index=True)
        result.to_csv(output, index=False)
        typer.echo(f"Saved data to {output}")
    else:
        typer.echo("No data fetched.")


if __name__ == "__main__":
    app()
