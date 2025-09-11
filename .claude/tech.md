# Technical Standards - vPrism

This document defines the technical standards, patterns, and architectural guidelines for the vPrism project.

## Core Technology Stack

### MCP (Model Context Protocol) Implementation
**CRITICAL REQUIREMENT**: This project **MUST** use [fastmcp](https://github.com/jlowin/fastmcp) version 2.x or later.

- **Package**: `fastmcp>=2.10.6`
- **Prohibited**: Do not use the official `mcp` python package
- **Rationale**: fastmcp provides a more Pythonic, decorator-based API that aligns with our async-first architecture

### Framework & Libraries
- **Web Framework**: FastAPI >= 0.104.0
- **Async Runtime**: uvicorn[standard] >= 0.24.0
- **Type System**: Pydantic >= 2.5.0
- **HTTP Client**: httpx >= 0.25.0
- **Task Queue**: asyncio (built-in)

### Data Processing
- **DataFrames**: pandas >= 2.1.0, polars >= 0.19.0
- **Database**: duckdb >= 0.9.0
- **Caching**: Multi-level cache (memory + DuckDB)

### Development & Testing
- **Testing**: pytest >= 8.4.1, pytest-asyncio >= 1.1.0
- **Linting**: ruff >= 0.1.0
- **Type Checking**: mypy >= 1.7.0
- **Logging**: loguru >= 0.7.0

## Architecture Patterns

### New Project Structure
All core functionality has been reorganized under `src/core/` for better modularity:

```
src/core/
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

### MCP Server Architecture
```python
# FastMCP-based server implementation in src/vprism_mcp/
from fastmcp import FastMCP
from src.core.services.data import DataService
from src.core.data.providers import get_provider

class VPrismMCPServer:
    def __init__(self):
        self.mcp = FastMCP("vprism-financial-data")
        self.data_service = DataService()
        self._setup_tools()
    
    def _setup_tools(self):
        @self.mcp.tool()
        async def get_stock_data(symbol: str, period: str = "1y"):
            """Get stock data for a given symbol."""
            return await self.data_service.get_stock_data(symbol, period)
        
        @self.mcp.resource("data://markets")
        async def get_markets():
            """Get available markets."""
            return await self.data_service.get_available_markets()
```

### Async-First Design
- All I/O operations must be async
- Use `async def` for all methods that perform I/O
- Prefer `asyncio.gather()` for concurrent operations
- Implement proper cancellation handling

### Error Handling
- Use custom exception hierarchy from `core.exceptions`
- Implement circuit breaker pattern for external services
- Provide meaningful error messages in MCP responses
- Log errors with appropriate context using structured logging

## Data Provider Integration

### Provider Architecture
- **Base Class**: `src.core.data.providers.base.DataProvider`
- **Naming Convention**: `{ProviderName}` (no "Provider" suffix)
- **Registration**: Use provider factory pattern in `src.core.data.providers.registry`

### Rate Limiting
- Implement exponential backoff
- Use token bucket algorithm for rate limiting
- Respect API provider limits

## Configuration Management

### Environment Variables
All configuration must use `VPRISM_` prefix:
- `VPRISM_API_KEY`
- `VPRISM_CACHE_SIZE`
- `VPRISM_LOG_LEVEL`

### Configuration Files
- Primary: `vprism.toml` (TOML format)
- Optional: `vprism.yaml` (YAML format)
- Schema validation using Pydantic Settings

## Testing Standards

### Test Structure
```
tests/
├── test_*.py           # Unit tests for src/core/
├── web/
│   └── test_*.py       # Web service tests (src/web/)
└── integration/
    └── test_*.py       # Integration tests
```

### Test Requirements
- All public methods must have corresponding tests
- Use pytest-asyncio for async tests
- Mock external API calls
- Achieve >80% code coverage

### MCP Testing
- Test all MCP tools and resources
- Validate parameter handling
- Test error scenarios
- Verify response formats

## Security Guidelines

### API Key Management
- Store keys in environment variables
- Never commit keys to version control
- Use key rotation when possible

### Input Validation
- Validate all input parameters
- Sanitize user-provided data
- Implement rate limiting per client

## Performance Standards

### Caching Strategy
- **L1 Cache**: In-memory (TTL: 5 minutes)
- **L2 Cache**: DuckDB (TTL: 1 hour)
- **L3 Cache**: File-based (TTL: 24 hours)

### Response Time Targets
- MCP tool responses: < 2 seconds
- Batch operations: < 10 seconds
- Historical data: < 30 seconds

## Code Quality

### Type Hints
- All public APIs must have type hints
- Use `from typing import ...` for complex types
- Prefer `TypedDict` over `dict` for structured data

### Documentation
- All public methods must have docstrings
- Include parameter descriptions and examples
- Document error conditions

### Code Formatting
- Use ruff for formatting and linting
- Line length: 88 characters
- Follow PEP 8 style guidelines

## Deployment

### Container Requirements
- Use official Python 3.13+ image
- Multi-stage builds for optimization
- Health checks for MCP server
- Proper signal handling for graceful shutdown

### Monitoring
- Structured logging with request IDs
- Health check endpoints
- Metrics collection (response times, error rates)
- Alerting for critical failures

## MCP-Specific Guidelines

### Tool Design
- Tools should be atomic and focused
- Use descriptive parameter names
- Provide helpful error messages
- Include examples in docstrings

### Resource Design
- Use consistent URI patterns: `data://{type}/{identifier}`
- Implement proper caching headers
- Support conditional requests

### Prompt Design
- Create reusable prompt templates
- Include parameter validation
- Provide context-aware suggestions