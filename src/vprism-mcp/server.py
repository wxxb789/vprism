"""
FastMCP Server for vPrism Financial Data Platform

This module implements the MCP (Model Context Protocol) server interface
for vPrism, providing financial data access through standardized MCP tools.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from fastmcp import FastMCP
from loguru import logger

from vprism.core.client import VPrismClient
from vprism.core.exceptions import VPrismError
from vprism.core.models import MarketType, TimeFrame


class VPrismMCPServer:
    """
    vPrism MCP Server implementation providing financial data tools.

    This server exposes vPrism's financial data capabilities through
    standardized MCP tools, allowing AI models to access real-time
    and historical financial data.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize vPrism MCP Server.

        Args:
            config: Optional configuration dictionary for vPrism client
        """
        self.config = config or {}
        self.mcp = FastMCP("vprism-financial-data")
        self.client = VPrismClient(config=self.config)
        self._setup_tools()

    def _setup_tools(self) -> None:
        """Setup MCP tools for financial data access."""

        @self.mcp.tool()
        async def get_stock_data(
            symbol: str,
            start_date: str,
            end_date: str,
            timeframe: str = "1d",
            market: str = "us",
        ) -> dict[str, Any]:
            """
            Get historical stock data for a specific symbol.

            Args:
                symbol: Stock symbol (e.g., "AAPL", "MSFT", "TSLA")
                start_date: Start date in YYYY-MM-DD format
                end_date: End date in YYYY-MM-DD format
                timeframe: Data timeframe ("1d", "1h", "5m", "1m")
                market: Market type ("us", "cn", "hk")

            Returns:
                Dictionary containing stock data with OHLCV values
            """
            try:
                logger.info(
                    f"Getting stock data for {symbol} from {start_date} to {end_date}"
                )

                # Convert string parameters to enum types
                market_type = MarketType(market.lower())
                time_frame = TimeFrame(timeframe.lower())

                # Get data using vPrism client
                data = await self.client.get_async(
                    symbol=symbol.upper(),
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=time_frame,
                    market=market_type,
                )

                # Convert to MCP-friendly format
                result = {
                    "symbol": symbol.upper(),
                    "market": market,
                    "timeframe": timeframe,
                    "data_points": len(data.data) if data.data else 0,
                    "start_date": start_date,
                    "end_date": end_date,
                    "data": [],
                }

                if data.data:
                    for point in data.data:
                        result["data"].append(
                            {
                                "date": point.timestamp.isoformat()
                                if hasattr(point.timestamp, "isoformat")
                                else str(point.timestamp),
                                "open": float(point.open_price)
                                if point.open_price
                                else None,
                                "high": float(point.high_price)
                                if point.high_price
                                else None,
                                "low": float(point.low_price)
                                if point.low_price
                                else None,
                                "close": float(point.close_price)
                                if point.close_price
                                else None,
                                "volume": int(point.volume) if point.volume else None,
                            }
                        )

                return result

            except VPrismError as e:
                logger.error(f"vPrism error getting stock data: {e}")
                return {"error": str(e), "symbol": symbol}
            except Exception as e:
                logger.error(f"Unexpected error getting stock data: {e}")
                return {
                    "error": f"Failed to get stock data: {str(e)}",
                    "symbol": symbol,
                }

        @self.mcp.tool()
        async def get_market_overview(
            market: str = "us", date: str | None = None
        ) -> dict[str, Any]:
            """
            Get market overview data including major indices.

            Args:
                market: Market type ("us", "cn", "hk")
                date: Specific date for overview (YYYY-MM-DD), defaults to latest

            Returns:
                Dictionary with market indices and overview data
            """
            try:
                logger.info(f"Getting market overview for {market}")

                market_type = MarketType(market.lower())
                target_date = date or datetime.now().strftime("%Y-%m-%d")

                # Define major indices for each market
                market_indices = {
                    "us": ["SPY", "QQQ", "DIA", "IWM"],
                    "cn": ["000001.SS", "399001.SZ", "399006.SZ"],
                    "hk": ["^HSI", "^HSCEI"],
                }

                symbols = market_indices.get(market.lower(), ["SPY"])

                overview_data = {}
                for symbol in symbols:
                    try:
                        data = await self.client.get_async(
                            symbol=symbol,
                            start_date=target_date,
                            end_date=target_date,
                            timeframe=TimeFrame.DAILY,
                            market=market_type,
                        )

                        if data.data and len(data.data) > 0:
                            point = data.data[0]
                            overview_data[symbol] = {
                                "symbol": symbol,
                                "date": target_date,
                                "close": float(point.close_price)
                                if point.close_price
                                else 0.0,
                                "change": float(point.close_price - point.open_price)
                                if point.close_price and point.open_price
                                else 0.0,
                                "change_percent": float(
                                    (point.close_price - point.open_price)
                                    / point.open_price
                                    * 100
                                )
                                if point.close_price and point.open_price
                                else 0.0,
                                "volume": int(point.volume) if point.volume else 0,
                            }
                    except Exception as e:
                        logger.warning(f"Failed to get data for {symbol}: {e}")
                        overview_data[symbol] = {"error": str(e), "symbol": symbol}

                return {"market": market, "date": target_date, "indices": overview_data}

            except VPrismError as e:
                logger.error(f"vPrism error getting market overview: {e}")
                return {"error": str(e), "market": market}
            except Exception as e:
                logger.error(f"Unexpected error getting market overview: {e}")
                return {
                    "error": f"Failed to get market overview: {str(e)}",
                    "market": market,
                }

        @self.mcp.tool()
        async def search_symbols(
            query: str, market: str = "us", limit: int = 10
        ) -> dict[str, Any]:
            """
            Search for stock symbols by name or ticker.

            Args:
                query: Search query (symbol or company name)
                market: Market type ("us", "cn", "hk")
                limit: Maximum number of results to return

            Returns:
                Dictionary with search results
            """
            try:
                logger.info(f"Searching symbols for query: {query}")

                # For now, return simplified search results
                # In a full implementation, this would use a proper symbol search API
                common_symbols = {
                    "us": {
                        "AAPL": "Apple Inc.",
                        "MSFT": "Microsoft Corporation",
                        "GOOGL": "Alphabet Inc.",
                        "AMZN": "Amazon.com Inc.",
                        "TSLA": "Tesla Inc.",
                        "META": "Meta Platforms Inc.",
                        "NVDA": "NVIDIA Corporation",
                        "JPM": "JPMorgan Chase & Co.",
                        "JNJ": "Johnson & Johnson",
                        "V": "Visa Inc.",
                    },
                    "cn": {
                        "000001.SS": "上证指数",
                        "399001.SZ": "深证成指",
                        "000002.SS": "A股指数",
                        "600519.SS": "贵州茅台",
                        "000858.SZ": "五粮液",
                        "601318.SS": "中国平安",
                        "000001.SZ": "平安银行",
                        "002415.SZ": "海康威视",
                        "000002.SZ": "万科A",
                        "600036.SS": "招商银行",
                    },
                    "hk": {
                        "00001.HK": "长和",
                        "00700.HK": "腾讯控股",
                        "03690.HK": "美团点评",
                        "09988.HK": "阿里巴巴",
                        "01810.HK": "小米集团",
                        "00939.HK": "建设银行",
                        "01398.HK": "工商银行",
                        "00388.HK": "香港交易所",
                        "02318.HK": "中国平安",
                        "01109.HK": "华润置地",
                    },
                }

                market_symbols = common_symbols.get(
                    market.lower(), common_symbols["us"]
                )

                results = []
                query_lower = query.lower()

                # Search by symbol
                for symbol, name in market_symbols.items():
                    if query_lower in symbol.lower() or query_lower in name.lower():
                        results.append(
                            {"symbol": symbol, "name": name, "market": market}
                        )
                        if len(results) >= limit:
                            break

                return {
                    "query": query,
                    "market": market,
                    "results": results,
                    "total": len(results),
                }

            except Exception as e:
                logger.error(f"Error searching symbols: {e}")
                return {"error": f"Failed to search symbols: {str(e)}", "query": query}

        @self.mcp.tool()
        async def get_realtime_price(symbol: str, market: str = "us") -> dict[str, Any]:
            """
            Get real-time price for a specific symbol.

            Args:
                symbol: Stock symbol
                market: Market type ("us", "cn", "hk")

            Returns:
                Dictionary with current price information
            """
            try:
                logger.info(f"Getting real-time price for {symbol}")

                market_type = MarketType(market.lower())

                # Get latest data
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

                data = await self.client.get_async(
                    symbol=symbol.upper(),
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=TimeFrame.DAILY,
                    market=market_type,
                )

                if data.data and len(data.data) > 0:
                    point = data.data[-1]  # Latest data point
                    return {
                        "symbol": symbol.upper(),
                        "market": market,
                        "price": float(point.close_price)
                        if point.close_price
                        else None,
                        "change": float(point.close_price - point.open_price)
                        if point.close_price and point.open_price
                        else None,
                        "change_percent": float(
                            (point.close_price - point.open_price)
                            / point.open_price
                            * 100
                        )
                        if point.close_price and point.open_price
                        else None,
                        "volume": int(point.volume) if point.volume else None,
                        "timestamp": point.timestamp.isoformat()
                        if hasattr(point.timestamp, "isoformat")
                        else str(point.timestamp),
                    }
                else:
                    return {"error": "No data available", "symbol": symbol}

            except VPrismError as e:
                logger.error(f"vPrism error getting real-time price: {e}")
                return {"error": str(e), "symbol": symbol}
            except Exception as e:
                logger.error(f"Unexpected error getting real-time price: {e}")
                return {
                    "error": f"Failed to get real-time price: {str(e)}",
                    "symbol": symbol,
                }

        @self.mcp.tool()
        async def get_batch_quotes(
            symbols: list[str], market: str = "us"
        ) -> dict[str, Any]:
            """
            Get real-time quotes for multiple symbols at once.

            Args:
                symbols: List of stock symbols
                market: Market type ("us", "cn", "hk")

            Returns:
                Dictionary with quotes for all requested symbols
            """
            try:
                logger.info(f"Getting batch quotes for {len(symbols)} symbols")

                market_type = MarketType(market.lower())
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

                results = {}
                for symbol in symbols:
                    try:
                        data = await self.client.get_async(
                            symbol=symbol.upper(),
                            start_date=start_date,
                            end_date=end_date,
                            timeframe=TimeFrame.DAILY,
                            market=market_type,
                        )

                        if data.data and len(data.data) > 0:
                            point = data.data[-1]
                            results[symbol.upper()] = {
                                "symbol": symbol.upper(),
                                "price": float(point.close_price)
                                if point.close_price
                                else None,
                                "change": float(point.close_price - point.open_price)
                                if point.close_price and point.open_price
                                else None,
                                "change_percent": float(
                                    (point.close_price - point.open_price)
                                    / point.open_price
                                    * 100
                                )
                                if point.close_price and point.open_price
                                else None,
                                "volume": int(point.volume) if point.volume else None,
                                "timestamp": point.timestamp.isoformat()
                                if hasattr(point.timestamp, "isoformat")
                                else str(point.timestamp),
                            }
                        else:
                            results[symbol.upper()] = {
                                "error": "No data available",
                                "symbol": symbol.upper(),
                            }
                    except Exception as e:
                        results[symbol.upper()] = {
                            "error": str(e),
                            "symbol": symbol.upper(),
                        }

                return {
                    "market": market,
                    "symbols": symbols,
                    "quotes": results,
                    "total": len(results),
                }

            except VPrismError as e:
                logger.error(f"vPrism error getting batch quotes: {e}")
                return {"error": str(e)}
            except Exception as e:
                logger.error(f"Unexpected error getting batch quotes: {e}")
                return {"error": f"Failed to get batch quotes: {str(e)}"}

        @self.mcp.resource("data://markets")
        async def get_available_markets() -> dict[str, Any]:
            """
            Get list of available markets and their characteristics.

            Returns:
                Dictionary with market information
            """
            return {
                "markets": {
                    "us": {
                        "name": "US Stock Market",
                        "description": "United States stock exchanges including NYSE, NASDAQ",
                        "timezone": "EST/EDT",
                        "trading_hours": "9:30 AM - 4:00 PM EST",
                    },
                    "cn": {
                        "name": "China Stock Market",
                        "description": "Chinese stock exchanges including Shanghai and Shenzhen",
                        "timezone": "CST",
                        "trading_hours": "9:30 AM - 3:00 PM CST",
                    },
                    "hk": {
                        "name": "Hong Kong Stock Market",
                        "description": "Hong Kong Stock Exchange",
                        "timezone": "HKT",
                        "trading_hours": "9:30 AM - 4:00 PM HKT",
                    },
                }
            }

        @self.mcp.prompt()
        async def financial_analysis(symbol: str, timeframe: str = "1y") -> str:
            """
            Generate a financial analysis prompt for the given symbol.

            Args:
                symbol: Stock symbol to analyze
                timeframe: Analysis timeframe

            Returns:
                Structured prompt for financial analysis
            """
            return f"""
Please provide a comprehensive financial analysis for {symbol} over the past {timeframe}.

Focus on:
1. Price trends and technical indicators
2. Volume patterns
3. Market sentiment
4. Key support and resistance levels
5. Risk assessment

Use the available financial data tools to gather relevant information and provide actionable insights.
"""

    async def start(self, transport: str = "stdio") -> None:
        """
        Start the MCP server.

        Args:
            transport: Transport method ("stdio", "http", or "sse")
        """
        logger.info(f"Starting vPrism MCP server with {transport} transport")

        try:
            if hasattr(self.client, "initialize"):
                await self.client.initialize()
            await self.mcp.run(transport=transport)
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise
        finally:
            if hasattr(self.client, "close"):
                await self.client.close()

    def run(self, transport: str = "stdio") -> None:
        """Run the MCP server synchronously."""
        asyncio.run(self.start(transport))


def create_mcp_server(config: dict[str, Any] | None = None) -> VPrismMCPServer:
    """
    Create and configure a vPrism MCP server.

    Args:
        config: Optional configuration dictionary

    Returns:
        Configured VPrismMCPServer instance
    """
    return VPrismMCPServer(config=config)


if __name__ == "__main__":
    # Run MCP server directly
    server = create_mcp_server()
    server.run()
