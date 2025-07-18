"""
Command-line interface for vprism.

This module provides a comprehensive CLI for interacting with the vprism
financial data platform, supporting data queries, configuration management,
and system administration tasks.
"""

from __future__ import annotations

import asyncio
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from vprism.core.client import VPrismClient
from vprism.core.exceptions import VPrismException
from vprism.core.models import AssetType, MarketType, TimeFrame

app = typer.Typer(
    name="vprism",
    help="vprism - Modern Financial Data Infrastructure Platform",
    add_completion=False,
)
console = Console()


@app.command()
def version() -> None:
    """Show vprism version information."""
    from vprism import __version__

    console.print(f"vprism version: {__version__}")


@app.command()
def get(
    asset: AssetType = typer.Argument(..., help="Asset type to query"),
    market: MarketType | None = typer.Option(
        None, "--market", "-m", help="Market to query"
    ),
    symbols: str | None = typer.Option(
        None, "--symbols", "-s", help="Comma-separated symbols"
    ),
    provider: str | None = typer.Option(None, "--provider", "-p", help="Data provider"),
    timeframe: TimeFrame | None = typer.Option(
        None, "--timeframe", "-t", help="Data timeframe"
    ),
    start: str | None = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end: str | None = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Maximum records"),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
) -> None:
    """Get financial data."""
    try:
        # Parse symbols
        symbol_list = None
        if symbols:
            symbol_list = [s.strip() for s in symbols.split(",")]

        # Create client and get data
        client = VPrismClient()
        data = client.get_sync(
            asset=asset,
            market=market,
            symbols=symbol_list,
            provider=provider,
            timeframe=timeframe,
            start=start,
            end=end,
            limit=limit,
        )

        # Display results
        if output_format == "table":
            _display_table(data)
        elif output_format == "json":
            console.print_json(data.model_dump_json())
        elif output_format == "csv":
            _display_csv(data)
        else:
            console.print(f"[red]Unsupported format: {output_format}[/red]")
            raise typer.Exit(1)

    except VPrismException as e:
        console.print(f"[red]Error: {e.message}[/red]")
        if e.details:
            console.print(f"[yellow]Details: {e.details}[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def stream(
    asset: AssetType = typer.Argument(..., help="Asset type to stream"),
    market: MarketType | None = typer.Option(
        None, "--market", "-m", help="Market to stream"
    ),
    symbols: str | None = typer.Option(
        None, "--symbols", "-s", help="Comma-separated symbols"
    ),
    provider: str | None = typer.Option(None, "--provider", "-p", help="Data provider"),
) -> None:
    """Stream real-time financial data."""
    try:
        # Parse symbols
        symbol_list = None
        if symbols:
            symbol_list = [s.strip() for s in symbols.split(",")]

        console.print("[green]Starting data stream... (Press Ctrl+C to stop)[/green]")

        async def stream_data() -> None:
            async with VPrismClient() as client:
                async for data in client.stream(
                    asset=asset,
                    market=market,
                    symbols=symbol_list,
                    provider=provider,
                ):
                    _display_stream_data(data)

        asyncio.run(stream_data())

    except KeyboardInterrupt:
        console.print("\n[yellow]Stream stopped by user[/yellow]")
    except VPrismException as e:
        console.print(f"[red]Error: {e.message}[/red]")
        if e.details:
            console.print(f"[yellow]Details: {e.details}[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    set_key: str | None = typer.Option(
        None, "--set", help="Set configuration key=value"
    ),
) -> None:
    """Manage vprism configuration."""
    if show:
        console.print("[green]Current configuration:[/green]")
        console.print("Configuration management not yet implemented")
    elif set_key:
        console.print(f"[green]Setting configuration: {set_key}[/green]")
        console.print("Configuration management not yet implemented")
    else:
        console.print(
            "[yellow]Use --show to view or --set key=value to configure[/yellow]"
        )


@app.command()
def health() -> None:
    """Check system health and provider status."""
    console.print("[green]Checking system health...[/green]")
    console.print("Health check not yet implemented")


def _display_table(data: Any) -> None:
    """Display data in table format."""
    table = Table(title="Financial Data")
    table.add_column("Symbol", style="cyan")
    table.add_column("Timestamp", style="magenta")
    table.add_column("Open", style="green")
    table.add_column("High", style="green")
    table.add_column("Low", style="red")
    table.add_column("Close", style="blue")
    table.add_column("Volume", style="yellow")

    # This would be implemented when we have actual data
    table.add_row("N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A")

    console.print(table)


def _display_csv(data: Any) -> None:
    """Display data in CSV format."""
    console.print("symbol,timestamp,open,high,low,close,volume")
    console.print("N/A,N/A,N/A,N/A,N/A,N/A,N/A")


def _display_stream_data(data: Any) -> None:
    """Display streaming data."""
    console.print(f"[cyan]Stream data:[/cyan] {data}")


if __name__ == "__main__":
    app()
