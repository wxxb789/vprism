# Project Structure

## Root Directory Layout
```
vprism/
├── .kiro/                  # Kiro IDE configuration and steering
├── vprism/                 # Main package source code
├── tests/                  # Test suite
├── pyproject.toml          # Project configuration and dependencies
├── Makefile               # Development commands
├── README.md              # Project documentation
├── uv.lock               # Dependency lock file
└── .pre-commit-config.yaml # Pre-commit hooks
```

## Source Code Organization (`vprism/`)
```
vprism/
├── __init__.py            # Package entry point with convenience functions
├── cli.py                 # Command-line interface
└── core/                  # Core business logic
    ├── __init__.py
    ├── client.py          # Main client interface
    ├── models.py          # Pydantic data models
    ├── exceptions.py      # Custom exception classes
    ├── config.py          # Configuration management
    ├── interfaces.py      # Abstract interfaces/protocols
    ├── provider_*.py      # Provider-related modules
    ├── data_router.py     # Data routing logic
    ├── cache.py           # Caching implementation
    └── repository.py      # Data persistence layer
```

## Test Organization (`tests/`)
```
tests/
├── __init__.py
├── test_*.py              # Module-level tests
├── core/                  # Core module tests
│   └── test_*.py
└── __pycache__/           # Python cache (ignored)
```

## Architecture Patterns

### Core Principles
- **Separation of Concerns**: Clear boundaries between CLI, client, core logic, and providers
- **Provider Abstraction**: Unified interface for multiple data providers
- **Async-First**: Built around async/await patterns for performance
- **Type Safety**: Comprehensive type hints with mypy strict mode

### Module Responsibilities
- **`__init__.py`**: Public API with convenience functions (`get()`, `aget()`)
- **`cli.py`**: Command-line interface using typer and rich
- **`core/client.py`**: Main client class for both sync and async operations
- **`core/models.py`**: Pydantic models for data structures and validation
- **`core/exceptions.py`**: Custom exception hierarchy with error codes
- **`core/provider_*.py`**: Provider abstraction and implementations

### Naming Conventions
- **Files**: Snake_case (e.g., `data_router.py`)
- **Classes**: PascalCase (e.g., `VPrismClient`, `DataResponse`)
- **Functions/Variables**: Snake_case (e.g., `get_data`, `asset_type`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `DEFAULT_TIMEOUT`)
- **Private Members**: Leading underscore (e.g., `_internal_method`)

### Import Organization
1. Standard library imports
2. Third-party imports
3. Local application imports
4. Use `from __future__ import annotations` for forward references

### Error Handling
- Use custom `VPrismException` with error codes
- Provide detailed error messages and optional details dict
- Handle both sync and async error propagation consistently

### Testing Structure
- Mirror source structure in tests
- Use descriptive test class and method names
- Group related tests in classes
- Use pytest fixtures for common setup
- Aim for 90%+ test coverage