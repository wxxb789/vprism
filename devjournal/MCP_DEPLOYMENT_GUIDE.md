# vprism MCP Server Deployment Guide

## Overview

vprism now supports the Model Context Protocol (MCP), providing AI applications with standardized access to real-time and historical financial data through MCP tools, resources, and prompts.

## Features

### Tools
- **get_stock_data**: Retrieve historical stock data with OHLCV values
- **get_market_overview**: Get market indices and overview data
- **search_symbols**: Search for stock symbols by name or ticker
- **get_realtime_price**: Get current price for a symbol
- **get_batch_quotes**: Get real-time quotes for multiple symbols

### Resources
- **data://markets**: Available markets and their characteristics

### Prompts
- **financial_analysis**: Generate structured financial analysis prompts

## Quick Start

### 1. Installation

```bash
# Install vprism with MCP support
pip install -e .

# Or install with MCP dependencies
pip install fastmcp>=2.10.6
```

### 2. Running MCP Server

#### STDIO Mode (Default)
```bash
# Run MCP server with stdio transport
python -m vprism.mcp

# Or using main.py
python main.py mcp
```

#### HTTP Mode
```bash
# Run MCP server with HTTP transport
python -m vprism.mcp --transport http --host 127.0.0.1 --port 8001

# Or
python -m vprism.mcp --transport http
```

#### SSE Mode
```bash
# Run MCP server with SSE transport
python -m vprism.mcp --transport sse --host 127.0.0.1 --port 8001
```

### 3. MCP Configuration

Create an `mcp_config.json` file:

```json
{
  "name": "vprism-financial-data",
  "version": "0.1.0",
  "description": "vprism Financial Data Platform MCP Server",
  "transport": {
    "stdio": {
      "command": "python",
      "args": ["-m", "vprism.mcp"]
    }
  }
}
```

## Integration with AI Applications

### Claude Desktop

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "vprism": {
      "command": "python",
      "args": ["-m", "vprism.mcp"],
      "env": {}
    }
  }
}
```

### Custom Python Client

```python
from fastmcp import Client

async def main():
    async with Client("stdio", command=["python", "-m", "mcp"]) as client:
        # List available tools
        tools = await client.list_tools()
        print("Available tools:", [t.name for t in tools])
        
        # Get stock data
        data = await client.call_tool("get_stock_data", {
            "symbol": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31"
        })
        print("AAPL data:", data)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Available Tools

### get_stock_data

Retrieve historical stock data for a specific symbol.

**Parameters:**
- `symbol` (str): Stock symbol (e.g., "AAPL", "MSFT", "TSLA")
- `start_date` (str): Start date in YYYY-MM-DD format
- `end_date` (str): End date in YYYY-MM-DD format
- `timeframe` (str, optional): Data timeframe ("1d", "1h", "5m", "1m") - default: "1d"
- `market` (str, optional): Market type ("us", "cn", "hk") - default: "us"

**Example:**
```json
{
  "symbol": "AAPL",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "timeframe": "1d",
  "market": "us"
}
```

### get_market_overview

Get market overview data including major indices.

**Parameters:**
- `market` (str, optional): Market type ("us", "cn", "hk") - default: "us"
- `date` (str, optional): Specific date (YYYY-MM-DD), defaults to latest

### search_symbols

Search for stock symbols by name or ticker.

**Parameters:**
- `query` (str): Search query
- `market` (str, optional): Market type ("us", "cn", "hk") - default: "us"
- `limit` (int, optional): Maximum results to return - default: 10

### get_realtime_price

Get current price for a specific symbol.

**Parameters:**
- `symbol` (str): Stock symbol
- `market` (str, optional): Market type ("us", "cn", "hk") - default: "us"

### get_batch_quotes

Get real-time quotes for multiple symbols at once.

**Parameters:**
- `symbols` (list[str]): List of stock symbols
- `market` (str, optional): Market type ("us", "cn", "hk") - default: "us"

## Resources

### data://markets

Provides information about available markets.

**Example:**
```json
{
  "markets": {
    "us": {
      "name": "US Stock Market",
      "description": "United States stock exchanges including NYSE, NASDAQ",
      "timezone": "EST/EDT",
      "trading_hours": "9:30 AM - 4:00 PM EST"
    }
  }
}
```

## Prompts

### financial_analysis

Generates structured prompts for financial analysis.

**Parameters:**
- `symbol` (str): Stock symbol to analyze
- `timeframe` (str, optional): Analysis timeframe - default: "1y"

## Configuration

### Environment Variables

- `VPRISM_CACHE_ENABLED`: Enable/disable caching (default: true)
- `VPRISM_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `VPRISM_TIMEOUT`: Request timeout in seconds (default: 30)

### Configuration File

Create `mcp_config.yaml`:

```yaml
name: vprism-financial-data
version: 0.1.0
description: vprism Financial Data Platform MCP Server

logging:
  level: INFO

features:
  realtime_data: true
  historical_data: true
  batch_queries: true
```

## Error Handling

The MCP server includes comprehensive error handling:

- **Invalid symbols**: Returns error message with symbol information
- **Date format errors**: Handles gracefully with appropriate messages
- **Network issues**: Provides clear error descriptions
- **Rate limiting**: Includes retry information when applicable

## Testing

Run the comprehensive test suite:

```bash
# Run all MCP tests
pytest tests/test_mcp_server.py -v

# Run with coverage
pytest tests/test_mcp_server.py --cov=mcp --cov-report=html
```

## Performance Optimization

### Caching
- Automatic caching of frequently requested data
- Configurable cache TTL based on data type
- Multi-level cache (memory + database)

### Batch Processing
- Efficient batch queries to reduce API calls
- Parallel data fetching for multiple symbols
- Optimized data aggregation

## Deployment Options

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -e .

EXPOSE 8001
CMD ["python", "-m", "mcp", "--transport", "http", "--host", "0.0.0.0"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  mcp:
    build: .
    ports:
      - "8001:8001"
    environment:
      - VPRISM_LOG_LEVEL=INFO
    command: ["python", "-m", "mcp", "--transport", "http", "--host", "0.0.0.0"]
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mcp
  template:
    metadata:
      labels:
        app: mcp
    spec:
      containers:
      - name: mcp
        image: vprism:latest
        ports:
        - containerPort: 8001
        env:
        - name: VPRISM_LOG_LEVEL
          value: "INFO"
        command: ["python", "-m", "mcp", "--transport", "http", "--host", "0.0.0.0"]
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure `fastmcp>=2.10.6` is installed
2. **Connection refused**: Check if server is running on correct port
3. **Tool not found**: Verify server initialization completed successfully
4. **Data timeout**: Check network connectivity and API limits

### Debug Mode

Enable debug logging:

```bash
python -m vprism.mcp --debug
# or
VPRISM_LOG_LEVEL=DEBUG python -m vprism.mcp
```

### Health Check

The server includes health check endpoints:

- **HTTP mode**: `GET /health`
- **STDIO mode**: Use `get_market_overview` tool as health check

## Security

- Input validation and sanitization
- Rate limiting protection
- Secure configuration handling
- No sensitive data in logs

## Monitoring

- Structured logging with loguru
- Prometheus metrics support
- Health check endpoints
- Error tracking and alerting

## Contributing

When adding new MCP tools:

1. Update `vprism/mcp/server.py`
2. Add comprehensive tests in `tests/test_mcp_server.py`
3. Update this documentation
4. Add configuration options if needed