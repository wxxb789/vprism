# vprism Project Structure

## Root Directory Organization

```
vprism/
├── src/vprism/           # Main application source code
├── tests/                # Comprehensive test suite
├── docs/                 # Documentation and API references
├── scripts/              # Development and deployment scripts
├── examples/             # Usage examples and tutorials
├── pyproject.toml        # Project configuration and dependencies
├── uv.lock              # Locked dependency versions
├── Dockerfile           # Multi-stage container build
├── docker-compose.yml   # Development environment orchestration
└── README.md           # Project overview and quick start
```

## Core Package Structure

### `src/vprism/` - Main Application Package
```
vprism/
├── __init__.py          # Package initialization and exports
├── core/                # Core business logic and services
├── providers/           # Data provider integrations
├── models/              # Pydantic data models and enums
├── cache/               # Caching strategies and implementations
├── web/                 # FastAPI web layer and endpoints
├── cli/                 # Command-line interface
└── utils/               # Shared utilities and helpers
```

### `core/` - Business Logic Layer
```
core/
├── __init__.py
├── service.py           # Main DataService orchestrator
├── processors/          # Data processing and transformation
├── validators/          # Data validation and quality checks
└── config.py           # Application configuration
```

**Responsibilities:**
- Orchestrates data flow between providers, cache, and consumers
- Implements business rules and data processing logic
- Manages configuration and environment settings
- Handles provider selection and failover strategies

### `providers/` - Data Provider Integrations
```
providers/
├── __init__.py
├── base.py             # Abstract base provider interface
├── registry.py         # Provider registration and discovery
├── alpha_vantage.py    # Alpha Vantage API provider
├── yahoo_finance.py    # Yahoo Finance provider
├── quandl.py          # Quandl data provider
└── local.py           # Local file/directory provider
```

**Design Patterns:**
- **Strategy Pattern**: Each provider implements a common interface
- **Registry Pattern**: Dynamic provider discovery and registration
- **Adapter Pattern**: Normalize different provider APIs to common format

### `models/` - Data Models and Types
```
models/
├── __init__.py
├── data.py             # Core data models (Asset, DataPoint, etc.)
├── enums.py            # Enumerations for types, markets, timeframes
├── query.py            # Query parameter models
└── response.py         # API response models
```

**Model Organization:**
- **Business Models**: Asset, DataPoint, DataQuery, DataResponse
- **Enumeration Types**: AssetType, MarketType, TimeFrame, ProviderType, DataQuality
- **Validation**: Pydantic-based validation with custom JSON encoders
- **Type Safety**: Full mypy compatibility with strict type checking

### `cache/` - Caching Strategies
```
cache/
├── __init__.py
├── base.py             # Cache interface and base classes
├── redis_cache.py      # Redis-based distributed caching
├── memory_cache.py     # In-memory LRU cache
└── cache_keys.py       # Cache key generation utilities
```

**Caching Strategy:**
- **Multi-level Cache**: Memory (L1) + Redis (L2) + DuckDB (L3)
- **Smart Invalidation**: Time-based and event-based cache invalidation
- **Provider-aware**: Cache keys include provider and market context
- **Performance**: Sub-millisecond L1, <10ms L2, <100ms L3 cache access

### `web/` - Web API Layer
```
web/
├── __init__.py
├── main.py             # FastAPI application factory
├── routers/            # API endpoint routers
├── middleware/         # Request/response middleware
├── dependencies/       # FastAPI dependency injection
└── schemas/           # API request/response schemas
```

**API Structure:**
- **RESTful Design**: Resource-based endpoints with standard HTTP methods
- **Versioning**: URL-based versioning (/api/v1/)
- **Documentation**: Auto-generated OpenAPI/Swagger documentation
- **Error Handling**: Consistent error responses with proper HTTP codes

### `cli/` - Command Line Interface
```
cli/
├── __init__.py
├── main.py             # Typer-based CLI application
├── commands/           # Command groups and implementations
└── workers/            # Background task workers
```

**CLI Organization:**
- **Command Groups**: data, providers, cache, health, config
- **Rich Integration**: Terminal UI with colors and progress bars
- **Async Support**: Asyncio-based commands for I/O operations
- **Error Handling**: User-friendly error messages and exit codes

### `utils/` - Shared Utilities
```
utils/
├── __init__.py
├── logging.py          # Structured logging configuration
├── metrics.py          # Prometheus metrics collection
├── validation.py       # Common validation utilities
├── datetime.py         # Date/time handling utilities
└── http.py            # HTTP client utilities
```

## Test Structure

### `tests/` - Comprehensive Test Suite
```
tests/
├── __init__.py
├── conftest.py         # Pytest configuration and fixtures
├── unit/              # Unit tests for individual components
├── integration/       # Integration tests for provider APIs
└── e2e/              # End-to-end tests for full workflows
```

**Testing Strategy:**
- **Unit Tests**: Test individual functions and classes in isolation
- **Integration Tests**: Test provider integrations with mocked/external APIs
- **E2E Tests**: Test complete user workflows from CLI to API
- **Performance Tests**: Benchmark critical paths and cache performance

### Test Organization by Component
```
tests/unit/
├── test_models.py         # Data model validation tests
├── test_providers.py      # Provider interface tests
├── test_cache.py         # Caching layer tests
├── test_services.py      # Business logic tests
└── test_utils.py         # Utility function tests

tests/integration/
├── test_alpha_vantage.py  # Alpha Vantage integration
├── test_yahoo_finance.py  # Yahoo Finance integration
└── test_cache_redis.py   # Redis cache integration
```

## Code Organization Patterns

### 1. Domain-Driven Design
- **Core Domain**: Financial data processing and normalization
- **Bounded Contexts**: Providers, Cache, Web API, CLI
- **Ubiquitous Language**: Consistent terminology across codebase

### 2. Clean Architecture
- **Dependency Inversion**: Dependencies point inward toward business logic
- **Interface Segregation**: Small, focused interfaces for providers and cache
- **Single Responsibility**: Each module has one clear purpose

### 3. Functional Core, Imperative Shell
- **Pure Functions**: Data transformation and validation logic
- **Side Effects**: I/O operations isolated to specific layers
- **Testability**: Business logic easily testable without external dependencies

## File Naming Conventions

### Python Files
- **snake_case**: `data_service.py`, `market_provider.py`
- **Descriptive**: Names reflect responsibility and scope
- **Test Files**: Prefixed with `test_`, mirrors source structure
- **Configuration**: `.py` files for configuration, `.env` for secrets

### Directory Structure
- **Singular**: `provider/` not `providers/` (except top-level)
- **Purpose-based**: `cache/` not `redis/` (implementation details hidden)
- **Flat Hierarchy**: Maximum 3 levels deep within feature areas

### API Endpoints
- **kebab-case**: `/api/v1/market-data/{symbol}`
- **Resource-based**: `/assets/{symbol}/prices` not `/get-prices`
- **Versioned**: `/api/v1/` prefix for backward compatibility

## Import Organization

### Standard Library First
```python
# Standard library
import asyncio
from datetime import datetime
from typing import List, Optional

# Third-party imports
import httpx
from pydantic import BaseModel
from loguru import logger

# Local imports
from vprism.models.data import DataPoint
from vprism.providers.base import DataProvider
```

### Absolute Imports
- **Preferred**: `from vprism.models.data import Asset`
- **Avoid**: Relative imports like `from ..models import Asset`
- **Exception**: Test files may use relative imports for fixtures

### Type Checking
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vprism.core.service import DataService
```

## Key Architectural Principles

### 1. Provider Abstraction
- **Interface**: All providers implement `DataProvider` interface
- **Normalization**: Consistent data format regardless of source
- **Failover**: Automatic provider switching on failure
- **Rate Limiting**: Intelligent rate limiting per provider

### 2. Cache Strategy
- **Multi-level**: Memory → Redis → DuckDB
- **Invalidation**: Smart invalidation based on market hours and data freshness
- **Monitoring**: Cache hit/miss metrics and performance tracking
- **Provider-aware**: Cache keys include provider context

### 3. Error Handling
- **Consistent**: Standard error response format across all endpoints
- **Informative**: Detailed error messages for debugging
- **Recoverable**: Graceful degradation when providers fail
- **Logged**: All errors logged with context and stack traces

### 4. Configuration Management
- **Environment-based**: 12-factor app principles
- **Validation**: Runtime configuration validation on startup
- **Defaults**: Sensible defaults for quick development setup
- **Documentation**: All configuration options documented

### 5. Testing Strategy
- **Pytest**: Standard pytest with asyncio support
- **Fixtures**: Reusable test fixtures for common scenarios
- **Mocking**: External API mocking for reliable tests
- **Coverage**: Minimum 80% code coverage requirement
- **Performance**: Benchmark tests for critical paths