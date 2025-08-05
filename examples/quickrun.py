#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "typer>=0.9.0",
#     "rich>=13.0.0",
#     "yfinance>=0.2.0",
#     "akshare>=1.12.0",
#     "pandas>=2.0.0",
# ]
# ///

from datetime import datetime, timedelta

import pandas as pd
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    import yfinance as yf  # type: ignore
except ImportError:
    yf = None

try:
    import akshare as ak  # type: ignore
except ImportError:
    ak = None

app = typer.Typer()
console = Console()


def get_data_yfinance(symbol: str, days: int = 10) -> pd.DataFrame:
    """Get OHLCV data from yfinance."""
    if not yf:
        console.print("[red]yfinance not available[/red]")
        return pd.DataFrame()

    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 5)  # Add buffer for weekends

        ticker = yf.Ticker(symbol)
        data = ticker.history(start=start_date, end=end_date)

        if data.empty:
            console.print(f"[red]No data found for {symbol} using yfinance[/red]")
            return pd.DataFrame()

        # Select last 'days' of data
        data = data.tail(days)

        # Reset index and format
        data = data.reset_index()
        data["Date"] = pd.to_datetime(data["Date"]).dt.strftime("%Y-%m-%d")

        return data[["Date", "Open", "High", "Low", "Close", "Volume"]]  # type: ignore[no-any-return]

    except Exception as e:
        console.print(f"[red]Error fetching from yfinance: {e}[/red]")
        return pd.DataFrame()


def get_data_akshare(symbol: str, days: int = 10) -> pd.DataFrame:
    """Get OHLCV data from akshare."""
    if not ak:
        console.print("[red]akshare not available[/red]")
        return pd.DataFrame()

    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days + 5)).strftime("%Y%m%d")

        # Handle different symbol formats for akshare
        if symbol.upper().endswith(".SS"):
            ak_symbol = f"sh{symbol.replace('.SS', '')}"
        elif symbol.upper().endswith(".SZ"):
            ak_symbol = f"sz{symbol.replace('.SZ', '')}"
        else:
            ak_symbol = symbol

        data = ak.stock_zh_a_hist(symbol=ak_symbol, period="daily", start_date=start_date, end_date=end_date, adjust="")

        if data.empty:
            console.print(f"[red]No data found for {symbol} using akshare[/red]")
            return pd.DataFrame()

        # Select last 'days' of data
        data = data.tail(days)

        # Rename columns to match standard format
        data = data.rename(columns={"日期": "Date", "开盘": "Open", "收盘": "Close", "最高": "High", "最低": "Low", "成交量": "Volume"})

        return data[["Date", "Open", "High", "Low", "Close", "Volume"]]  # type: ignore[no-any-return]

    except Exception as e:
        console.print(f"[red]Error fetching from akshare: {e}[/red]")
        return pd.DataFrame()


def display_ohlcv_table(symbol: str, data: pd.DataFrame, provider: str) -> None:
    """Display OHLCV data in a rich table."""
    if data.empty:
        console.print(f"[red]No data to display for {symbol}[/red]")
        return

    table = Table(title=f"{symbol} - OHLCV Data ({provider})")

    table.add_column("Date", style="cyan", no_wrap=True)
    table.add_column("Open", style="green", justify="right")
    table.add_column("High", style="green", justify="right")
    table.add_column("Low", style="red", justify="right")
    table.add_column("Close", style="blue", justify="right")
    table.add_column("Volume", style="yellow", justify="right")

    for _, row in data.iterrows():
        table.add_row(str(row["Date"]), f"{row['Open']:.2f}", f"{row['High']:.2f}", f"{row['Low']:.2f}", f"{row['Close']:.2f}", f"{int(row['Volume']):,}")

    console.print(table)


@app.command()
def main(
    symbol: str = typer.Argument(..., help="Stock symbol (e.g., AAPL, 000001.SZ)"),
    days: int = typer.Option(10, help="Number of days to display"),
    provider: str = typer.Option("yfinance", help="Data provider: yfinance, akshare, or both"),
) -> None:
    """Get OHLCV data for a given symbol using multiple data providers."""

    console.print(
        Panel.fit(f"Fetching OHLCV data for [bold green]{symbol}[/bold green] - Last [bold]{days}[/bold] days", title="Quick Stock Data", border_style="blue")
    )

    providers = ["yfinance", "akshare"] if provider == "both" else [provider]

    for prov in providers:
        console.print(f"\n[bold blue]Using {prov.upper()} provider:[/bold blue]")

        if prov == "yfinance":
            data = get_data_yfinance(symbol, days)
        elif prov == "akshare":
            data = get_data_akshare(symbol, days)
        else:
            console.print(f"[red]Unknown provider: {prov}[/red]")
            continue

        display_ohlcv_table(symbol, data, prov)


if __name__ == "__main__":
    app()
