# vprism Technology Stack - Implementation Complete

## Architecture

**High-Level Design**: Clean Architecture with Domain-Driven Design principles
- **Domain Layer**: Core business entities, value objects, and domain services
- **Application Layer**: Use cases, query handlers, and application services
- **Infrastructure Layer**: External systems, data providers, repositories, and caches
- **Presentation Layer**: REST API, CLI, and MCP server interfaces
- **Provider Layer**: Pluggable data provider adapters with capability discovery

## Core Technology Stack

### Backend Framework - IMPLEMENTED
- **Language**: Python 3.11+ with full type hints and mypy strict mode
- **Web Framework**: FastAPI 0.104+ with async/await support (via uvicorn)
- **API Documentation**: Automatic OpenAPI/Swagger generation
- **Data Validation**: Pydantic 2.5+ for request/response validation
- **Async Runtime**: Full async/await support with asyncio

### Data Processing - IMPLEMENTED
- **DataFrames**: Polars 0.19+ and Pandas 2.1+ for data processing
- **Database**: DuckDB 0.9+ for analytical queries and local storage
- **Data Models**: Pydantic-based domain models with strict typing
- **Query Builder**: Fluent interface for complex financial data queries

### Caching Architecture - IMPLEMENTED
- **Multi-level Cache**: L1 memory + L2 DuckDB persistent cache
- **Cache Strategy**: Query-based caching with TTL and fingerprinting
- **Invalidation**: Automatic cache invalidation and cleanup
- **Key Generation**: Deterministic cache keys based on query signatures

### External Integrations - IMPLEMENTED
- **HTTP Client**: httpx 0.25+ for async HTTP with connection pooling
- **Data Providers**: AkShare, yFinance, Alpha Vantage, vprism Provider
- **Authentication**: JWT tokens with cryptography for security
- **Configuration**: pydantic-settings for environment-based config

### Observability - IMPLEMENTED
- **Logging**: Loguru 0.7+ for structured logging with rotation
- **Metrics**: prometheus-client 0.19+ for application metrics
- **Tracing**: OpenTelemetry API 1.21+ for distributed tracing
- **Health Checks**: Built-in health monitoring endpoints

### Development Tools - IMPLEMENTED
- **Package Manager**: uv dependency management via pyproject.toml
- **Code Quality**: 
  - ruff 0.1+ for linting (E, F, I, N, W, UP, B, C4, SIM, TCH)
  - mypy 1.7+ for type checking (strict mode)
  - pytest 7.4+ with pytest-asyncio for async testing
- **Testing**: 90%+ code coverage with comprehensive test suite

## Development Environment

### Required Tools
- **Python**: 3.11, 3.12, or 3.13
- **Package Manager**: uv (recommended) or pip
- **Container Runtime**: Docker & Docker Compose
- **Git**: For version control

### Setup Commands
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Run tests
uv run pytest

# Start development environment
uv run uvicorn vprism.web.main:app --reload

# Docker development
docker-compose up --build
```

## Environment Variables

### Core Configuration
```bash
# Environment
VPRISM_ENV=development|staging|production
LOG_LEVEL=DEBUG|INFO|WARNING|ERROR

# Server Configuration
HOST=0.0.0.0
PORT=8000
WORKERS=4

# Database
DUCKDB_DATABASE=/data/vprism.duckdb
DUCKDB_MEMORY_LIMIT=1GB

# Redis Cache
REDIS_URL=redis://localhost:6379
REDIS_DB=0
CACHE_TTL=3600

# Security
SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION=3600

# API Keys (Provider-specific)
ALPHA_VANTAGE_API_KEY=
YAHOO_FINANCE_API_KEY=
QUANDL_API_KEY=
```

### Provider Configuration
```bash
# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10

# Provider Timeouts
PROVIDER_TIMEOUT=30
PROVIDER_RETRY_ATTEMPTS=3
PROVIDER_BACKOFF_FACTOR=0.3

# Data Quality
MIN_DATA_QUALITY=medium
CACHE_INVALIDATION_TTL=300
```

## Configuration - IMPLEMENTED

### Environment Variables
- **DUCKDB_PATH**: Database file path (default: vprism_data.duckdb)
- **CACHE_TTL**: Default cache TTL in seconds (default: 3600)
- **LOG_LEVEL**: Logging level (DEBUG, INFO, WARNING, ERROR)
- **PROVIDER_TIMEOUT**: Provider request timeout (default: 30s)

### Development Commands - IMPLEMENTED
```bash
# Install package
pip install -e .

# Run tests
pytest tests/ -v

# Type checking
mypy src/vprism --strict

# Code formatting
ruff format src/
ruff check src/

# Run service
uvicorn vprism.service:app --reload --host 0.0.0.0 --port 8000
```

## Deployment Modes - IMPLEMENTED

### Library Mode
- **Use Case**: Direct Python library integration
- **Entry Point**: `import vprism`
- **Dependencies**: Python 3.11+, DuckDB, httpx

### Service Mode
- **Use Case**: REST API server
- **Entry Point**: `uvicorn vprism.service:app`
- **Dependencies**: FastAPI, uvicorn, DuckDB

### MCP Mode
- **Use Case**: AI agent integration
- **Entry Point**: `vprism.mcp:server`
- **Dependencies**: FastMCP server integration

## Production Configuration - IMPLEMENTED

### Database Configuration
- **DuckDB**: Single-file analytical database
- **Schema**: 6 optimized tables with proper indexing
- **Performance**: Partitioned views and materialized views

### Cache Configuration
- **L1 Cache**: In-memory thread-safe cache (1000 items max)
- **L2 Cache**: DuckDB-based persistent cache with TTL
- **Invalidation**: Automatic expiration and cleanup

### Provider Configuration
- **AkShare**: Chinese market data (60 req/min limit)
- **yFinance**: Yahoo Finance data (1000 req/hour limit)
- **Alpha Vantage**: Professional data (5 req/min limit)
- **vprism Provider**: Internal data aggregation