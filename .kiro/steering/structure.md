# vprism Project Structure - IMPLEMENTED

## CRITICAL DIRECTORY STRUCTURE RULES

**⚠️ STRICT ENFORCEMENT:**
- **Git root**: `Q:/repos/my/vprism/` (NEVER create subdirectories with source code)
- **Source code ONLY**: `Q:/repos/my/vprism/src/vprism/` (ABSOLUTE PATH)
- **Test code ONLY**: `Q:/repos/my/vprism/tests/` (ABSOLUTE PATH)
- **DEV JOURNAL**: `Q:/repos/my/vprism/devjournal/` - Development journal and notes
- **USER GUIDE**: `Q:/repos/my/vprism/guide/` - User documentation and guides
- **NO EXCEPTIONS**: Never create `Q:/repos/my/vprism/vprism/` or similar duplicates

## Root Directory Organization - IMPLEMENTED

```
vprism/
├── src/vprism/           # Main application source code (IMPLEMENTED) - ONLY HERE
├── tests/                # Comprehensive test suite (IMPLEMENTED) - ONLY HERE
├── devjournal/           # Development journal and notes (MANDATORY)
├── guide/                # User documentation and guides (MANDATORY)
├── pyproject.toml        # Project configuration (IMPLEMENTED)
├── uv.lock              # Locked dependency versions (IMPLEMENTED)
├── README.md            # Project overview (IMPLEMENTED)
├── Dockerfile           # Multi-stage container build (IMPLEMENTED)
├── docker-compose.yml   # Development environment (IMPLEMENTED)
├── .kiro/               # Steering documentation (IMPLEMENTED)
└── .git/                # Git repository (PROTECTED)
```

## DIRECTORY VIOLATION CHECKLIST

**❌ NEVER ALLOWED:**
- `Q:/repos/my/vprism/vprism/` (duplicate root)
- `Q:/repos/my/vprism/vprism/src/vprism/` (nested duplication)
- Any source code outside `src/vprism/`
- Any test code outside `tests/`

**✅ ALWAYS ENSURE:**
- All `.py` files in `src/vprism/` or `tests/`
- No duplicate package structures
- Single source of truth for each file type

## Core Package Structure

### `src/vprism/` - Main Application Package - IMPLEMENTED
```
vprism/
├── __init__.py          # Package initialization and exports (IMPLEMENTED)
│   # Library Mode APIs:
│   # - vprism.get() - Simple sync data retrieval
│   # - vprism.get_async() - Simple async data retrieval
│   # - vprism.query() - Query builder for complex queries
│   # - vprism.execute() - Execute built queries
│   # - vprism.configure() - Global configuration management
├── core/                # Core business logic and services (IMPLEMENTED)
│   ├── __init__.py
│   ├── exceptions.py    # Custom exception hierarchy
│   ├── interfaces/      # Domain interfaces
│   ├── models.py        # Core domain models
│   ├── services/        # Business logic services
│   └── client.py        # Main client interface
├── infrastructure/      # Infrastructure layer (IMPLEMENTED)
│   ├── __init__.py
│   ├── cache/           # Multi-level caching implementation
│   ├── providers/       # Data provider adapters
│   ├── repositories/    # Data persistence layer
│   ├── router.py        # Data routing service
│   └── storage/         # Database schema and operations
├── web/                 # Web API layer - IMPLEMENTED
│   ├── __init__.py
│   ├── app.py           # FastAPI application factory
│   ├── models.py        # Web API request/response models
│   ├── main.py          # Web service entry point
│   └── routes/          # API route handlers
│       ├── __init__.py
│       ├── data_routes.py    # Financial data endpoints
│       └── health_routes.py  # Health monitoring endpoints
└── exceptions/          # Exception definitions

### `src/vprism/mcp/` - MCP Server - COMPLETED ✅
```
mcp/
├── __init__.py      # MCP server exports
├── __main__.py      # CLI entry point for MCP mode
└── server.py        # FastMCP server implementation
```
```

### `core/` - Business Logic Layer - IMPLEMENTED
```
core/
├── __init__.py
├── exceptions.py        # Custom exception hierarchy (IMPLEMENTED)
├── interfaces/          # Domain interfaces
├── models.py            # Core domain models (IMPLEMENTED)
└── services/            # Business logic services
    └── data_router.py   # Main data routing service (IMPLEMENTED)
```

**Responsibilities:**
- Orchestrates data flow between providers, cache, and consumers (IMPLEMENTED)
- Implements business rules and data processing logic (IMPLEMENTED)
- Manages configuration and environment settings (IMPLEMENTED)
- Handles provider selection and failover strategies (IMPLEMENTED)

### `infrastructure/cache/` - Multi-level Caching - IMPLEMENTED
```
cache/
├── __init__.py
├── base.py              # Cache interface and base classes (IMPLEMENTED)
├── cache_key.py         # Cache key generation utilities (IMPLEMENTED)
├── memory.py            # Thread-safe in-memory cache (IMPLEMENTED)
├── duckdb.py            # DuckDB-based persistent cache (IMPLEMENTED)
├── key.py               # Cache key utilities (IMPLEMENTED)
└── multilevel.py        # Multi-level cache orchestration (IMPLEMENTED)
```

### `infrastructure/providers/` - Data Provider Adapters - IMPLEMENTED
```
providers/
├── __init__.py
├── base.py              # Abstract base provider interface (IMPLEMENTED)
├── registry.py          # Provider registration and discovery (IMPLEMENTED)
├── akshare_provider.py  # AkShare Chinese market data (IMPLEMENTED)
├── alpha_vantage_provider.py # Alpha Vantage API provider (IMPLEMENTED)
├── vprism_provider.py   # Internal vprism provider (IMPLEMENTED)
└── yfinance_provider.py # Yahoo Finance provider (IMPLEMENTED)
```

**Design Patterns:**
- **Strategy Pattern**: Each provider implements a common interface (IMPLEMENTED)
- **Registry Pattern**: Dynamic provider discovery and registration (IMPLEMENTED)
- **Adapter Pattern**: Normalize different provider APIs to common format (IMPLEMENTED)
- **Capability Discovery**: Runtime provider capability detection (IMPLEMENTED)

### `infrastructure/repositories/` - Data Persistence Layer - IMPLEMENTED
```
repositories/
├── __init__.py
├── base.py              # Base repository interface (IMPLEMENTED)
├── cache.py             # Cache repository for multi-level caching (IMPLEMENTED)
├── data.py              # Data repository for financial data (IMPLEMENTED)
├── provider.py          # Provider repository for data sources (IMPLEMENTED)
└── query.py             # Query repository for query management (IMPLEMENTED)
```

### `infrastructure/storage/` - Database Schema and Operations - IMPLEMENTED
```
storage/
├── __init__.py
├── database.py          # DuckDB connection and management (IMPLEMENTED)
├── database_schema.py   # Database table definitions and indexing (IMPLEMENTED)
├── models.py            # Database models and schemas (IMPLEMENTED)
└── schema.py            # Schema versioning and migrations (IMPLEMENTED)
```

**Storage Features:**
- **6 Optimized Tables**: asset_info, daily_ohlcv, intraday_ohlcv, real_time_quotes, cache_entries, data_quality (IMPLEMENTED)
- **Proper Indexing**: Composite primary keys, date indexes, symbol indexes (IMPLEMENTED)
- **Partitioned Views**: Year-based partitioning for large datasets (IMPLEMENTED)
- **Materialized Views**: Latest prices and monthly statistics (IMPLEMENTED)

### `tests/` - Comprehensive Test Suite - IMPLEMENTED ✅
```
tests/
├── __init__.py
├── test_cache.py              # Multi-level caching tests (IMPLEMENTED)
├── test_data_router.py        # Data routing service tests (IMPLEMENTED)
├── test_providers.py          # Provider integration tests (IMPLEMENTED)
├── test_repositories.py       # Repository layer tests (IMPLEMENTED)
├── test_storage.py            # Database and storage tests (IMPLEMENTED)
├── test_error_handling.py     # Comprehensive error handling tests (IMPLEMENTED)
├── test_circuit_breaker.py    # Circuit breaker pattern tests (IMPLEMENTED)
├── test_retry.py              # Retry mechanism tests (IMPLEMENTED)
├── test_data_quality.py       # Data quality system tests (IMPLEMENTED)
├── test_quality_system.py     # Comprehensive quality assurance tests (IMPLEMENTED)
├── test_consistency.py        # Data consistency validation tests (IMPLEMENTED)
├── test_batch_processor.py    # Batch processing tests (IMPLEMENTED)
├── test_web_service.py        # Web API endpoint tests (IMPLEMENTED)
├── test_mcp_server.py         # MCP server integration tests (IMPLEMENTED)
└── test_library_interface.py  # Library mode API tests (IMPLEMENTED)
```

**Testing Strategy:**
- **Unit Tests**: Test individual functions and classes in isolation (IMPLEMENTED)
- **Integration Tests**: Test provider integrations with mocked/external APIs (IMPLEMENTED)
- **Coverage**: Comprehensive test coverage for all major components (IMPLEMENTED)

