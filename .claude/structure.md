# Project Structure - vPrism

This document defines the file organization and naming conventions for the vPrism project.

## Root Structure

```
vprism/
├── vprism/                  # Source code
├── tests/                   # Test files
├── docs/                    # Documentation
├── examples/                # Usage examples
├── data/                    # Application data
├── logs/                    # Log files
├── devjournal/             # Development documentation
├── docker/                 # Docker configuration
├── pyproject.toml          # Project configuration
├── uv.lock                # Dependency lock file
└── README.md              # Project overview
```

## Source Code Structure (`vprism/`)

### Core Architecture (`vprism/core/`)
All core business logic and shared components are organized under `vprism/core/`:

```
vprism/core/
├── __init__.py
├── client/                 # Client building and query execution
├── config/                 # Configuration management
├── data/                   # Data layer (cache, providers, repositories)
├── exceptions/             # Exception handling system
├── health/                 # Health checking system
├── logging/                # Logging configuration
├── models/                 # Data models and schemas
├── monitoring/             # Monitoring and metrics
├── patterns/               # Design patterns (circuit breaker, retry, etc.)
├── services/               # Core business services
└── validation/             # Data validation and quality
```

### Service Layer
- **Web Service** (`vprism/web/`): FastAPI-based web service
- **MCP Server** (`vprism/mcp/`): Model Context Protocol server
- **Docker** (`vprism/docker/`): Docker configuration and deployment

## Detailed Component Structure

### Client Layer (`vprism/core/client/`)
```
client/
├── __init__.py
├── builder.py             # Client builder pattern
├── client.py              # Main client implementation
└── query.py               # Query execution and management
```

### Configuration (`vprism/core/config/`)
```
config/
├── __init__.py
├── cache.py               # Cache configuration
├── logging.py             # Logging configuration
├── provider.py            # Provider configuration
└── settings.py            # Main settings management
```

### Data Layer (`vprism/core/data/`)
```
data/
├── cache/                 # Multi-level caching system
├── providers/             # Data providers (yfinance, alpha_vantage, etc.)
├── repositories/          # Data repositories and access patterns
├── routing.py             # Data routing and orchestration
└── storage/               # Database and storage abstraction
```

### Exception System (`vprism/core/exceptions/`)
```
exceptions/
├── __init__.py
├── base.py                # Base exception classes
├── codes.py               # Error codes enumeration
└── handler.py             # Centralized error handling
```

### Models (`vprism/core/models/`)
```
models/
├── __init__.py
├── base.py                # Base model definitions
├── market.py              # Market data models
├── query.py               # Query and request models
└── response.py            # Response and result models
```

### Services (`vprism/core/services/`)
```
services/
├── __init__.py
├── batch.py               # Batch processing service
├── data.py                # Data processing service
├── data_router.py         # Data routing service
└── routing.py             # Service routing logic
```

## File Naming Conventions

### Python Files
- Use lowercase with underscores: `data_service.py`
- Private modules prefix with underscore: `_internal.py`
- Test files prefix with `test_`: `test_data_service.py`

### Classes
- Use PascalCase: `DataService`, `MarketData`
- Exception classes suffix with `Error`: `DataValidationError`

### Functions and Methods
- Use lowercase with underscores: `get_market_data()`, `validate_input()`
- Private methods prefix with underscore: `_internal_method()`

### Constants
- Use UPPERCASE with underscores: `MAX_CACHE_SIZE`, `DEFAULT_TIMEOUT`

## Directory Organization Patterns

### Feature-Based Grouping
Group related functionality together in dedicated directories:
- All cache-related code in `vprism/core/data/cache/`
- All provider-related code in `vprism/core/data/providers/`
- All validation-related code in `vprism/core/validation/`

### Layer Separation
Maintain clear separation between:
- **Infrastructure**: Database, caching, external APIs
- **Domain**: Business logic and rules
- **Application**: Service orchestration and coordination
- **Presentation**: API endpoints and user interfaces

### Test Structure
Mirror the source structure in tests:
```
tests/
├── test_core/             # Tests for vprism/core/
│   ├── test_data/
│   ├── test_models/
│   └── test_services/
├── web/                   # Web service tests
└── integration/           # Integration tests
```

## Configuration Files

### Project Configuration
- `pyproject.toml`: Main project configuration
- `vprism.toml`: Application configuration (optional)
- `vprism.yaml`: Alternative YAML configuration (optional)

### Environment Variables
All environment variables use `VPRISM_` prefix:
- `VPRISM_API_KEY`
- `VPRISM_LOG_LEVEL`
- `VPRISM_CACHE_SIZE`

## Documentation Structure

### Code Documentation
- All public APIs must have docstrings
- Use Google-style docstrings for consistency
- Include type hints for all public methods
- Document error conditions and edge cases

### Project Documentation
- `docs/`: Technical documentation
- `examples/`: Usage examples and tutorials
- `devjournal/`: Development notes and decisions

## Migration Guidelines

### Legacy Code
When migrating legacy code:
1. Map old structure to new structure
2. Update import statements
3. Ensure tests pass
4. Update documentation references

### New Features
For new features:
1. Follow the established directory structure
2. Place functionality in the appropriate module
3. Add tests in the corresponding test directory
4. Update documentation as needed

## Validation

### Structure Validation
- Ensure all imports work correctly
- Verify test discovery works
- Check that Docker builds succeed
- Validate documentation generation

### Consistency Checks
- Naming conventions are followed
- File organization matches patterns
- Configuration is properly structured
- Documentation is up-to-date