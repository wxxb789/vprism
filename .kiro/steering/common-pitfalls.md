# Common Pitfalls and How to Avoid Them

## Overview
This document captures lessons learned from extensive development sessions to help future contributors avoid common mistakes and follow best practices established during development.

## Pydantic v2 Migration Pitfalls

### 1. Field Validation Changes
**Pitfall**: Using deprecated `@validator` decorator
**Solution**: Use `@field_validator` with correct signature

```python
# ❌ WRONG - Pydantic v1 style
from pydantic import validator

class StockData(BaseModel):
    symbol: str
    
    @validator('symbol')
    def validate_symbol(cls, v):
        return v.upper()

# ✅ CORRECT - Pydantic v2 style
from pydantic import field_validator

class StockData(BaseModel):
    symbol: str
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        return v.upper()
```

### 2. Config Class Migration
**Pitfall**: Using `Config` inner class
**Solution**: Use `model_config = ConfigDict(...)`

```python
# ❌ WRONG - Pydantic v1 style
class StockData(BaseModel):
    symbol: str
    
    class Config:
        populate_by_name = True
        validate_assignment = True

# ✅ CORRECT - Pydantic v2 style
from pydantic import ConfigDict

class StockData(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        str_strip_whitespace=True
    )
    symbol: str
```

### 3. Field Constraints
**Pitfall**: Using deprecated constraint types
**Solution**: Use `Field(...)` with parameters

```python
# ❌ WRONG - Pydantic v1 style
from pydantic import conint, confloat

class StockData(BaseModel):
    price: confloat(gt=0)
    volume: conint(ge=0)

# ✅ CORRECT - Pydantic v2 style
from pydantic import Field

class StockData(BaseModel):
    price: float = Field(..., gt=0)
    volume: int = Field(..., ge=0)
```

## FastAPI Integration Pitfalls

### 1. Async/Await Patterns
**Pitfall**: Mixing sync and async code incorrectly
**Solution**: Always use async/await consistently

```python
# ❌ WRONG - Mixing sync and async
@app.get("/data/{symbol}")
async def get_data(symbol: str):
    # This is sync - will block event loop
    data = yfinance.Ticker(symbol).history()
    return data

# ✅ CORRECT - Proper async handling
@app.get("/data/{symbol}")
async def get_data(symbol: str):
    # Use async-compatible libraries or run in thread pool
    data = await run_in_threadpool(
        lambda: yfinance.Ticker(symbol).history()
    )
    return data
```

### 2. Error Handling
**Pitfall**: Not handling provider-specific errors
**Solution**: Use proper exception handlers

```python
# ❌ WRONG - Generic error handling
@app.get("/data/{symbol}")
async def get_data(symbol: str):
    try:
        return await provider.get_data(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ CORRECT - Specific error handling
@app.get("/data/{symbol}")
async def get_data(symbol: str):
    try:
        return await provider.get_data(symbol)
    except ProviderError as e:
        raise HTTPException(status_code=503, detail="Provider unavailable")
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### 3. Request Validation
**Pitfall**: Not validating input parameters
**Solution**: Use Pydantic models for validation

```python
# ❌ WRONG - Manual validation
@app.get("/data/{symbol}")
async def get_data(symbol: str, start_date: str = None):
    if start_date and not is_valid_date(start_date):
        raise HTTPException(status_code=400, detail="Invalid date format")
    # ... more validation

# ✅ CORRECT - Pydantic validation
class DataRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    start_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')

@app.get("/data/{symbol}")
async def get_data(symbol: str, start_date: Optional[str] = None):
    request = DataRequest(symbol=symbol, start_date=start_date)
    # Request is already validated
```

## Database Pitfalls

### 1. DuckDB Connection Management
**Pitfall**: Not properly managing database connections
**Solution**: Use connection pooling and context managers

```python
# ❌ WRONG - Connection leaks
conn = duckdb.connect("vprism_data.duckdb")
result = conn.execute("SELECT * FROM stocks").fetchall()
# Connection never closed

# ✅ CORRECT - Context manager
with duckdb.connect("vprism_data.duckdb") as conn:
    result = conn.execute("SELECT * FROM stocks").fetchall()
    # Connection automatically closed
```

### 2. Data Type Consistency
**Pitfall**: Inconsistent data types between providers
**Solution**: Standardize types during data processing

```python
# ❌ WRONG - Mixed types
# Provider A returns float prices
# Provider B returns string prices
# Provider C returns Decimal prices

# ✅ CORRECT - Standardized types
def standardize_price_data(raw_data: dict) -> dict:
    """Standardize price data types"""
    return {
        'symbol': str(raw_data['symbol']).upper(),
        'price': float(raw_data['price']),
        'volume': int(raw_data['volume']),
        'timestamp': pd.to_datetime(raw_data['timestamp'])
    }
```

### 3. DateTime Handling
**Pitfall**: Timezone issues and inconsistent date formats
**Solution**: Always use UTC and standardize formats

```python
# ❌ WRONG - Mixed timezones and formats
def process_date(date_str: str):
    return datetime.strptime(date_str, "%Y-%m-%d")  # No timezone info

# ✅ CORRECT - UTC standardization
def process_date(date_str: str) -> datetime:
    """Parse and standardize date to UTC"""
    dt = pd.to_datetime(date_str)
    if dt.tz is None:
        dt = dt.tz_localize('UTC')
    else:
        dt = dt.tz_convert('UTC')
    return dt
```

## Testing Pitfalls

### 1. Async Test Setup
**Pitfall**: Not properly setting up async tests
**Solution**: Use pytest-asyncio and proper fixtures

```python
# ❌ WRONG - Missing async setup
import pytest

async def test_async_function():
    result = await async_get_data()
    assert result is not None

# ✅ CORRECT - Proper async test setup
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await async_get_data()
    assert result is not None
```

### 2. Mock Setup for External APIs
**Pitfall**: Incorrect mock setup causing flaky tests
**Solution**: Use proper mocking patterns

```python
# ❌ WRONG - Mocking at wrong level
@patch('yfinance.Ticker')
def test_get_data(mock_ticker):
    mock_ticker.return_value.history.return_value = mock_data
    # This might fail if the code uses a different import path

# ✅ CORRECT - Mock at the correct level
@patch('vprism.providers.yahoo.yfinance.Ticker')
def test_get_data(mock_ticker):
    mock_ticker.return_value.history.return_value = mock_data
    # Mock the exact import path used in the code
```

### 3. Test Data Management
**Pitfall**: Hard-coded test data causing brittle tests
**Solution**: Use fixtures and factories

```python
# ❌ WRONG - Hard-coded data
def test_stock_data():
    data = {"AAPL": {"price": 150.0, "volume": 1000000}}
    assert process_data(data) == expected_result

# ✅ CORRECT - Fixture-based data
@pytest.fixture
def sample_stock_data():
    return generate_sample_data(symbol="AAPL", price=150.0, volume=1000000)

def test_stock_data(sample_stock_data):
    result = process_data(sample_stock_data)
    assert result.symbol == "AAPL"
```

## Cache Management Pitfalls

### 1. Cache Key Generation
**Pitfall**: Non-deterministic cache keys
**Solution**: Use consistent key generation

```python
# ❌ WRONG - Unstable cache keys
def get_cache_key(symbol: str, start_date: str, end_date: str):
    return f"{symbol}_{start_date}_{end_date}_{time.time()}"  # Time makes it unstable

# ✅ CORRECT - Deterministic cache keys
def get_cache_key(symbol: str, start_date: str, end_date: str):
    """Generate deterministic cache key"""
    key_data = f"{symbol}_{start_date}_{end_date}"
    return hashlib.md5(key_data.encode()).hexdigest()
```

### 2. Cache Invalidation
**Pitfall**: Not invalidating cache on data updates
**Solution**: Implement proper invalidation strategies

```python
# ❌ WRONG - Cache never invalidated
class DataProvider:
    def get_data(self, symbol: str):
        if self.cache.get(symbol):
            return self.cache.get(symbol)
        data = self.fetch_data(symbol)
        self.cache.set(symbol, data)
        return data

# ✅ CORRECT - Proper invalidation
class DataProvider:
    def get_data(self, symbol: str, force_refresh: bool = False):
        if not force_refresh and self.cache.get(symbol):
            return self.cache.get(symbol)
        
        data = self.fetch_data(symbol)
        self.cache.set(symbol, data, ttl=3600)
        return data
    
    def refresh_data(self, symbol: str):
        """Force refresh cached data"""
        self.cache.delete(symbol)
        return self.get_data(symbol, force_refresh=True)
```

## Performance Pitfalls

### 1. N+1 Query Problem
**Pitfall**: Making individual API calls for each symbol
**Solution**: Batch requests when possible

```python
# ❌ WRONG - Individual requests
async def get_multiple_stocks(symbols: list[str]):
    results = []
    for symbol in symbols:
        data = await provider.get_stock(symbol)  # N API calls
        results.append(data)
    return results

# ✅ CORRECT - Batch requests
async def get_multiple_stocks(symbols: list[str]):
    return await provider.get_stocks_batch(symbols)  # 1 API call
```

### 2. Memory Management
**Pitfall**: Loading large datasets into memory
**Solution**: Use streaming and pagination

```python
# ❌ WRONG - Loading all data
def process_large_dataset(start_date, end_date):
    data = provider.get_all_data(start_date, end_date)  # Could be huge
    return process_data(data)

# ✅ CORRECT - Streaming processing
def process_large_dataset(start_date, end_date):
    for chunk in provider.get_data_chunks(start_date, end_date):
        yield process_data(chunk)
```

## Provider Integration Pitfalls

### 1. Rate Limiting
**Pitfall**: Not respecting provider rate limits
**Solution**: Implement rate limiting and backoff

```python
# ❌ WRONG - No rate limiting
async def fetch_data(symbol: str):
    return await httpx.get(f"https://api.provider.com/data/{symbol}")

# ✅ CORRECT - With rate limiting
import asyncio
from vprism.core.rate_limiter import RateLimiter

rate_limiter = RateLimiter(requests_per_minute=60)

async def fetch_data(symbol: str):
    await rate_limiter.acquire()
    return await httpx.get(f"https://api.provider.com/data/{symbol}")
```

### 2. Error Handling
**Pitfall**: Not handling provider-specific errors
**Solution**: Implement comprehensive error handling

```python
# ❌ WRONG - Generic error handling
async def fetch_data(symbol: str):
    try:
        response = await httpx.get(f"https://api.provider.com/data/{symbol}")
        return response.json()
    except Exception as e:
        raise Exception(f"Failed to fetch data: {e}")

# ✅ CORRECT - Specific error handling
async def fetch_data(symbol: str):
    try:
        response = await httpx.get(f"https://api.provider.com/data/{symbol}")
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise RateLimitError(retry_after=retry_after)
        
        if response.status_code == 404:
            raise SymbolNotFoundError(symbol)
        
        response.raise_for_status()
        return response.json()
        
    except httpx.TimeoutException:
        raise ProviderTimeoutError("Request timed out")
    except httpx.ConnectError:
        raise ProviderConnectionError("Failed to connect to provider")
```

### 3. Data Format Variations
**Pitfall**: Assuming consistent data formats across providers
**Solution**: Implement data normalization

```python
# ❌ WRONG - Assuming consistent format
def process_provider_data(data: dict):
    return {
        'price': data['price'],
        'volume': data['volume']
    }

# ✅ CORRECT - Data normalization
def normalize_provider_data(provider: str, raw_data: dict) -> dict:
    """Normalize data from different providers"""
    normalizers = {
        'yahoo': lambda d: {
            'price': d['regularMarketPrice'],
            'volume': d['regularMarketVolume']
        },
        'alphavantage': lambda d: {
            'price': float(d['05. price']),
            'volume': int(d['06. volume'])
        }
    }
    
    if provider not in normalizers:
        raise ValueError(f"Unknown provider: {provider}")
    
    return normalizers[provider](raw_data)
```

## Configuration Pitfalls

### 1. Environment Variable Types
**Pitfall**: Not handling type conversion for env vars
**Solution**: Use Pydantic settings with proper types

```python
# ❌ WRONG - Manual type conversion
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
RATE_LIMIT = float(os.getenv("RATE_LIMIT", "60.0"))

# ✅ CORRECT - Pydantic settings
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    cache_ttl: int = Field(default=3600, env="CACHE_TTL")
    rate_limit: float = Field(default=60.0, env="RATE_LIMIT")
```

### 2. Configuration Validation
**Pitfall**: Not validating configuration at startup
**Solution**: Validate settings on initialization

```python
# ❌ WRONG - No validation
class Settings(BaseSettings):
    cache_ttl: int = 3600

# ✅ CORRECT - With validation
class Settings(BaseSettings):
    cache_ttl: int = Field(default=3600, gt=0, le=86400)
    
    @validator('cache_ttl')
    def validate_cache_ttl(cls, v):
        if v <= 0:
            raise ValueError("CACHE_TTL must be positive")
        return v
```

## Security Pitfalls

### 1. API Key Management
**Pitfall**: Hard-coding API keys in code
**Solution**: Use environment variables and secrets management

```python
# ❌ WRONG - Hard-coded keys
API_KEY = "sk-1234567890abcdef"

# ✅ CORRECT - Environment variables
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    alpha_vantage_api_key: str = Field(..., env="ALPHA_VANTAGE_API_KEY")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

### 2. Input Validation
**Pitfall**: Not validating user inputs
**Solution**: Implement comprehensive input validation

```python
# ❌ WRONG - Trusting user input
def get_stock_data(symbol: str):
    return fetch_data(symbol)  # No validation

# ✅ CORRECT - Input validation
def get_stock_data(symbol: str):
    if not symbol or len(symbol) > 10:
        raise ValidationError("Invalid symbol")
    
    if not symbol.isalpha():
        raise ValidationError("Symbol must contain only letters")
    
    return fetch_data(symbol.upper())
```

## Deployment Pitfalls

### 1. Dependency Management
**Pitfall**: Not pinning dependencies
**Solution**: Use lock files and specific versions

```bash
# ❌ WRONG - Vague requirements
# requirements.txt
fastapi
pydantic
httpx

# ✅ CORRECT - Specific versions
# pyproject.toml
[project]
dependencies = [
    "fastapi==0.111.0",
    "pydantic==2.5.0",
    "httpx==0.25.0"
]
```

### 2. Environment Configuration
**Pitfall**: Missing environment variables in production
**Solution**: Use environment validation and defaults

```python
# ❌ WRONG - No defaults or validation
class Settings(BaseSettings):
    database_url: str
    redis_url: str

# ✅ CORRECT - With defaults and validation
class Settings(BaseSettings):
    database_url: str = Field(default="vprism_data.duckdb")
    redis_url: str = Field(default="redis://localhost:6379")
    
    @validator('database_url', 'redis_url')
    def validate_urls(cls, v):
        if not v:
            raise ValueError(f"{v} cannot be empty")
        return v
```

## Best Practices Summary

### 1. Always Use
- Type hints for all functions and variables
- Pydantic v2 patterns (model_config, field_validator)
- Async/await consistently
- Proper error handling with specific exceptions
- Environment variable validation
- Comprehensive testing with fixtures
- Database connection pooling
- Cache key normalization
- Rate limiting for external APIs

### 2. Never Do
- Hard-code configuration values
- Mix sync and async code
- Skip input validation
- Ignore error handling
- Use deprecated Pydantic features
- Assume data format consistency across providers
- Load large datasets into memory without streaming
- Skip type checking
- Use magic numbers without constants

### 3. Always Test
- Unit tests for all functions
- Integration tests for API endpoints
- Error handling scenarios
- Rate limiting behavior
- Cache functionality
- Data validation
- Provider-specific edge cases
- Performance under load

### 4. Monitor
- API response times
- Error rates and types
- Cache hit/miss ratios
- Memory usage
- Database query performance
- Provider rate limit usage
- System health metrics