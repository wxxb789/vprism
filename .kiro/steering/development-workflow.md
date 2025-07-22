# Development Workflow Standards

## Post-Task Completion Protocol

This document defines the mandatory steps to be executed after completing any development task in this repository.

### Mandatory Post-Task Steps

Every time a task is completed, **ALWAYS** execute these steps in order:

#### 1. Update Task Status in tasks.md
- [ ] Mark the completed task with `[x]` in the corresponding `tasks.md` file
- [ ] Use markdown checkbox format: `- [x] Task description`
- [ ] Ensure the checkbox is properly formatted with space after `[x]`

#### 2. Update Steering Documentation
- [ ] Run `/steering-update` command if project structure changed
- [ ] Review and update relevant `.kiro/steering/*.md` files
- [ ] Ensure documentation reflects current state of the codebase

#### 3. Code Formatting
- [ ] Execute `ruff format` from project root to format all Python files
- [ ] Execute `ruff check --fix` to auto-fix linting issues
- [ ] Verify no formatting issues remain

#### 4. Git Commit (Atomic Commits)
- [ ] Stage all changes: `git add -A`
- [ ] Create atomic commit with clear message
- [ ] Commit message format: `type(scope): description`
- [ ] Examples:
  - `feat(cache): implement multi-level caching`
  - `fix(provider): handle rate limiting in yfinance`
  - `docs(steering): update project structure documentation`

### Commit Message Standards

Follow conventional commits specification:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

### Quality Checklist

Before committing, ensure:
- [ ] All tests pass: `pytest`
- [ ] Type checking passes: `mypy src/vprism --strict`
- [ ] Code formatting is applied: `ruff format`
- [ ] Linting passes: `ruff check`
- [ ] Task status updated in tasks.md
- [ ] Steering docs updated if needed

### Automation

These steps are enforced through:
- Pre-commit hooks (when configured)
- Manual verification during development
- CI/CD pipeline validation

### Examples

#### Example 1: Completing a Feature
```bash
# 1. Update tasks.md (mark checkbox as [x])
# 2. Update steering if structure changed
/steering-update

# 3. Format and lint code
ruff format
ruff check --fix

# 4. Commit changes
git add -A
git commit -m "feat(cache): implement multi-level caching with memory and duckdb"
```

#### Example 2: Documentation Update
```bash
# 1. Update tasks.md
# 2. Format docs
ruff format

# 3. Commit
git add -A
git commit -m "docs(steering): update project structure documentation"
```

### 已完成任务：错误处理和容错机制

#### 任务6完成总结
- **状态**：✅ 已完成
- **测试用例**：55个，100%通过率
- **覆盖率**：核心模块100%，整体90%+

#### 新增核心组件
- `vprism.core.exceptions`: 完整异常层次结构
- `vprism.core.error_codes`: 标准化错误代码系统
- `vprism.core.error_handler`: 错误处理和日志系统
- `vprism.core.circuit_breaker`: 熔断器实现
- `vprism.core.retry`: 指数退避重试机制

#### 使用模式
```python
# 异常处理
from vprism.core.exceptions import ProviderError
from vprism.core.error_handler import ErrorHandler

# 熔断器
from vprism.core.circuit_breaker import circuit_breaker

# 重试机制
from vprism.core.retry import retry, ResilientExecutor
```

## Testing & Debugging Guidelines

### Testing Strategy

#### Test Pyramid
- **Unit Tests**: 80% - Test individual functions and classes
- **Integration Tests**: 15% - Test component interactions
- **End-to-End Tests**: 5% - Test complete user workflows

#### Test Organization
```
tests/
├── unit/                    # Unit tests
│   ├── test_models.py
│   ├── test_providers.py
│   └── test_services.py
├── integration/            # Integration tests
│   ├── test_api.py
│   ├── test_database.py
│   └── test_cache.py
├── fixtures/               # Test data and mocks
│   ├── sample_data.py
│   └── mock_responses.py
└── conftest.py            # Pytest configuration
```

#### Common Testing Patterns

#### UV Toolchain Commands - MANDATORY
```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Type checking
uv run mypy src/vprism --strict

# Code formatting
uv run ruff format src/
uv run ruff check src/

# Run service
uv run uvicorn vprism.service:app --reload --host 0.0.0.0 --port 8000

# Development with hot reload
uv run python -m vprism.web.main
```

#### 1. Database Testing
```python
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup
    Path(db_path).unlink(missing_ok=True)

@pytest.fixture
def test_client(temp_db):
    """Test client with temporary database"""
    from vprism.web.main import app
    from fastapi.testclient import TestClient
    
    # Override database path
    app.dependency_overrides[get_db] = lambda: temp_db
    
    with TestClient(app) as client:
        yield client
```

##### 2. Mocking External APIs
```python
from unittest.mock import patch, AsyncMock
import pytest

@pytest.fixture
def mock_yahoo_finance():
    """Mock Yahoo Finance API responses"""
    with patch('yfinance.Ticker') as mock_ticker:
        mock_instance = AsyncMock()
        mock_instance.history.return_value = mock_stock_data()
        mock_ticker.return_value = mock_instance
        yield mock_instance

def mock_stock_data():
    """Sample stock data for testing"""
    import pandas as pd
    return pd.DataFrame({
        'Open': [100.0, 101.0, 102.0],
        'Close': [101.0, 102.0, 103.0],
        'Volume': [1000000, 1100000, 1200000]
    })
```

##### 3. Cache Testing
```python
import time
from vprism.core.cache import CacheManager

class TestCacheManager:
    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration"""
        cache = CacheManager(ttl=1)  # 1 second TTL
        cache.set("test_key", "test_value")
        
        # Should exist immediately
        assert cache.get("test_key") == "test_value"
        
        # Wait for expiration
        time.sleep(1.1)
        assert cache.get("test_key") is None
```

### Debugging Guidelines

#### 1. Debug Configuration
```python
# debug_config.py
import logging
from vprism.core.logging import setup_logging

def setup_debug_logging():
    """Setup debug logging for development"""
    setup_logging(
        level="DEBUG",
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("debug.log")
        ]
    )

# Usage in tests
@pytest.fixture(autouse=True)
def debug_logging():
    setup_debug_logging()
```

#### 2. Common Debug Scenarios

##### Database Query Debugging
```python
import duckdb

def debug_database_query(query: str, params: dict = None):
    """Debug database queries with logging"""
    conn = duckdb.connect("vprism_data.duckdb")
    
    try:
        # Log query
        print(f"Executing query: {query}")
        if params:
            print(f"With params: {params}")
        
        # Execute and log results
        result = conn.execute(query, params).fetchall()
        print(f"Query returned {len(result)} rows")
        
        return result
    except Exception as e:
        print(f"Query failed: {e}")
        raise
    finally:
        conn.close()
```

##### API Response Debugging
```python
import httpx
import json

async def debug_api_call(url: str, **kwargs):
    """Debug HTTP API calls"""
    async with httpx.AsyncClient() as client:
        print(f"Making request to: {url}")
        print(f"Parameters: {json.dumps(kwargs, indent=2)}")
        
        response = await client.get(url, **kwargs)
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        try:
            data = response.json()
            print(f"Response data (first 100 chars): {str(data)[:100]}...")
            return data
        except:
            print(f"Response text: {response.text[:200]}...")
            return response.text
```

#### 3. Performance Debugging
```python
import time
import cProfile
import pstats

def profile_function(func, *args, **kwargs):
    """Profile function execution"""
    profiler = cProfile.Profile()
    
    start_time = time.time()
    result = profiler.runcall(func, *args, **kwargs)
    end_time = time.time()
    
    print(f"Function took {end_time - start_time:.2f} seconds")
    
    # Print profiling results
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)  # Top 10 functions
    
    return result

# Usage
result = profile_function(my_expensive_function, arg1, arg2)
```

### Troubleshooting FAQ

#### Common Issues and Solutions

##### 1. Database Connection Issues
```bash
# Check database file permissions
ls -la vprism_data.duckdb

# Verify database integrity - USE UV ONLY
uv run python -c "import duckdb; duckdb.connect('vprism_data.duckdb').execute('PRAGMA integrity_check')"

# Reset database - USE UV ONLY
rm vprism_data.duckdb
uv run python -m vprism.cli init-db
```

##### 2. Provider Rate Limiting
```python
# Check rate limits in logs
grep "Rate limit" debug.log

# Test provider response
curl -I "https://api.alpaca.markets/v2/assets"

# Use test mode to avoid real API calls
export VPRISM_TEST_MODE=true
```

##### 3. Cache Issues
```python
# Clear cache programmatically
from vprism.core.cache import CacheManager
cache = CacheManager()
cache.clear()

# Clear cache via CLI - USE UV ONLY
uv run python -m vprism.cli clear-cache
```

##### 4. Type Checking Issues
```bash
# Run mypy with verbose output - USE UV ONLY
uv run mypy src/vprism --strict --verbose

# Check specific file - USE UV ONLY
uv run mypy src/vprism/providers/yahoo.py --strict

# Generate type coverage report - USE UV ONLY
uv run mypy src/vprism --strict --html-report mypy_report
```

##### 5. UV Toolchain Issues
```bash
# Install uv if not available
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify uv installation
uv --version

# Sync dependencies
uv sync

# Clear uv cache if needed
uv cache clean

# Always use uv prefix for commands
uv run python -c "import vprism; print('OK')"
```

### Development Tools Setup

#### VS Code Configuration
```json
{
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "python.testing.pytestArgs": [
        "tests"
    ],
    "python.linting.mypyEnabled": true,
    "python.linting.enabled": true,
    "python.formatting.provider": "ruff",
    "python.sortImports.args": ["--profile", "black"],
    "python.analysis.typeCheckingMode": "strict"
}
```

#### PyCharm Configuration
1. **Interpreter**: Set to project virtual environment
2. **Testing**: Configure pytest as test runner
3. **Type Checking**: Enable mypy integration
4. **Code Style**: Import ruff configuration
5. **Run/Debug**: Configure run configurations for FastAPI server

### Continuous Integration

#### GitHub Actions Workflow
```yaml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.11, 3.12, 3.13]
    
    steps:
    - uses: actions/checkout@v4
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install uv
      run: pip install uv
    
    - name: Install dependencies
      run: uv sync
    
    - name: Run tests
      run: uv run pytest --cov=vprism --cov-report=xml
    
    - name: Type checking
      run: uv run mypy src/vprism --strict
    
    - name: Code formatting check
      run: uv run ruff format --check
    
    - name: Linting
      run: uv run ruff check
```

### Enforcement

This workflow is mandatory for all contributors. Violations will be caught during code review and must be resolved before merge.