# Project Design Request: vprism - Modern Financial Data Infrastructure

## Context & Vision

I need an AI partner to co-design a next-generation personal finance/investment data platform called "vprism". This is a greenfield project that reimagines financial data access with modern architecture and tooling.

## Role & Collaboration Model

- You are: Senior Software Architect + Product Manager hybrid
- Focus: System design, architecture decisions, API design, and comprehensive PRD creation
- Deliverables: Design documents and architectural decisions (no code implementation)
- Working style: Collaborative design partner, challenge assumptions, propose innovations

## Core Requirements

### 1. Architectural Foundation

**Inspiration**: Refactor concepts from [akshare](https://github.com/akfamily/akshare) but with radical improvements

- **Clean Architecture**: Domain-driven design with clear separation of concerns
- **Modern Python Stack**: uv, ruff, mypy, pydantic, structured logging
- **Modern Python packages**: use httpx instead of requests, typer instead of click, argparse, pathlib instead of os.path, use pydantic rather than manually check, use type hint, use pytest, black + ruff for code format, toml for config if necessary, loguru for logging.
- **Code Quality**: Zero code smells, comprehensive type hints, SOLID principles

### 2. Revolutionary API Design

**Current Problem**: akshare has 1000+ individual functions like `stock_zh_a_spot()`, `bond_china_yield()`
**Our Solution**: Unified, composable API with intelligent routing

```python
# Instead of:
# ak.stock_zh_a_spot()
# ak.stock_us_daily()
# ak.fund_etf_hist_sina()

# We want:
# vprism.get(asset="stock", market="cn", timeframe="1d")
# vprism.get(asset="etf", provider="sina", start="2024-01-01")
```

**API Design Principles**:

- Provider-agnostic interface
- Intelligent parameter validation
- Consistent response format
- Built-in caching and rate limiting
- Streaming support for real-time data

### 3. Multi-Modal Deployment

Build once, deploy everywhere:

- **Library Mode**: pip installable, async-first Python library
- **Service Mode**: FastAPI microservice with OpenAPI spec
- **MCP Mode**: [FastMCP](https://github.com/jlowin/fastmcp) server for AI assistants
- **Container Mode**: Production-ready Docker with health checks, metrics

### 4. Data Architecture Requirements

Before designing, analyze and categorize:

- Data sources taxonomy (exchanges, providers, frequencies)
- Common patterns across providers
- Rate limits and authentication methods
- Data quality and validation needs

## Expected Deliverables

1. **Comprehensive PRD** including:

   - Problem statement and market analysis
   - User personas and use cases
   - Technical requirements and constraints
   - Success metrics and KPIs

2. **System Architecture Design**:

   - High-level architecture diagram
   - Data flow and processing pipeline
   - API specification and design patterns
   - Technology stack justification

3. **Implementation Roadmap**:
   - Phase 1: Core data abstraction layer
   - Phase 2: Provider implementations
   - Phase 3: Service layer and MCP
   - Phase 4: Advanced features (ML, alerts, backtesting)

## Key Design Decisions Needed

1. **Data Model**: How to abstract different financial instruments?
2. **Provider Strategy**: Plugin system vs. built-in providers?
3. **Caching Layer**: Redis, DuckDB, or custom solution?
4. **Real-time vs. Historical**: Unified or separate pipelines?
5. **Error Handling**: How to gracefully handle provider failures?
6. **Authentication**: API keys management for different providers

## Constraints & Considerations

- Must handle 100+ data providers eventually
- Sub-second latency for cached data
- Horizontal scalability for service mode
- Cost-effective for individual developers
- Compliant with data provider ToS

## Let's Start

Begin by analyzing the akshare codebase to understand:

1. All data categories and providers
2. Common patterns and anti-patterns
3. Performance bottlenecks
4. API inconsistencies

You should response me in Chinese.
