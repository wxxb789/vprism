"""MCP Server for vprism Financial Data Platform.

Exposes 2 tools:
  - get_financial_data: unified historical/real-time data access
  - get_market_overview: major indices for a market
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastmcp import FastMCP
from loguru import logger

from vprism.core.client import VPrismClient
from vprism.core.exceptions import VPrismError


class VPrismMCPServer:
    """vprism MCP Server - 2 focused tools for financial data access."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = config or {}
        self.mcp: FastMCP[Any] = FastMCP("vprism-financial-data")
        self.client: VPrismClient = VPrismClient(config=self.config)
        self._setup_tools()

    def _setup_tools(self) -> None:
        """Register MCP tools."""

        @self.mcp.tool()
        async def get_financial_data(
            symbol: str,
            start_date: str | None = None,
            end_date: str | None = None,
            timeframe: str = "1d",
            market: str = "us",
            asset_type: str = "stock",
        ) -> dict[str, Any]:
            """Get financial data for a symbol.

            Args:
                symbol: Ticker symbol (e.g. "AAPL", "000001", "00700")
                start_date: Start date YYYY-MM-DD (default: 30 days ago)
                end_date: End date YYYY-MM-DD (default: today)
                timeframe: Data interval ("1m", "5m", "1h", "1d", "1w", "1M")
                market: Market identifier ("us", "cn", "hk")
                asset_type: Asset type ("stock", "etf", "crypto", "index")

            Returns:
                OHLCV data with metadata.
            """
            try:
                end = end_date or datetime.now(UTC).strftime("%Y-%m-%d")
                start = start_date or (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")

                logger.info(f"MCP get_financial_data: {symbol} {start}..{end} tf={timeframe}")

                data = await self.client.get_async(
                    asset=asset_type,
                    symbols=[symbol.upper()],
                    start=start,
                    end=end,
                    timeframe=timeframe,
                    market=market,
                )

                result: dict[str, Any] = {
                    "symbol": symbol.upper(),
                    "market": market,
                    "timeframe": timeframe,
                    "start_date": start,
                    "end_date": end,
                    "data_points": len(data.data) if data.data else 0,
                    "data": [],
                }

                if data.data:
                    result["data"] = [
                        {
                            "date": p.timestamp.isoformat(),
                            "open": float(p.open_price) if p.open_price else None,
                            "high": float(p.high_price) if p.high_price else None,
                            "low": float(p.low_price) if p.low_price else None,
                            "close": float(p.close_price) if p.close_price else None,
                            "volume": int(p.volume) if p.volume else None,
                        }
                        for p in data.data
                    ]

                return result

            except VPrismError as e:
                logger.error(f"VPrism error: {e}")
                return {"error": str(e), "symbol": symbol}
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return {"error": f"Failed to get data: {e}", "symbol": symbol}

        @self.mcp.tool()
        async def get_market_overview(market: str = "us", date: str | None = None) -> dict[str, Any]:
            """Get market overview with major index data.

            Args:
                market: Market identifier ("us", "cn", "hk")
                date: Specific date YYYY-MM-DD (default: latest)

            Returns:
                Index prices and changes for the market.
            """
            try:
                target_date = date or datetime.now(UTC).strftime("%Y-%m-%d")
                logger.info(f"MCP get_market_overview: {market} @ {target_date}")

                indices: dict[str, list[str]] = {
                    "us": ["SPY", "QQQ", "DIA", "IWM"],
                    "cn": ["000001.SS", "399001.SZ", "399006.SZ"],
                    "hk": ["^HSI", "^HSCEI"],
                }

                symbols = indices.get(market.lower(), ["SPY"])

                async def _fetch_index(symbol: str) -> tuple[str, dict[str, Any]]:
                    try:
                        data = await self.client.get_async(
                            asset="index",
                            symbols=[symbol],
                            start=target_date,
                            end=target_date,
                            timeframe="1d",
                            market=market,
                        )

                        if data.data:
                            p = data.data[0]
                            change = float(p.close_price - p.open_price) if p.close_price and p.open_price else 0.0
                            change_pct = float(change / float(p.open_price) * 100) if p.open_price and float(p.open_price) != 0 else 0.0
                            return symbol, {
                                "symbol": symbol,
                                "date": target_date,
                                "close": float(p.close_price) if p.close_price else 0.0,
                                "change": round(change, 4),
                                "change_percent": round(change_pct, 2),
                                "volume": int(p.volume) if p.volume else 0,
                            }
                        return symbol, {"symbol": symbol, "date": target_date, "close": 0.0}
                    except Exception as e:
                        logger.warning(f"Failed to get data for {symbol}: {e}")
                        return symbol, {"error": str(e), "symbol": symbol}

                results = await asyncio.gather(*(_fetch_index(s) for s in symbols))
                overview: dict[str, Any] = dict(results)

                return {"market": market, "date": target_date, "indices": overview}

            except Exception as e:
                logger.error(f"Market overview error: {e}")
                return {"error": f"Failed to get market overview: {e}", "market": market}

    async def start(self, transport: Literal["stdio", "http", "sse", "streamable-http"] | None = "stdio", **kwargs: Any) -> None:
        """Start the MCP server."""
        logger.info(f"Starting vprism MCP server ({transport})")
        try:
            if hasattr(self.client, "initialize"):
                await self.client.initialize()
            self.mcp.run(transport=transport, **kwargs)
        except Exception as e:
            logger.error(f"MCP server failed: {e}")
            raise
        finally:
            if hasattr(self.client, "close"):
                await self.client.close()

    def run(self, transport: Literal["stdio", "http", "sse", "streamable-http"] = "stdio", **kwargs: Any) -> None:
        """Run the MCP server synchronously."""
        asyncio.run(self.start(transport, **kwargs))


def create_mcp_server(config: dict[str, Any] | None = None) -> VPrismMCPServer:
    """Create a configured MCP server instance."""
    return VPrismMCPServer(config=config)


if __name__ == "__main__":
    server = create_mcp_server()
    server.run()
