# vPrism - Unified Financial Data Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

vPrism is a comprehensive financial data platform that provides unified access to multiple financial data sources through consistent, high-performance APIs. It abstracts away the complexity of managing multiple data providers, rate limits, and data format inconsistencies.

## 🚀 Quick Start

### Installation
```bash
pip install vprism
```

### Basic Usage
```python
from vprism import VPrismClient

# Create client
client = VPrismClient()

# Get stock data
data = await client.get_stock_data("AAPL", period="1y")
print(data.head())

# Use MCP server
# Start: python -m src.vprism_mcp
```

### Docker Deployment
```bash
docker-compose up -d
```

## 🏗️ Architecture

vPrism is built with a modular, scalable architecture:

```
vprism/
├── src/core/              # Core business logic
├── src/web/               # FastAPI web service
├── src/vprism_mcp/        # MCP server
├── src/docker/            # Docker configuration
├── tests/                 # Comprehensive test suite
└── docs/                  # Documentation
```

### Core Components

#### 1. Data Layer (`src/core/data/`)
- **Multi-level caching** (memory, DuckDB, file-based)
- **Provider abstraction** (Yahoo Finance, Alpha Vantage, AkShare)
- **Rate limiting** and **circuit breaker** patterns
- **Data validation** and **quality checks**

#### 2. Service Layer (`src/core/services/`)
- **Batch processing** for large data requests
- **Data routing** between providers
- **Query optimization** and **caching**

#### 3. API Layer
- **MCP Server**: Native Model Context Protocol support
- **Web API**: RESTful FastAPI service
- **Python Library**: Simple, intuitive interface

## 📊 Features

### Data Sources
- ✅ **Yahoo Finance**: Real-time and historical stock data
- ✅ **Alpha Vantage**: Comprehensive financial data with fundamentals
- ✅ **AkShare**: Chinese market data and alternative sources
- ✅ **Extensible**: Easy to add new providers

### Performance & Reliability
- **Multi-level caching** for optimal performance
- **Automatic failover** between providers
- **Rate limit management** with exponential backoff
- **Circuit breaker** pattern for resilience
- **Health monitoring** and **metrics**

### Developer Experience
- **MCP Server**: AI-native design for chatbots and AI assistants
- **Comprehensive documentation** with examples
- **Docker support** for easy deployment
- **Type hints** and **async/await** support

## 🎯 Use Cases

### 1. AI Financial Assistant
```python
# MCP server provides data to AI chatbots
python -m src.vprism_mcp
```

### 2. Algorithmic Trading
```python
from vprism import VPrismClient

client = VPrismClient()
data = await client.get_stock_data("TSLA", period="1d", interval="1m")
```

### 3. Financial Research
```python
# Batch processing for large datasets
batch = client.create_batch()
batch.add_request("AAPL", "1y")
batch.add_request("GOOGL", "1y")
results = await batch.execute()
```

### 4. Web Applications
```bash
# Start web service
uvicorn src.web.main:app --reload
```

## 📁 Project Structure

```
vprism/
├── src/
│   ├── core/                    # Core business logic
│   │   ├── client/              # Client implementation
│   │   ├── config/              # Configuration management
│   │   ├── data/                # Data layer
│   │   │   ├── cache/           # Multi-level caching
│   │   │   ├── providers/       # Data providers
│   │   │   ├── repositories/    # Data access patterns
│   │   │   └── storage/         # Database abstraction
│   │   ├── exceptions/          # Error handling
│   │   ├── models/              # Data models
│   │   ├── services/            # Business services
│   │   └── validation/          # Data validation
│   ├── web/                     # FastAPI web service
│   ├── vprism_mcp/              # MCP server
│   └── docker/                  # Docker configuration
├── tests/                       # Test suite
├── docs/                        # Documentation
└── examples/                    # Usage examples
```

## 🛠️ Development

### Setup Development Environment
```bash
# Clone repository
git clone https://github.com/your-repo/vprism.git
cd vprism

# Install with development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
```

### Configuration
```toml
# vprism.toml
[cache]
memory_ttl = 300
file_ttl = 86400

[providers]
yfinance = { enabled = true }
alpha_vantage = { api_key = "your_key" }

[logging]
level = "INFO"
```

## 📚 Documentation

- **[Quick Start](docs/quickstart.md)** - Get started in 5 minutes
- **[API Documentation](docs/api/)** - Complete API reference
- **[Deployment Guide](docs/deployment/)** - Production deployment
- **[Examples](examples/)** - Real-world usage examples

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **[Documentation](https://vprism.readthedocs.io/)**
- **[PyPI Package](https://pypi.org/project/vprism/)**
- **[Docker Hub](https://hub.docker.com/r/vprism/vprism)**
- **[GitHub Issues](https://github.com/your-repo/vprism/issues)**

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Data providers: Yahoo Finance, Alpha Vantage, AkShare
- Inspired by the need for reliable, unified financial data access