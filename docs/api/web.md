# vprism Web服务API文档

## 概述

vprism Web服务基于FastAPI构建，提供RESTful API接口，支持标准HTTP请求和WebSocket连接。

## 基础信息

- **Base URL**: `http://localhost:8000/api/v1`
- **文档地址**: `http://localhost:8000/docs` (Swagger UI)
- **备用文档**: `http://localhost:8000/redoc` (ReDoc)
- **OpenAPI规范**: `http://localhost:8000/openapi.json`

## 认证

Web服务支持两种认证方式：

### API Key认证
```bash
curl -H "X-API-Key: your_api_key" http://localhost:8000/api/v1/data/stock/AAPL
```

### JWT Token认证
```bash
curl -H "Authorization: Bearer your_jwt_token" http://localhost:8000/api/v1/data/stock/AAPL
```

## API端点

### 获取单只股票数据

```http
GET /api/v1/data/stock/{symbol}
```

**参数:**
- `symbol` (path): 股票代码，如 AAPL, TSLA
- `market` (query): 市场代码 (默认: US)
- `timeframe` (query): 时间周期 (默认: 1d)
- `start_date` (query): 开始日期 (YYYY-MM-DD)
- `end_date` (query): 结束日期 (YYYY-MM-DD)
- `limit` (query): 数据条数限制 (默认: 100)
- `provider` (query): 指定数据提供商

**示例请求:**
```bash
curl "http://localhost:8000/api/v1/data/stock/AAPL?market=US&timeframe=1d&limit=50"
```

**响应格式:**
```json
{
  "status": "success",
  "data": {
    "symbol": "AAPL",
    "market": "US",
    "timeframe": "1d",
    "count": 50,
    "data": [
      {
        "timestamp": "2024-01-02T00:00:00Z",
        "open": 185.9,
        "high": 188.2,
        "low": 183.8,
        "close": 187.1,
        "volume": 82460000
      }
    ],
    "provider": "yahoo_finance",
    "cached": false
  },
  "meta": {
    "request_id": "req_123456",
    "processing_time_ms": 245
  }
}
```

### POST方式获取股票数据

```http
POST /api/v1/data/stock
```

**请求体:**
```json
{
  "symbols": ["AAPL", "GOOGL", "MSFT"],
  "market": "US",
  "timeframe": "1d",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "provider": "yahoo_finance"
}
```

### 获取市场数据

```http
GET /api/v1/data/market
```

**参数:**
- `market` (query): 市场代码
- `type` (query): 市场数据类型 (indices, sectors, etc.)

**示例:**
```bash
curl "http://localhost:8000/api/v1/data/market?market=US&type=indices"
```

### 批量数据查询

```http
POST /api/v1/data/batch
```

**请求体:**
```json
{
  "queries": [
    {
      "symbol": "AAPL",
      "market": "US",
      "timeframe": "1d",
      "limit": 100
    },
    {
      "symbol": "GOOGL", 
      "market": "US",
      "timeframe": "1h",
      "limit": 50
    }
  ],
  "parallel": true,
  "cache_ttl": 3600
}
```

### 获取股票代码列表

```http
GET /api/v1/data/symbols
```

**参数:**
- `market` (query): 市场代码 (默认: US)
- `exchange` (query): 交易所代码
- `search` (query): 搜索关键词

**示例:**
```bash
curl "http://localhost:8000/api/v1/data/symbols?market=US&search=Apple"
```

## 健康检查端点

### 基础健康检查

```http
GET /api/v1/health
```

**响应:**
```json
{
  "status": "healthy",
  "timestamp": "2024-07-21T10:30:00Z",
  "version": "0.1.0",
  "uptime_seconds": 3600
}
```

### Kubernetes就绪检查

```http
GET /api/v1/health/ready
```

### Kubernetes存活检查

```http
GET /api/v1/health/live
```

### 提供商状态检查

```http
GET /api/v1/health/providers
```

**响应:**
```json
{
  "providers": {
    "yahoo_finance": {
      "status": "healthy",
      "response_time_ms": 120,
      "last_check": "2024-07-21T10:29:45Z",
      "success_rate": 0.98
    },
    "akshare": {
      "status": "healthy", 
      "response_time_ms": 85,
      "last_check": "2024-07-21T10:29:50Z",
      "success_rate": 0.95
    }
  }
}
```

### 缓存状态检查

```http
GET /api/v1/health/cache
```

## 错误处理

### 错误响应格式

```json
{
  "status": "error",
  "error": {
    "code": "SYMBOL_NOT_FOUND",
    "message": "Symbol TSLAA not found",
    "details": {
      "symbol": "TSLAA",
      "provider": "yahoo_finance"
    }
  },
  "meta": {
    "request_id": "req_789012",
    "timestamp": "2024-07-21T10:30:00Z"
  }
}
```

### 错误代码对照表

| 代码 | HTTP状态 | 描述 |
|------|----------|------|
| SYMBOL_NOT_FOUND | 404 | 股票代码不存在 |
| PROVIDER_ERROR | 503 | 数据提供商错误 |
| RATE_LIMIT_EXCEEDED | 429 | 请求频率超限 |
| INVALID_PARAMETER | 400 | 参数错误 |
| UNAUTHORIZED | 401 | 认证失败 |
| INTERNAL_ERROR | 500 | 服务器内部错误 |

## 分页和过滤

### 分页参数

- `page` (query): 页码 (默认: 1)
- `page_size` (query): 每页条数 (默认: 100, 最大: 1000)

### 排序参数

- `sort_by` (query): 排序字段 (timestamp, volume, close)
- `sort_order` (query): 排序方向 (asc, desc)

### 过滤参数

- `start_date` (query): 开始日期过滤
- `end_date` (query): 结束日期过滤
- `min_volume` (query): 最小成交量过滤

## WebSocket接口

### 实时数据订阅

```http
GET /ws/realtime/{symbol}
```

**示例JavaScript客户端:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/realtime/AAPL');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('实时价格:', data.price);
};

ws.onerror = function(error) {
    console.error('WebSocket错误:', error);
};
```

## Python客户端示例

### 使用 requests库

```python
import requests

base_url = "http://localhost:8000/api/v1"

# 获取股票数据
response = requests.get(
    f"{base_url}/data/stock/AAPL",
    params={
        "market": "US",
        "timeframe": "1d",
        "limit": 50
    }
)
data = response.json()
print(f"数据条数: {data['data']['count']}")
```

### 批量查询

```python
import requests
import json

base_url = "http://localhost:8000/api/v1"

# 批量查询
payload = {
    "symbols": ["AAPL", "GOOGL", "MSFT"],
    "market": "US",
    "timeframe": "1d",
    "limit": 10
}

response = requests.post(f"{base_url}/data/batch", json=payload)
result = response.json()

for symbol, data in result['data'].items():
    print(f"{symbol}: {len(data)} 条数据")
```

## 速率限制

Web服务实现了以下速率限制：
- 匿名用户: 100请求/分钟
- 认证用户: 1000请求/分钟
- 批量请求: 10请求/分钟

## 监控指标

### Prometheus指标端点

```http
GET /metrics
```

### 关键指标

- `http_requests_total`: HTTP请求总数
- `http_request_duration_seconds`: 请求延迟
- `data_provider_errors_total`: 数据提供商错误总数
- `cache_hit_ratio`: 缓存命中率
- `active_connections`: 活跃连接数

## SDK和工具

### Python SDK

```python
from vprism_web_client import VPrismWebClient

client = VPrismWebClient(
    base_url="http://localhost:8000/api/v1",
    api_key="your_api_key"
)

# 获取数据
data = client.get_stock_data("AAPL", market="US", limit=100)
```

### JavaScript SDK

```javascript
const VPrismClient = require('vprism-web-client');

const client = new VPrismClient({
    baseURL: 'http://localhost:8000/api/v1',
    apiKey: 'your_api_key'
});

// 获取股票数据
const data = await client.getStockData('AAPL', {
    market: 'US',
    timeframe: '1d',
    limit: 100
});
```

## 部署和运维

### Docker部署

```bash
docker run -p 8000:8000 vprism/web-service:latest
```

### 环境变量配置

```bash
export VPRISM_WEB_PORT=8000
export VPRISM_WEB_WORKERS=4
export VPRISM_CACHE_TTL=3600
export VPRISM_LOG_LEVEL=INFO
```

### 健康监控脚本

```bash
#!/bin/bash
# health_check.sh

response=$(curl -s http://localhost:8000/api/v1/health)
status=$(echo $response | jq -r '.status')

if [ "$status" == "healthy" ]; then
    echo "服务健康运行"
    exit 0
else
    echo "服务异常"
    exit 1
fi
```