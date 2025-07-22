# vprism Web 服务

vprism 的 FastAPI Web 服务实现，提供 RESTful API 接口访问金融数据。

## 快速开始

### 1. 启动服务

```bash
# 使用 Python 启动
python main.py web

# 或使用 uvicorn 直接启动
uvicorn src.vprism.web.app:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 访问文档

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 3. 基本使用

#### 获取股票数据

```bash
# GET 方式
curl "http://localhost:8000/api/v1/data/stock/AAPL?market=us&timeframe=1d&limit=5"

# POST 方式
curl -X POST "http://localhost:8000/api/v1/data/stock" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "market": "us",
    "timeframe": "1d",
    "limit": 5
  }'
```

#### 批量查询

```bash
curl -X POST "http://localhost:8000/api/v1/data/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [
      {"symbol": "AAPL", "market": "us", "timeframe": "1d", "limit": 2},
      {"symbol": "GOOGL", "market": "us", "timeframe": "1d", "limit": 2}
    ],
    "async_processing": false
  }'
```

## API 端点

### 数据端点

- `GET /api/v1/data/stock/{symbol}` - 获取单只股票数据
- `POST /api/v1/data/stock` - 获取股票数据（POST方式）
- `POST /api/v1/data/market` - 获取市场数据
- `POST /api/v1/data/batch` - 批量数据查询
- `GET /api/v1/data/symbols` - 获取股票代码列表

### 健康检查端点

- `GET /api/v1/health` - 基础健康检查
- `GET /api/v1/health/ready` - Kubernetes就绪检查
- `GET /api/v1/health/live` - Kubernetes存活检查
- `GET /api/v1/health/providers` - 提供商状态检查
- `GET /api/v1/health/cache` - 缓存状态检查
- `GET /api/v1/metrics` - 系统指标

## Docker 部署

### 使用 Docker Compose

```bash
# 构建和启动
docker-compose up --build

# 后台运行
docker-compose up -d

# 查看日志
docker-compose logs -f vprism-web
```

### 使用 Docker

```bash
# 构建镜像
docker build -t vprism-web .

# 运行容器
docker run -p 8000:8000 vprism-web
```

## 环境变量

| 变量名 | 默认值 | 描述 |
|--------|--------|------|
| `VPRISM_HOST` | 0.0.0.0 | 监听地址 |
| `VPRISM_PORT` | 8000 | 监听端口 |
| `VPRISM_RELOAD` | false | 是否启用热重载 |

## 响应格式

所有 API 响应都使用统一格式：

```json
{
  "success": true,
  "data": { ... },
  "message": "成功获取数据",
  "timestamp": "2024-07-21T01:09:32.692983",
  "request_id": "uuid-string"
}
```

错误响应格式：

```json
{
  "success": false,
  "error": "ValidationError",
  "message": "请求参数验证失败",
  "details": { "validation_errors": { ... } },
  "timestamp": "2024-07-21T01:09:32.692983",
  "request_id": "uuid-string"
}
```

## 示例代码

### Python 使用示例

```python
import requests

# 获取股票数据
response = requests.get("http://localhost:8000/api/v1/data/stock/AAPL")
data = response.json()
print(f"AAPL 最新价格: {data['data']['data'][0]['close']}")

# 批量查询
payload = {
    "queries": [
        {"symbol": "AAPL", "market": "us", "timeframe": "1d"},
        {"symbol": "GOOGL", "market": "us", "timeframe": "1d"}
    ]
}
response = requests.post("http://localhost:8000/api/v1/data/batch", json=payload)
batch_data = response.json()
```

### JavaScript 使用示例

```javascript
// 获取股票数据
fetch('http://localhost:8000/api/v1/data/stock/AAPL?market=us&timeframe=1d')
  .then(response => response.json())
  .then(data => console.log(data));

// 批量查询
fetch('http://localhost:8000/api/v1/data/batch', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    queries: [
      {symbol: 'AAPL', market: 'us', timeframe: '1d'},
      {symbol: 'GOOGL', market: 'us', timeframe: '1d'}
    ]
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

## 性能优化

- 支持 Gzip 压缩
- 支持缓存
- 支持批量查询优化
- 支持异步处理

## 监控和日志

- 结构化日志记录
- Prometheus 指标收集
- 健康检查和就绪检查
- 错误追踪和报告

## 扩展性

- 水平扩展支持
- 负载均衡
- 数据库连接池
- 缓存集群支持