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
- **Web Framework**: FastAPI 0.111+ with async/await support (via uvicorn) - IMPLEMENTED with full REST API
- **API Documentation**: Automatic OpenAPI/Swagger generation
- **Data Validation**: Pydantic 2.5+ for request/response validation
- **Async Runtime**: Full async/await support with asyncio

### Data Processing - IMPLEMENTED
- **DataFrames**: Polars 0.19+ and Pandas 2.1+ for data processing
- **Database**: DuckDB 1.3.2 (latest) for analytical queries and local storage
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
  - pytest 8.4+ with pytest-asyncio for async testing
- **Testing**: 90%+ code coverage with comprehensive test suite
- **Dependencies**: All packages updated to latest stable versions:
  - duckdb: 1.3.2 (latest)
  - typer: 0.16.0 (latest)
  - fastapi: 0.111+ (latest compatible)
  - polars: 0.19+ (latest features)
  - pandas: 2.1+ (current stable)

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

## Technical Patterns & Compatibility Notes

### Pydantic v2 Migration Guide

#### Key Changes from v1 to v2
- **Config class**: Replaced with `model_config = ConfigDict(...)`
- **Validators**: `@validator` → `@field_validator` with different signature
- **Root validators**: `@root_validator` → `@model_validator`
- **Field constraints**: Use `Field(..., gt=0)` instead of `conint(gt=0)`

#### Migration Patterns
```python
# ✅ Pydantic v2 Style
from pydantic import BaseModel, Field, ConfigDict

class StockData(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        str_strip_whitespace=True
    )
    
    symbol: str = Field(..., min_length=1, max_length=10)
    price: float = Field(..., gt=0)
    volume: int = Field(..., ge=0)

# ✅ Field validation
@field_validator('symbol')
@classmethod
def validate_symbol(cls, v: str) -> str:
    return v.upper()

# ✅ Model validation
@model_validator(mode='after')
def validate_price_volume(self) -> 'StockData':
    if self.price <= 0 and self.volume > 0:
        raise ValueError('Price must be positive when volume > 0')
    return self
```

### FastAPI/FastMCP Integration Patterns

#### Request/Response Models
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

# ✅ Use Pydantic v2 models for request/response
class DataRequest(BaseModel):
    symbols: list[str] = Field(..., min_items=1, max_items=100)
    start_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    end_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')

class DataResponse(BaseModel):
    data: list[dict]
    metadata: dict = Field(default_factory=dict)
    
@app.post("/api/v1/data", response_model=DataResponse)
async def get_data(request: DataRequest):
    try:
        # Implementation
        return DataResponse(data=[], metadata={})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

#### Error Handling Integration
```python
from vprism.core.exceptions import ProviderError, ValidationError
from vprism.core.error_handler import ErrorHandler

@app.exception_handler(ProviderError)
async def provider_error_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content={"error": "Provider unavailable", "details": str(exc)}
    )
```

### API Compatibility Patterns

#### Version Compatibility
```python
# ✅ Versioned API endpoints
@app.get("/api/v1/data/{symbol}")
async def get_stock_data_v1(symbol: str):
    ...

@app.get("/api/v2/data/{symbol}")
async def get_stock_data_v2(symbol: str, format: str = "json"):
    ...

# ✅ Backward compatibility layer
class CompatibilityAdapter:
    """Adapts v1 responses to v2 format"""
    @staticmethod
    def adapt_v1_to_v2(v1_data: dict) -> dict:
        return {
            "symbol": v1_data.get("ticker"),
            "price": v1_data.get("current_price"),
            "timestamp": v1_data.get("last_updated")
        }
```

#### Data Format Compatibility
```python
# ✅ Flexible date parsing
from datetime import datetime
from typing import Union

def parse_date(date_input: Union[str, datetime]) -> datetime:
    """Handle multiple date formats for backward compatibility"""
    if isinstance(date_input, datetime):
        return date_input
    
    # Try multiple formats
    formats = ["%Y-%m-%d", "%Y%m%d", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_input, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Invalid date format: {date_input}")
```

### Testing Best Practices

#### Test Structure
```python
# ✅ Test file naming: test_*.py
# ✅ Test class naming: Test* with descriptive names
class TestStockDataProvider:
    """Test suite for stock data provider"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.provider = StockDataProvider()
    
    def test_get_stock_data_success(self):
        """Test successful stock data retrieval"""
        result = self.provider.get_data("AAPL")
        assert result.symbol == "AAPL"
        assert result.price > 0
    
    def test_get_stock_data_invalid_symbol(self):
        """Test error handling for invalid symbol"""
        with pytest.raises(ValidationError):
            self.provider.get_data("INVALID_SYMBOL_12345")
```

#### Async Testing Patterns
```python
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_async_data_fetch():
    """Test async data fetching with proper mocking"""
    with patch('httpx.AsyncClient.get') as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"data": "test"}
        )
        
        result = await async_fetch_data("AAPL")
        assert result is not None
```

#### Mocking External Dependencies
```python
from unittest.mock import patch, MagicMock
import pytest

class TestExternalAPI:
    @patch('httpx.AsyncClient.get')
    async def test_rate_limiting(self, mock_get):
        """Test rate limiting behavior"""
        mock_get.return_value.status_code = 429
        mock_get.return_value.headers = {"Retry-After": "60"}
        
        with pytest.raises(RateLimitError):
            await self.client.fetch_data("AAPL")
```

### Environment Configuration

#### Development vs Production
```python
# ✅ Environment-specific configuration
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    environment: str = Field(default="development")
    
    # Database
    duckdb_path: str = Field(default="vprism_dev.duckdb")
    
    # Cache
    cache_ttl: int = Field(default=3600)
    
    # Rate limiting
    rate_limit_per_minute: int = Field(default=60)
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Load settings based on environment
settings = Settings()
if settings.environment == "production":
    settings.duckdb_path = "vprism_prod.duckdb"
    settings.cache_ttl = 7200
    settings.rate_limit_per_minute = 120
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

### Library Mode - COMPLETED
- **Use Case**: Direct Python library integration
- **Entry Point**: `import vprism`
- **Dependencies**: Python 3.11+, DuckDB, httpx
- **APIs Available**:
  - Simple API: `vprism.get(asset, market, symbols, ...)`
  - Async API: `vprism.get_async(asset, market, symbols, ...)`
  - Query Builder: `vprism.query().asset().market().build()`
  - Global Config: `vprism.configure(cache={}, providers={})`
- **Installation**: `pip install -e .` or `uv pip install -e .`
- **Usage**: Direct import and use in Python applications
- **Testing**: 287+ test cases with 95%+ coverage
- **Documentation**: Complete usage examples and API reference

### Service Mode - COMPLETED ✅
- **Use Case**: REST API server
- **Framework**: FastAPI 0.111+ with full REST API
- **Entry Point**: `python main.py web` or `uvicorn src.vprism.web.app:app`
- **Dependencies**: FastAPI, uvicorn, httpx, DuckDB
- **Features**: 
  - Complete RESTful API with OpenAPI 3.0 documentation
  - Swagger UI and ReDoc interfaces
  - Health checks and Kubernetes probes
  - CORS, Gzip compression, request validation
  - Standardized response format with error handling
- **Routes**: 
  - `/api/v1/data/stock/*` - Stock data endpoints
  - `/api/v1/data/market/*` - Market data endpoints
  - `/api/v1/data/batch/*` - Batch processing
  - `/api/v1/health/*` - Health monitoring endpoints

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

### Data Quality System - IMPLEMENTED
- **Data Quality Framework**: Comprehensive validation and cleaning pipeline
- **Components**: DataQualityValidator, DataQualityScorer, DataCleaner
- **Features**: 
  - Data validation (missing values, outliers, format consistency)
  - Quality scoring (completeness, accuracy, timeliness, consistency)
  - Data cleaning (interpolation, outlier removal, normalization)
- **Coverage**: 45+ unit tests with 95%+ coverage
- **Integration**: Seamless integration with existing data pipeline

### Data Consistency Validation - IMPLEMENTED
- **Consistency Validator**: Cross-provider data comparison and validation
- **Providers**: vprism vs AkShare data consistency checking
- **Features**:
  - Automated data comparison with configurable tolerance
  - Detailed consistency reports with statistical analysis
  - Batch validation for multiple symbols
  - Alert system for data quality issues
- **Testing**: 11 comprehensive test cases with mocking
- **Reporting**: Structured consistency reports and trend analysis