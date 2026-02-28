# vprism - Unified Financial Data Platform

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

vprism is a financial data platform that provides unified access to multiple data sources through consistent, high-performance APIs. It abstracts away the complexity of managing multiple data providers, rate limits, and data format inconsistencies.

## Quick Start

### Installation
```bash
pip install vprism

# With provider packages
pip install vprism[providers]
```

### Python Library
```python
from vprism.core.services.data import DataService

service = DataService()

# Simple API
response = await service.get("AAPL", start="2024-01-01", end="2024-12-31")

# Chinese market
response = await service.get("000001", market=MarketType.CN)

# Fluent API
response = await service.query() \
    .symbols(["AAPL", "GOOGL"]) \
    .start("2024-01-01") \
    .period("1y") \
    .get()
```

### MCP Server (for AI assistants)
```bash
python -m vprism.mcp
```

### Web API
```bash
uvicorn vprism.web.main:app --reload
```

### CLI
```bash
# Fetch market data
vprism data fetch --symbols AAPL --start 2024-01-01 --format table

# Resolve a symbol
vprism symbol resolve --raw-symbol 000001.SZ
```

## Architecture

```
vprism/
├── core/
│   ├── client/          # VPrismClient — high-level entry point
│   ├── config/          # Unified settings (VPrismConfig)
│   ├── data/
│   │   ├── providers/   # Yahoo Finance, Alpha Vantage, AkShare
│   │   ├── repositories/# DataRepository (DataPoint ↔ OHLCVRecord)
│   │   ├── storage/     # DuckDB (6 tables) + DatabaseManager
│   │   ├── cache/       # Multi-level cache (memory + DuckDB)
│   │   └── routing.py   # Provider scoring and selection
│   ├── services/        # DataService, SymbolService, PriceAdjuster
│   ├── models/          # DataQuery, DataResponse, DataPoint, enums
│   ├── patterns/        # Retry, CircuitBreaker, ResilientExecutor
│   ├── health/          # Component health checks
│   ├── monitoring/      # Performance logging, slow query tracking
│   ├── logging/         # Structured logging (loguru)
│   └── exceptions/      # Domain error hierarchy
├── cli/                 # Typer CLI: data fetch, symbol resolve
├── web/                 # FastAPI with data + health routes
├── mcp/                 # MCP server: get_financial_data, get_market_overview
└── tests/               # Unit + integration tests
```

### Data Flow

```
Request → Cache check → Provider (via DataRouter scoring) → Cache + Store → Response
                                                      ↘ On failure: Storage fallback
```

1. **DataService** checks multi-level cache (memory → DuckDB)
2. On cache miss, **DataRouter** scores providers by capability + historical performance
3. Best provider fetches data; result is cached and persisted
4. On provider failure, falls back to previously stored data

## Data Sources

| Provider | Markets | Auth |
|----------|---------|------|
| **Yahoo Finance** | US, global stocks, forex, crypto | None |
| **Alpha Vantage** | US, global stocks, forex, crypto | API key |
| **AkShare** | Chinese A-shares, indices | None |

All provider dependencies use lazy imports — `import vprism` works without any provider packages installed.

### Adding a Provider

Subclass `DataProvider`, implement `capability`, `get_data`, and `authenticate`, then register in `factory/create_default_providers`.

## Resilience

- **Exponential backoff retry** with configurable attempts, delay, and exceptions
- **Circuit breaker** with CLOSED → OPEN → HALF_OPEN state machine
- **ResilientExecutor** combining both patterns
- **Automatic failover** to stored data when providers are unavailable

## Database

DuckDB with 6 tables using DECIMAL(18,8) for prices:

| Table | Purpose |
|-------|---------|
| `assets` | Master asset data |
| `ohlcv` | Unified OHLCV price data |
| `symbol_mappings` | Raw → canonical symbol mappings |
| `provider_health` | Provider status and metrics |
| `cache` | Query result cache with TTL |
| `query_log` | Query audit trail |

## Development

```bash
# Setup
git clone https://github.com/wxxb789/vprism.git
cd vprism
uv run pip install -e ".[dev]"

# Dev loop
uv run mypy ./vprism
uv run ruff check --fix . && uv run ruff format .
uv run pytest
```

### Tools
- **uv** for environment and dependency management
- **ruff** for linting and formatting (line length 160)
- **mypy** strict mode on vprism/
- **pytest** with asyncio_mode=auto

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Links

- **[GitHub](https://github.com/wxxb789/vprism)**
- **[Issues](https://github.com/wxxb789/vprism/issues)**

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/), [DuckDB](https://duckdb.org/), [loguru](https://github.com/Delgan/loguru)
- Data providers: Yahoo Finance, Alpha Vantage, AkShare
