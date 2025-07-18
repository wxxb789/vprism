# vprism 系统设计文档

## 概述

vprism 是一个现代化的金融数据基础设施平台，旨在解决 akshare 等传统金融数据库的架构问题。通过采用领域驱动设计（DDD）、清洁架构原则和现代 Python 技术栈，vprism 提供统一的、可组合的 API 接口，支持多模态部署，为个人开发者到企业级应用提供高性能、可扩展的金融数据访问解决方案。

### 核心设计原则

1. **统一性优于分散性**：用一个可组合的 API 替代 1000+ 个分散函数
2. **现代性优于兼容性**：采用最新的 Python 生态系统和最佳实践
3. **可扩展性优于简单性**：设计支持从个人使用到企业级部署的扩展
4. **类型安全优于运行时检查**：100% 类型提示和编译时验证
5. **异步优于同步**：原生支持异步操作和并发处理

## 架构

### 高层架构

```mermaid
graph TB
    subgraph "客户端层"
        CLI[CLI 工具]
        LIB[Python 库]
        API[REST API]
        MCP[MCP 服务器]
    end
    
    subgraph "应用层"
        UC[用例层]
        SVC[服务层]
    end
    
    subgraph "领域层"
        DOM[领域模型]
        REPO[仓储接口]
    end
    
    subgraph "基础设施层"
        PROV[数据提供商适配器]
        CACHE[缓存层]
        STORE[存储层]
        AUTH[认证管理]
    end
    
    subgraph "外部系统"
        EXT1[交易所 API]
        EXT2[第三方数据商]
        EXT3[缓存存储]
        EXT4[持久化存储]
    end
    
    CLI --> UC
    LIB --> UC
    API --> UC
    MCP --> UC
    
    UC --> SVC
    SVC --> DOM
    SVC --> REPO
    
    REPO --> PROV
    REPO --> CACHE
    REPO --> STORE
    
    PROV --> AUTH
    PROV --> EXT1
    PROV --> EXT2
    
    CACHE --> EXT3
    STORE --> EXT4
```

### 领域驱动设计架构

系统采用六边形架构（端口和适配器模式），确保业务逻辑与外部依赖的解耦：

```mermaid
graph LR
    subgraph "核心领域"
        DOMAIN[领域模型<br/>- Asset<br/>- Market<br/>- DataPoint<br/>- Provider]
        SERVICES[领域服务<br/>- DataAggregator<br/>- PriceCalculator<br/>- Validator]
    end
    
    subgraph "应用层"
        USECASE[用例<br/>- GetMarketData<br/>- StreamRealTime<br/>- CacheData]
    end
    
    subgraph "端口"
        INBOUND[入站端口<br/>- DataQuery<br/>- StreamSubscription]
        OUTBOUND[出站端口<br/>- DataRepository<br/>- CacheRepository<br/>- NotificationPort]
    end
    
    subgraph "适配器"
        WEB[Web 适配器<br/>- FastAPI<br/>- WebSocket]
        CLI_ADAPTER[CLI 适配器<br/>- Typer]
        DATA[数据适配器<br/>- Provider APIs<br/>- Database<br/>- Redis]
    end
    
    WEB --> INBOUND
    CLI_ADAPTER --> INBOUND
    INBOUND --> USECASE
    USECASE --> DOMAIN
    USECASE --> SERVICES
    USECASE --> OUTBOUND
    OUTBOUND --> DATA
```

## 组件和接口

### 核心组件架构

#### 1. 统一数据访问层 (Unified Data Access Layer)

```python
# 核心接口设计
class DataQuery:
    asset: AssetType
    market: Optional[MarketType] = None
    provider: Optional[ProviderType] = None
    timeframe: Optional[TimeFrame] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    symbols: Optional[List[str]] = None
    
class DataResponse:
    data: List[DataPoint]
    metadata: ResponseMetadata
    source: ProviderInfo
    cached: bool
    timestamp: datetime
```

#### 2. 提供商抽象层 (Provider Abstraction Layer)

```python
# 提供商接口
class DataProvider(ABC):
    @abstractmethod
    async def get_data(self, query: DataQuery) -> DataResponse:
        pass
    
    @abstractmethod
    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        pass
    
    @property
    @abstractmethod
    def supported_assets(self) -> Set[AssetType]:
        pass
    
    @property
    @abstractmethod
    def rate_limits(self) -> RateLimitConfig:
        pass
```

#### 3. 智能路由器 (Intelligent Router)

```python
class DataRouter:
    def __init__(self, providers: List[DataProvider]):
        self.providers = providers
        self.provider_registry = ProviderRegistry(providers)
    
    async def route_query(self, query: DataQuery) -> DataProvider:
        # 智能选择最佳提供商
        candidates = self.provider_registry.find_providers(query)
        return await self.select_best_provider(candidates, query)
    
    async def select_best_provider(
        self, 
        candidates: List[DataProvider], 
        query: DataQuery
    ) -> DataProvider:
        # 基于延迟、可用性、成本等因素选择
        pass
```

### 数据模型设计

#### 核心领域模型

```python
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

class AssetType(str, Enum):
    STOCK = "stock"
    BOND = "bond"
    ETF = "etf"
    FUND = "fund"
    FUTURES = "futures"
    OPTIONS = "options"
    FOREX = "forex"
    CRYPTO = "crypto"
    INDEX = "index"
    COMMODITY = "commodity"

class MarketType(str, Enum):
    CN = "cn"  # 中国
    US = "us"  # 美国
    HK = "hk"  # 香港
    EU = "eu"  # 欧洲
    JP = "jp"  # 日本
    GLOBAL = "global"

class TimeFrame(str, Enum):
    TICK = "tick"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"

class DataPoint(BaseModel):
    symbol: str
    timestamp: datetime
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    extra_fields: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }

class Asset(BaseModel):
    symbol: str
    name: str
    asset_type: AssetType
    market: MarketType
    currency: str
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 缓存和存储策略

#### 多层缓存架构

```mermaid
graph TD
    subgraph "缓存层次"
        L1[L1: 内存缓存<br/>Redis/内存<br/>< 1秒数据]
        L2[L2: 本地存储<br/>DuckDB<br/>历史数据]
        L3[L3: 分布式存储<br/>对象存储<br/>长期归档]
    end
    
    subgraph "缓存策略"
        HOT[热数据<br/>实时价格<br/>高频访问]
        WARM[温数据<br/>日线数据<br/>中频访问]
        COLD[冷数据<br/>历史数据<br/>低频访问]
    end
    
    HOT --> L1
    WARM --> L2
    COLD --> L3
```

#### 缓存实现

```python
class CacheStrategy(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        pass

class MultiLevelCache:
    def __init__(self):
        self.l1_cache = RedisCache()  # 实时数据
        self.l2_cache = DuckDBCache()  # 历史数据
        self.l3_cache = ObjectStorageCache()  # 归档数据
    
    async def get_data(self, query: DataQuery) -> Optional[DataResponse]:
        # 按层级查找缓存
        if query.is_realtime():
            return await self.l1_cache.get(query.cache_key())
        elif query.is_recent():
            return await self.l2_cache.get(query.cache_key())
        else:
            return await self.l3_cache.get(query.cache_key())
```

## 错误处理

### 统一错误处理架构

```python
class VPrismException(Exception):
    """vprism 基础异常类"""
    def __init__(self, message: str, error_code: str, details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

class ProviderException(VPrismException):
    """数据提供商相关异常"""
    pass

class RateLimitException(ProviderException):
    """速率限制异常"""
    pass

class DataValidationException(VPrismException):
    """数据验证异常"""
    pass

class ErrorHandler:
    async def handle_provider_error(self, error: Exception, provider: str) -> DataResponse:
        if isinstance(error, RateLimitException):
            # 实施退避策略
            await self.backoff_strategy.wait()
            # 尝试备用提供商
            return await self.try_fallback_provider()
        elif isinstance(error, ProviderException):
            # 记录错误并返回错误响应
            logger.error(f"Provider {provider} failed: {error}")
            return self.create_error_response(error)
        else:
            # 未知错误，重新抛出
            raise error
```

### 故障转移和重试机制

```python
class FaultTolerantDataService:
    def __init__(self, providers: List[DataProvider]):
        self.providers = providers
        self.circuit_breaker = CircuitBreaker()
        self.retry_policy = ExponentialBackoffRetry()
    
    async def get_data_with_fallback(self, query: DataQuery) -> DataResponse:
        for provider in self.providers:
            try:
                if self.circuit_breaker.is_open(provider.name):
                    continue
                
                return await self.retry_policy.execute(
                    lambda: provider.get_data(query)
                )
            except Exception as e:
                self.circuit_breaker.record_failure(provider.name)
                logger.warning(f"Provider {provider.name} failed: {e}")
                continue
        
        raise NoAvailableProviderException("All providers failed")
```

## 测试策略

### 测试金字塔

```mermaid
graph TD
    subgraph "测试层次"
        E2E[端到端测试<br/>完整用户场景<br/>少量但关键]
        INTEGRATION[集成测试<br/>组件间交互<br/>中等数量]
        UNIT[单元测试<br/>单个组件<br/>大量且快速]
    end
    
    subgraph "测试类型"
        CONTRACT[契约测试<br/>API 兼容性]
        PERFORMANCE[性能测试<br/>延迟和吞吐量]
        CHAOS[混沌测试<br/>故障注入]
    end
    
    E2E --> CONTRACT
    INTEGRATION --> PERFORMANCE
    UNIT --> CHAOS
```

### 测试实现策略

```python
# 单元测试示例
class TestDataRouter:
    @pytest.fixture
    def mock_providers(self):
        return [
            MockProvider("provider_a", [AssetType.STOCK]),
            MockProvider("provider_b", [AssetType.BOND])
        ]
    
    @pytest.mark.asyncio
    async def test_route_stock_query(self, mock_providers):
        router = DataRouter(mock_providers)
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.CN)
        
        provider = await router.route_query(query)
        
        assert provider.name == "provider_a"
        assert AssetType.STOCK in provider.supported_assets

# 集成测试示例
class TestDataService:
    @pytest.mark.integration
    async def test_get_stock_data_with_cache(self):
        service = DataService()
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"]
        )
        
        # 第一次请求应该从提供商获取
        response1 = await service.get_data(query)
        assert not response1.cached
        
        # 第二次请求应该从缓存获取
        response2 = await service.get_data(query)
        assert response2.cached

# 性能测试示例
class TestPerformance:
    @pytest.mark.performance
    async def test_concurrent_requests(self):
        service = DataService()
        queries = [
            DataQuery(asset=AssetType.STOCK, symbols=[f"00000{i}"])
            for i in range(100)
        ]
        
        start_time = time.time()
        responses = await asyncio.gather(*[
            service.get_data(query) for query in queries
        ])
        end_time = time.time()
        
        assert len(responses) == 100
        assert end_time - start_time < 5.0  # 5秒内完成100个请求
```

### 测试数据管理

```python
class TestDataFactory:
    @staticmethod
    def create_stock_data(symbol: str = "000001", days: int = 30) -> List[DataPoint]:
        base_date = datetime.now() - timedelta(days=days)
        return [
            DataPoint(
                symbol=symbol,
                timestamp=base_date + timedelta(days=i),
                open=Decimal("10.00") + Decimal(str(random.uniform(-1, 1))),
                high=Decimal("10.50") + Decimal(str(random.uniform(-1, 1))),
                low=Decimal("9.50") + Decimal(str(random.uniform(-1, 1))),
                close=Decimal("10.00") + Decimal(str(random.uniform(-1, 1))),
                volume=Decimal(str(random.randint(1000000, 10000000)))
            )
            for i in range(days)
        ]
    
    @staticmethod
    def create_mock_provider(name: str, assets: List[AssetType]) -> MockProvider:
        return MockProvider(
            name=name,
            supported_assets=set(assets),
            test_data=TestDataFactory.create_stock_data()
        )
```

这个设计文档涵盖了 vprism 的核心架构、组件设计、数据模型、错误处理和测试策略。设计遵循了现代软件架构的最佳实践，确保系统的可扩展性、可维护性和高性能。
## 多
模态部署架构

### 部署模式对比

| 部署模式 | 目标用户 | 特点 | 技术栈 |
|---------|---------|------|--------|
| 库模式 | 个人开发者、数据科学家 | 轻量级、易集成 | Python Package |
| 服务模式 | 企业、团队 | 高并发、可扩展 | FastAPI + Docker |
| MCP 模式 | AI 助手、自动化 | 标准化接口 | FastMCP Server |
| 容器模式 | 生产环境 | 高可用、监控 | Kubernetes |

### 1. 库模式 (Library Mode)

```python
# 用户使用示例
import vprism

# 同步接口
data = vprism.get(asset="stock", market="cn", symbols=["000001"])

# 异步接口
async def get_data():
    async with vprism.AsyncClient() as client:
        data = await client.get(asset="stock", market="cn", symbols=["000001"])
        async for point in client.stream(asset="stock", symbols=["000001"]):
            print(point)

# 配置管理
vprism.configure(
    providers=["tushare", "akshare", "yahoo"],
    cache_backend="redis://localhost:6379",
    log_level="INFO"
)
```

### 2. 服务模式 (Service Mode)

```python
# FastAPI 应用结构
from fastapi import FastAPI, Depends
from vprism.web import create_app
from vprism.dependencies import get_data_service

app = create_app()

@app.get("/api/v1/data")
async def get_market_data(
    asset: AssetType,
    market: MarketType = None,
    symbols: List[str] = Query(...),
    service: DataService = Depends(get_data_service)
):
    query = DataQuery(asset=asset, market=market, symbols=symbols)
    return await service.get_data(query)

@app.websocket("/api/v1/stream")
async def stream_data(websocket: WebSocket):
    await websocket.accept()
    # 实时数据流实现
    pass
```

### 3. MCP 模式 (Model Context Protocol)

```python
# FastMCP 服务器实现
from fastmcp import FastMCP
from vprism.mcp import VPrismMCPServer

mcp = FastMCP("vprism-financial-data")

@mcp.tool()
async def get_stock_data(
    symbols: List[str],
    market: str = "cn",
    timeframe: str = "1d"
) -> Dict[str, Any]:
    """获取股票数据的 MCP 工具"""
    service = VPrismMCPServer()
    return await service.get_stock_data(symbols, market, timeframe)

@mcp.tool()
async def get_market_overview(market: str = "cn") -> Dict[str, Any]:
    """获取市场概览的 MCP 工具"""
    service = VPrismMCPServer()
    return await service.get_market_overview(market)

if __name__ == "__main__":
    mcp.run()
```

### 4. 容器模式 (Container Mode)

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装 uv
RUN pip install uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装依赖
RUN uv sync --frozen

# 复制应用代码
COPY . .

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动应用
CMD ["uv", "run", "uvicorn", "vprism.web:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# Kubernetes 部署配置
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vprism-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: vprism-api
  template:
    metadata:
      labels:
        app: vprism-api
    spec:
      containers:
      - name: vprism-api
        image: vprism:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## 技术栈详细说明

### 核心技术栈

```toml
# pyproject.toml
[project]
name = "vprism"
version = "0.1.0"
description = "Modern Financial Data Infrastructure"
authors = [{name = "vprism Team"}]
requires-python = ">=3.11"
dependencies = [
    # 核心框架
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5.0",
    
    # HTTP 客户端
    "httpx>=0.25.0",
    
    # 异步支持
    "asyncio-mqtt>=0.13.0",
    "aioredis>=2.0.0",
    
    # 数据处理
    "pandas>=2.1.0",
    "polars>=0.19.0",
    "duckdb>=0.9.0",
    
    # 命令行
    "typer>=0.9.0",
    "rich>=13.0.0",
    
    # 日志和监控
    "loguru>=0.7.0",
    "prometheus-client>=0.19.0",
    "opentelemetry-api>=1.21.0",
    
    # 配置管理
    "pydantic-settings>=2.1.0",
    "toml>=0.10.0",
    
    # 安全
    "cryptography>=41.0.0",
    "python-jose[cryptography]>=3.3.0",
    
    # MCP 支持
    "fastmcp>=0.2.0",
    
    # 测试
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "httpx[test]>=0.25.0",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.1.0",
    "mypy>=1.7.0",
    "black>=23.0.0",
    "pre-commit>=3.5.0",
]

[tool.ruff]
target-version = "py311"
line-length = 88
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM", "TCH"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
```

### 数据处理管道

```python
class DataPipeline:
    def __init__(self):
        self.extractors = ExtractorRegistry()
        self.transformers = TransformerRegistry()
        self.loaders = LoaderRegistry()
    
    async def process(self, query: DataQuery) -> DataResponse:
        # ETL 管道
        raw_data = await self.extract(query)
        clean_data = await self.transform(raw_data)
        result = await self.load(clean_data)
        return result
    
    async def extract(self, query: DataQuery) -> RawData:
        extractor = self.extractors.get_extractor(query.provider)
        return await extractor.extract(query)
    
    async def transform(self, raw_data: RawData) -> CleanData:
        transformer = self.transformers.get_transformer(raw_data.source_type)
        return await transformer.transform(raw_data)
    
    async def load(self, clean_data: CleanData) -> DataResponse:
        loader = self.loaders.get_loader(clean_data.target_format)
        return await loader.load(clean_data)
```

### 实时数据流处理

```python
class RealTimeDataStream:
    def __init__(self, broker_url: str):
        self.broker = MessageBroker(broker_url)
        self.subscribers = {}
    
    async def subscribe(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        topic = self.generate_topic(query)
        
        async for message in self.broker.subscribe(topic):
            data_point = self.deserialize_message(message)
            yield data_point
    
    async def publish(self, data_point: DataPoint):
        topic = self.generate_topic_from_data(data_point)
        message = self.serialize_data_point(data_point)
        await self.broker.publish(topic, message)
    
    def generate_topic(self, query: DataQuery) -> str:
        return f"vprism.{query.asset}.{query.market}.{query.timeframe}"
```

### 监控和可观测性

```python
from prometheus_client import Counter, Histogram, Gauge
from opentelemetry import trace

# 指标定义
REQUEST_COUNT = Counter('vprism_requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('vprism_request_duration_seconds', 'Request duration')
ACTIVE_CONNECTIONS = Gauge('vprism_active_connections', 'Active connections')

tracer = trace.get_tracer(__name__)

class MonitoringMiddleware:
    async def __call__(self, request: Request, call_next):
        with tracer.start_as_current_span("http_request") as span:
            start_time = time.time()
            
            # 记录请求
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path
            ).inc()
            
            try:
                response = await call_next(request)
                span.set_attribute("http.status_code", response.status_code)
                return response
            except Exception as e:
                span.record_exception(e)
                raise
            finally:
                # 记录响应时间
                REQUEST_DURATION.observe(time.time() - start_time)

class HealthCheck:
    def __init__(self, data_service: DataService):
        self.data_service = data_service
    
    async def check_health(self) -> Dict[str, Any]:
        checks = {
            "database": await self.check_database(),
            "cache": await self.check_cache(),
            "providers": await self.check_providers(),
        }
        
        overall_status = "healthy" if all(
            check["status"] == "healthy" for check in checks.values()
        ) else "unhealthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks
        }
```

### 安全和认证

```python
class SecurityManager:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.token_manager = TokenManager(secret_key)
    
    async def authenticate_request(self, request: Request) -> Optional[User]:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        return await self.token_manager.verify_token(token)
    
    def encrypt_api_key(self, api_key: str) -> str:
        fernet = Fernet(self.secret_key.encode())
        return fernet.encrypt(api_key.encode()).decode()
    
    def decrypt_api_key(self, encrypted_key: str) -> str:
        fernet = Fernet(self.secret_key.encode())
        return fernet.decrypt(encrypted_key.encode()).decode()

class RateLimiter:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
    
    async def check_rate_limit(self, user_id: str, endpoint: str) -> bool:
        key = f"rate_limit:{user_id}:{endpoint}"
        current = await self.redis.get(key)
        
        if current is None:
            await self.redis.setex(key, 3600, 1)  # 1 hour window
            return True
        
        if int(current) >= 1000:  # 1000 requests per hour
            return False
        
        await self.redis.incr(key)
        return True
```

这个设计文档现在包含了完整的系统架构、多模态部署方案、技术栈选择和实现细节。设计充分考虑了现代软件开发的最佳实践，确保系统的可扩展性、可维护性和高性能。