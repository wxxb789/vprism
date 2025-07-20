# vprism Technology Stack

## Architecture

**High-Level Design**: Microservices-ready, modular architecture with clear separation of concerns
- **Core Layer**: Business logic and data processing
- **Provider Layer**: External API integrations with pluggable providers
- **Web Layer**: FastAPI-based REST API and WebSocket endpoints
- **Cache Layer**: Redis for hot data, DuckDB for analytical queries
- **CLI Layer**: Rich CLI interface for development and administration

## Core Technology Stack

### Backend Framework
- **Language**: Python 3.11+ with full type hints and mypy strict mode
- **Web Framework**: FastAPI 0.116+ with async/await support
- **API Documentation**: Automatic OpenAPI/Swagger generation
- **Data Validation**: Pydantic 2.x for request/response validation

### Data Processing
- **DataFrames**: Polars 1.31+ for high-performance data processing
- **Database**: DuckDB 1.3+ for analytical queries and local storage
- **ORM**: SQLModel/Pydantic for data models
- **Caching**: Redis 7+ for distributed caching and session management

### External Integrations
- **HTTP Client**: httpx for async HTTP requests with connection pooling
- **Authentication**: python-jose for JWT tokens, cryptography for encryption
- **Configuration**: pydantic-settings for environment-based configuration
- **Task Queue**: Redis-based async task processing

### Observability & Monitoring
- **Metrics**: prometheus-client for application metrics
- **Tracing**: OpenTelemetry API for distributed tracing
- **Logging**: loguru for structured logging with rotation
- **Health Checks**: Built-in health endpoints for container orchestration

### Development Tools
- **Package Manager**: uv for fast dependency resolution
- **Code Quality**: 
  - black for code formatting (88 char line length)
  - ruff for linting (E, W, F, I, B, C4, UP, SIM, TCH)
  - mypy for type checking (strict mode)
  - pytest for testing with asyncio support
- **Pre-commit**: Automated code quality checks

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

## Port Configuration

### Application Ports
- **8000**: Main FastAPI application (HTTP/REST API)
- **8001**: WebSocket API for real-time data

### Infrastructure Ports
- **6379**: Redis cache and session storage
- **5432**: DuckDB (when running as service)
- **9090**: Prometheus metrics endpoint
- **3000**: Grafana dashboards

### Development Ports
- **8000**: Main application (development)
- **5678**: Python debugger (debugpy)
- **9229**: Node.js debugger (for frontend)

## Common Development Commands

### Development Workflow
```bash
# Install dependencies
uv sync

# Run linting
uv run ruff check .
uv run black --check .
uv run mypy src/

# Run tests
uv run pytest tests/
uv run pytest tests/unit/
uv run pytest tests/integration/

# Code formatting
uv run black .
uv run ruff format .

# Type checking
uv run mypy src/

# Security scanning
uv run pip-audit
```

### Docker Commands
```bash
# Development environment
docker-compose up

# Production build
docker build --target production -t vprism:latest .

# Run specific service
docker-compose up vprism-api

# Scale services
docker-compose up --scale vprism-worker=3

# Logs
docker-compose logs -f vprism-api
```

### CLI Commands
```bash
# Start development server
vprism serve --reload

# Data operations
vprism data fetch --symbol AAPL --provider yahoo
vprism data validate --file data.csv

# Provider management
vprism providers list
vprism providers test --provider alpha_vantage

# Cache operations
vprism cache clear
vprism cache stats

# Health checks
vprism health
vprism health --detailed
```

## Deployment Modes

### Library Mode
- **Use Case**: Integration into existing Python applications
- **Entry Point**: `import vprism`
- **Dependencies**: Minimal external services

### Service Mode
- **Use Case**: Microservices architecture
- **Entry Point**: `uvicorn vprism.web.main:app`
- **Dependencies**: Redis, DuckDB

### MCP Mode
- **Use Case**: AI agent integration
- **Entry Point**: `vprism mcp serve`
- **Dependencies**: FastMCP server

### Container Mode
- **Use Case**: Cloud deployment
- **Entry Point**: Docker containers
- **Dependencies**: Full stack with Redis, DuckDB, Prometheus, Grafana