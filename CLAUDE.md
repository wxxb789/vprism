# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Key Development Commands

Environment / Install:
uv run pip install -e ".[dev]"

Tests:
uv run pytest
Single file: uv run pytest tests/path/test_file.py
Single test: uv run pytest tests/path/test_file.py::test_name
Coverage (optional): uv run pytest --cov -q

Lint & Format:
uv run ruff check .
uv run ruff check --fix .
uv run ruff format .

Type Checking:
uv run mypy ./vprism

Run Web API (FastAPI):
uv run uvicorn vprism.web.main:app --reload

Run MCP Server:
uv run python -m vprism.mcp

Build Wheel:
uv run python -m build

Dev Loop Suggestion:
1. uv run mypy ./vprism
2. uv run ruff check --fix . && uv run ruff format .
3. uv run pytest
4. uv run uvicorn vprism.web.main:app --reload (as needed)

## High-Level Architecture

Layered core with explicit boundaries; avoid cross-layer leakage.

```
core/
  client/       -> VPrismClient builds DataQuery, delegates to DataService
  config/       -> Unified settings (VPrismConfig, CacheConfig, ProviderConfig, LoggingConfig)
  data/
    providers/  -> External source adapters (capability + fetch); lazy imports
    repositories/ -> Persistence abstraction (DataRepository: DataPoint ↔ OHLCVRecord)
    storage/    -> DuckDB schema (6 tables) + DatabaseManager
    cache/      -> Multi-level caching (memory + DuckDB-backed)
    routing.py  -> DataRouter with scoring-based provider selection
  services/     -> Orchestration: DataService, SymbolService, PriceAdjuster
  models/       -> Typed domain entities (queries, responses, points, enums)
  patterns/     -> Resilience primitives (ExponentialBackoffRetry, CircuitBreaker, ResilientExecutor)
  health/       -> Health checker with component registration
  monitoring/   -> Performance logging, slow query tracking
  logging/      -> Structured logging with loguru + trace propagation
  exceptions/   -> Domain error hierarchy
  validation/   -> Schema assertion utilities
  plugins/      -> Plugin loader for CLI extensions
cli/            -> Typer CLI: data fetch + symbol resolve
web/            -> FastAPI app (vprism.web.main:app) with data + health routes
mcp/            -> MCP server: 2 tools (get_financial_data, get_market_overview)
tests/          -> Unit + integration: providers, routing, schema, symbols, resilience, CLI, web, MCP
```

## Database Schema (6 tables)

The DuckDB schema uses DECIMAL(18,8) for prices, composite natural keys, FK/CHECK constraints:

| Table | Purpose | Primary Key |
|-------|---------|------------|
| `assets` | Master asset data | (symbol, market) |
| `ohlcv` | Unified price data | (symbol, market, ts, timeframe, provider) |
| `symbol_mappings` | Raw→canonical mappings | (canonical, raw_symbol, market, source) |
| `provider_health` | Provider status/metrics | (name) |
| `cache` | Query result cache | (key) |
| `query_log` | Query audit trail | (id) |

Schema is managed by `core/data/storage/schema.py` (DatabaseSchema class).

## Core Data Flow

1. VPrismClient.get / get_async builds DataQuery
2. DataService.query_data checks multi-level cache
3. On cache miss: DataRouter scores providers by capability + historical performance
4. Provider validates capability, fetches, returns DataResponse/DataPoints
5. DataService caches result + persists to DuckDB via DataRepository
6. On provider failure: DataService falls back to stored data via _fallback_from_storage()
7. Web (FastAPI) or MCP layer serializes outward

## Provider System

### Lazy Imports
All provider dependencies (yfinance, akshare, aiohttp) use lazy imports via `_ensure_*()` helper functions. This ensures `import vprism` works without provider packages installed.

### Provider Selection
DataRouter uses scoring: capability match (0.2 per dimension) + latency penalty + historical success rate. Scores are updated via `update_provider_score()` after each request.

### Current Providers
- `yahoo` (YFinanceProvider) — stocks, forex, crypto; rate limit 2000 req/min
- `akshare` (AkShareProvider) — Chinese market data; rate limit 1000 req/min
- `alpha_vantage` (AlphaVantageProvider) — stocks, forex, crypto with API key

### Adding a Provider
Subclass `DataProvider` (capability property, get_data, authenticate) → register in `factory/create_default_providers`.

## Symbol Normalization

`SymbolService` normalizes raw symbols (e.g., "000001.SZ", "sh600519") into canonical form (e.g., "CN:STOCK:SZ000001"). Uses priority-ordered rules with LRU cache (10K entries). Batch normalization via `normalize_batch()`.

## Exception Hierarchy

- `VPrismError` → base
- `ProviderError` → data source failures
- `RateLimitError` → rate limit exceeded
- `DataValidationError` → input/output validation
- `NetworkError` → connectivity issues
- `CacheError` → cache failures
- `AuthenticationError` → auth failures
- `NoCapableProviderError` → no provider matches query
- `NoAvailableProviderError` → all providers unavailable
- `UnresolvedSymbolError` → symbol normalization failures
- `DomainError` → domain logic errors

## MCP Server

2 tools:
- `get_financial_data(symbol, start_date, end_date, timeframe, market, asset_type)` — historical/real-time data
- `get_market_overview(market, date)` — major index overview

## CLI

2 command groups:
- `data fetch` — fetch market data with configurable output (table/jsonl)
- `symbol resolve` — normalize a raw symbol

Global options: `--format`, `--output`, `--log-level`, `--no-color`

## Persistence & Caching

- `storage/database.py`: DatabaseManager for CRUD operations
- `storage/schema.py`: DatabaseSchema — creates/validates 6-table schema
- `repositories/data.py`: DataRepository — DataPoint ↔ OHLCVRecord mapping + batch save/query
- `cache/multilevel.py`: MultiLevelCache (memory → DuckDB) with TTL

## Resilience Patterns

- `patterns/retry.py`: ExponentialBackoffRetry with configurable RetryConfig
- `patterns/circuitbreaker.py`: CircuitBreaker with state machine (CLOSED → OPEN → HALF_OPEN); lock only held during state transitions, not during func execution
- `patterns/resilient.py`: ResilientExecutor combining retry + circuit breaker

## Testing Guidance

Async: rely on pytest asyncio_mode=auto (write async tests directly).
Focused tests around providers, routing, schema, symbols, resilience.
Tests excluded from mypy; keep strict typing in library code.
Optional provider tests (yfinance) automatically skip when package unavailable.

## Type & Style Conventions

Strict mypy on vprism/ (retain full annotations).
Ruff enforces imports, style, line length 160; run fix + format in dev loop.

## Dependencies

Runtime deps in `[project.dependencies]`. Provider packages (akshare, yfinance, aiohttp) in `[project.optional-dependencies].providers`. Dev tools in `[project.optional-dependencies].dev`.

## Notes for Future Automation (Claude)

Maintain Python 3.13+ compatibility; update pyproject.toml for deps.
Preserve layering; avoid unsolicited large refactors.
Prefer existing resilience primitives over ad-hoc try/except.
All provider imports must be lazy (inside functions, not module-level).
Use `datetime.now(UTC)` not `datetime.utcnow()`.
Use `inspect.iscoroutinefunction` not `asyncio.iscoroutinefunction`.

---

# Code Quality System

## Baseline Principles
- Python Version: 3.13+ only (use `py313` target in tooling)
- Type System: 100% annotated public surface; internal functions may use inferred generics sparingly
- Static Gates: Ruff (style, import hygiene, anti-patterns), mypy strict, optional pytest --cov quality gates
- CI MUST block on: mypy, ruff (no warnings), pytest (all green)

## Layers of Quality
1. Design Level
  - Single Responsibility per module; cross-layer imports forbidden (enforced via periodic grep audit)
  - Explicit provider capability contracts; never infer via side effects
  - Data models are immutable unless mutation is a domain requirement
2. Implementation Level
  - No hidden global state; configuration flows through explicit objects
  - Use resilience primitives (retry, circuit breaker) instead of ad-hoc try/except
  - Enforce timeouts on all network + I/O boundaries
3. Verification Level
  - Static: mypy strict (no ignores except third-party stubs with justification)
  - Behavioral: pytest focuses on externally observable outcomes; avoid over-specifying internals
  - Contract: Pydantic validation at ingress (web, mcp, public client)
4. Operational Level
  - Structured logging (no print) with contextual fields (provider, symbol, latency_ms)
  - Expose health endpoints; no business logic in health checks
  - Progressive degradation: fail fast on provider errors, fall back to stored data

## Code Review Checklist (Mandatory)
- Boundary Clarity: New code respects layering
- Type Integrity: No Any leakage across module boundaries
- Error Semantics: Domain exceptions not generic Exception
- Resource Safety: Async contexts properly awaited; files/sessions closed
- Performance: No N+1 loops over provider/data store calls
- Observability: Meaningful log/metric hooks for new behaviors
- Security: No secret logging; crypto primitives from stdlib/approved libs only

## Testing Standards
- Naming: test_<module>_<behavior>
- Structure: Arrange / Act / Assert blocks separated by blank line
- Determinism: No real network; use fakes/mocks with explicit data
- Parametrize for input domain coverage; prefer hypothesis where boundary-heavy
- Performance Tests: Mark with @pytest.mark.perf to allow CI exclusion by default

## Dependency Hygiene
- All runtime deps declared in [project.dependencies]
- Provider packages in [project.optional-dependencies].providers (lazy imported at runtime)
- dev extras only for tooling (lint, type, test)
- Remove unused deps quarterly (script TODO)
- Pin minimum versions only; rely on uv.lock for resolution

## Documentation Alignment
- Each new public class/function gets docstring (purpose, params, returns, raises)
- Update README / docs when adding provider capabilities or config keys
- Keep architectural narrative (this file) the single source for layering rules

## Anti-Patterns (Reject in Review)
- Silent except: pass
- Wildcard imports
- Direct datetime.utcnow() without timezone awareness
- Inlined JSON/YAML longer than 10 lines (extract resource file if needed)
- Boolean parameter explosion (prefer small strategy objects)
- Module-level imports of optional provider packages (use lazy imports)

## Automation Roadmap
- Add pre-commit with ruff + mypy + minimal import cycles check
- Introduce coverage threshold gate (e.g. 85%)
- Add dependency freshness report (monthly)
- Add architectural import boundary test

---

# Prime Directives of Code Craft

These directives extend existing guidance; they are philosophical additions and do not override specific project constraints (e.g., current Ruff line length 160, Python 3.13 baseline).

## I. Single Source of Truth
Centralize dependency & tooling config in pyproject.toml. Use uv for environment + locking. No requirements.txt. (A lock file may be added if reproducibility demands it.) Keep tool configs (ruff, mypy) unified there. CI must enforce ruff + mypy.

Example (illustrative only; adapt to current repo standards):
```toml
[tool.ruff]
# (Project currently uses line length 160; example below is philosophical.)
line-length = 160

[tool.mypy]
python_version = "3.13"
strict = true
```

## II. Strong Structures First
Model domain before logic. Favor explicit Pydantic models for inputs/outputs/boundaries. Prefer immutability (`model_config = {"frozen": True}`) when feasible.
```python
from __future__ import annotations
from pydantic import BaseModel, Field, EmailStr
from typing import TypeVar

UserID = int
TUser = TypeVar("TUser", bound="User")

class User(BaseModel):
    """Immutable user contract."""
    model_config = {"frozen": True}
    id: UserID
    name: str = Field(min_length=1)
    email: EmailStr
```

## III. Absolute Clarity
Optimize for the reader. No magic numbers; extract constants. Keep functions single-purpose. Use precise typing; prefer modern union syntax (X | Y). Avoid silent exception suppression—use contextlib.suppress intentionally.
```python
import contextlib
from typing import Sequence

REQUEST_TIMEOUT_SECONDS = 30.0

def find_user(users: Sequence[User], user_id: UserID) -> User | None:
    for u in users:
        if u.id == user_id:
            return u
    return None

def load_optional_config(path: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        # Explicitly acceptable if file missing
        data = open(path, "r", encoding="utf-8").read()
        # process(data)
```

## IV. Trust, Then Verify
Layered verification:
1. Static: mypy --strict.
2. Structural: Pydantic validation at boundaries.
3. Behavioral: pytest (focus on externally observable behavior, not internals).

Use fixtures for clarity; parametrize for coverage.

## V. Humane Interfaces
CLI: prefer Typer for typed, discoverable commands. Output: Rich for user-facing formatting (avoid raw print for UX surfaces). Internal debug logging still uses logging module.
```python
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

@app.command()
def list_users() -> None:
    users = []  # placeholder for retrieval
    table = Table("ID", "Name", "Email")
    for u in users:
        table.add_row(str(u.id), u.name, u.email)
    console.print(table)
```

## VI. Mindset of Scale
Think about algorithmic complexity, batching vs per-item I/O, memory footprint (stream instead of load-all where practical). Avoid premature micro-optimizations; design for observability so scaling decisions are data-driven later.

---
