# Technology Stack

## Build System & Package Management
- **Package Manager**: uv (modern Python package manager)
- **Build Backend**: hatchling
- **Python Version**: 3.11+ (supports 3.11 and 3.12)

## Core Framework & Libraries
- **Web Framework**: FastAPI (>=0.104.0) with uvicorn
- **Data Models**: Pydantic v2 (>=2.5.0) with pydantic-settings
- **HTTP Client**: httpx (>=0.25.0)
- **Async Support**: aioredis (>=2.0.0)

## Data Processing
- **DataFrames**: pandas (>=2.1.0) and polars (>=0.19.0)
- **Database**: DuckDB (>=0.9.0) for analytics
- **Caching**: Redis via aioredis

## CLI & User Interface
- **CLI Framework**: typer (>=0.9.0)
- **Rich Output**: rich (>=13.0.0) for formatted console output

## Development Tools
- **Linting**: ruff (>=0.1.0) - replaces flake8, isort, and more
- **Formatting**: ruff format (replaces black)
- **Type Checking**: mypy (>=1.7.0) with strict mode
- **Testing**: pytest with asyncio, coverage, and mock support
- **Pre-commit**: pre-commit hooks for code quality

## Common Commands

### Development Setup
```bash
make dev-setup          # Set up development environment
make install            # Install dependencies
```

### Code Quality
```bash
make lint               # Run linting checks
make format             # Format code
make format-check       # Check code formatting
make type-check         # Run type checking
make check-all          # Run all checks
```

### Testing
```bash
make test               # Run tests with coverage
make test-fast          # Run tests without coverage
```

### Build & Release
```bash
make build              # Build package
make clean              # Clean build artifacts
make release VERSION=x.y.z  # Create release
```

### CI/Local Validation
```bash
make ci                 # Run all CI checks locally
```

## Configuration Standards
- **Line Length**: 88 characters (ruff/black standard)
- **Target Python**: 3.11+
- **Coverage Requirement**: 90% minimum
- **Type Checking**: Strict mode enabled