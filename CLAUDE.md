# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Install
uv run pip install -e ".[dev]"

# Dev loop (run in order)
uv run mypy ./vprism
uv run ruff check --fix . && uv run ruff format .
uv run pytest

# Run targets
uv run uvicorn vprism.web.main:app --reload   # Web API
uv run python -m vprism.mcp                    # MCP server (supports --transport {stdio,http,sse})

# Granular testing
uv run pytest tests/path/test_file.py                # single file
uv run pytest tests/path/test_file.py::test_name     # single test
uv run pytest --cov -q                                # with coverage
# Integration tests (network-dependent, skipped by default):
uv run pytest --vprism-run-integration

# Build
uv run python -m build
```

## Architecture

Layered core with strict boundaries — no cross-layer imports.

```
core/
  client/        VPrismClient builds DataQuery, delegates to DataService
  config/        VPrismConfig, CacheConfig, ProviderConfig, LoggingConfig
  data/
    providers/   External source adapters (capability + fetch); lazy imports
    repositories/  Persistence (DataRepository: DataPoint ↔ OHLCVRecord)
    storage/     DuckDB core schema (6 tables) + DatabaseManager
    cache/       Multi-level cache (memory → DuckDB) with TTL
    ingestion/   Raw data validation, batching, dedup → raw_ohlcv table
    schema.py    Extended schemas: raw_ohlcv, quality/drift metrics, corporate actions, reconciliation, shadow
    routing.py   DataRouter — scoring-based provider selection
  services/      DataService, SymbolService, PriceAdjuster
  models/        DataQuery, DataResponse, DataPoint, enums (AssetType, MarketType, TimeFrame)
  patterns/      ExponentialBackoffRetry, CircuitBreaker, ResilientExecutor
  health/        Health checker with component registration
  monitoring/    Performance logging, slow query tracking
  logging/       Structured logging (loguru) + trace propagation
  exceptions/    Domain error hierarchy (VPrismError base)
  validation/    Schema assertion utilities
  plugins/       Plugin loader for CLI extensions
cli/             Typer CLI: `data fetch`, `symbol resolve`
web/             FastAPI app with data + health routes
mcp/             MCP server: get_financial_data, get_market_overview
```

## Data Flow

1. `VPrismClient.get` / `get_async` → builds `DataQuery`
2. `DataService.query_data` → checks multi-level cache (memory → DuckDB)
3. Cache miss → `DataRouter` scores providers (capability match + latency + success rate)
4. Provider fetches → result cached + persisted to DuckDB via `DataRepository`
5. Provider failure → `_fallback_from_storage()` returns previously stored data
6. Web / MCP layer serializes outward

## Provider System

**Default providers** (created by `create_default_providers()`):
- `yahoo` (YFinance) — stocks, forex, crypto; 2000 req/min
- `akshare` (AkShare) — Chinese market: stocks, ETF, fund; 1000 req/min

**AlphaVantage** exists but requires manual instantiation with API key — not in defaults.

**Critical rule**: All provider dependencies use lazy imports via `_ensure_*()` helpers. Provider packages (yfinance, akshare, aiohttp) must NEVER be imported at module level.

**Adding a provider**: Subclass `DataProvider` (implement `capability`, `get_data`, `authenticate`) → register in `factory.py`.

## Database

**Core schema** (`core/data/storage/schema.py`) — 6 tables with DECIMAL(18,8) prices, composite natural keys:
`assets`, `ohlcv`, `symbol_mappings`, `provider_health`, `cache`, `query_log`

**Extended schemas** (`core/data/schema.py`) — additional tables for:
raw ingestion (`raw_ohlcv`), quality metrics, drift metrics, corporate actions, adjustments, reconciliation, shadow runs

## Symbol Normalization

`SymbolService` normalizes raw symbols (e.g., "000001.SZ" → "CN:STOCK:SZ000001"). Priority-ordered rules, LRU cache (10K entries), batch via `normalize_batch()`.

## Hard Rules for This Codebase

- **Python 3.13+** — use modern syntax (`X | Y` unions, etc.)
- **Strict mypy** on `vprism/` (tests excluded) — full type annotations on all public APIs
- **Ruff** line-length 160, rules: E, F, I, N, W, UP, B, C4, SIM, TCH
- **No cross-layer imports** — respect the layering boundaries
- **Lazy provider imports** — inside functions, never module-level
- **`datetime.now(UTC)`** not `datetime.utcnow()`
- **`inspect.iscoroutinefunction`** not `asyncio.iscoroutinefunction`
- **Domain exceptions** — use the `VPrismError` hierarchy, never bare `Exception`
- **Resilience primitives** — use existing retry/circuit breaker patterns, not ad-hoc try/except
- **Structured logging** (loguru) — no `print()`, include contextual fields (provider, symbol, latency_ms)
- **Pydantic validation** at ingress boundaries (web, mcp, public client)
- **Immutable models** — `model_config = {"frozen": True}` unless mutation is required
- **Test naming**: `test_<module>_<behavior>`, Arrange/Act/Assert structure
- **Async tests**: pytest `asyncio_mode=auto` — write async tests directly
- **No real network in tests** — use fakes/mocks; integration tests require `--vprism-run-integration`
- **Dependencies**: runtime in `[project.dependencies]`, providers in `[project.optional-dependencies].providers`, dev tools in `[project.optional-dependencies].dev`
