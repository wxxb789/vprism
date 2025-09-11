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

core/
  client/ -> VPrismClient builds DataQuery, delegates to services.DataRouter
  config/ -> Environment + override settings
  data/
    providers/ -> External source adapters (capability + fetch)
    repositories/ -> Persistence abstraction over storage
    storage/ -> DuckDB schema + DatabaseManager
    cache/ -> Multi-level caching (planned / partial)
    routing.py -> Legacy utilities (prefer services.data_router)
  services/ -> Orchestration (routing, batching, health loop)
  models/ -> Typed domain entities (queries, responses, points, enums)
  patterns/ -> Resilience primitives (retry, circuit breaker)
  monitoring/, logging/ -> Operational telemetry
  validation/ -> Quality & consistency checks
  exceptions/ -> Domain error hierarchy
web/ -> FastAPI app (vprism.web.main:app) modular routes
mcp/ -> MCP server exposing internal data access
tests/ -> Unit + integration across providers, routing, persistence, quality, web, MCP

## Core Data Flow

1. VPrismClient.get / get_async builds DataQuery
2. DataRouter asks ProviderRegistry for first healthy capable provider
3. Provider validates capability, fetches, returns DataResponse/DataPoints
4. Optional: repository persists/queries via DuckDB -> DataRecord
5. Validation enforces quality & consistency
6. Resilience patterns wrap provider calls
7. Web (FastAPI) or MCP layer serializes outward

## Provider Selection & Health
ProviderRegistry: instances + lazy capability + health flags.
Health loop: start_health_check updates provider_health periodically.
Routing heuristic: first healthy capable provider (candidate future scoring: latency, historical success, capability breadth).

## Persistence & Caching
storage/database.py + models.py: DuckDB schema + access patterns.
repositories/data.py: DataPoint -> DataRecord mapping & filtered queries.
cache/: planned multi-level short‑circuiting; inspect integration points before adding logic.

## Testing Guidance
Async: rely on pytest asyncio_mode=auto (write async tests directly).
Focused tests around providers, routing, resilience, validation.
Tests excluded from mypy; keep strict typing in library code.

## Type & Style Conventions
Strict mypy on vprism/ (retain full annotations).
Ruff enforces imports, style, line length 160; run fix + format in dev loop.

## Extension Points
Providers: subclass DataProvider (capability property, get_data, authenticate) + register in factory/create_default_providers.
Routing: evolve DataRouter.route_query with scoring (latency, health %, capability richness).
Persistence: extend DatabaseManager + repositories (keep services thin).

## MCP & Web Service
MCP: uv run python -m vprism.mcp exposes internal data.
FastAPI: uv run uvicorn vprism.web.main:app --reload (routes in web/routes/).

## Notes for Future Automation (Claude)
Maintain Python 3.11 compatibility; update pyproject.toml for deps.
Preserve layering; avoid unsolicited large refactors.
Prefer existing resilience primitives over ad-hoc try/except.

