# vprism MCP服务API文档

## 概述

vprism MCP (Model Context Protocol) 服务提供了一个标准化的接口，使AI模型能够直接访问金融数据。该服务基于 [**fastmcp**](https://github.com/jlowin/fastmcp) 实现，支持多种传输模式。

**⚠️ 重要说明**: 本项目**必须使用** fastmcp (版本 ≥2.10.6)，禁止使用官方 python-mcp 包。

## 什么是MCP

MCP (Model Context Protocol) 是一个开放协议，用于标准化应用程序如何向LLM提供上下文。vprism MCP服务允许AI助手直接查询实时和历史金融数据。

## 安装和启动

### 独立运行MCP服务器

```bash
# 从源码运行
python -m mcp.server

# 指定配置
python -m mcp.server --config mcp_config.json
```

### 配置文件示例

#### JSON格式 (mcp_config.json)
```json
{
  "transport": "stdio",
  "tools": {
    "get_stock_data": {
      "enabled": true,
      "rate_limit": 100
    },
    "get_market_overview": {
      "enabled": true
    }
  },
  "providers": {
    "yahoo_finance": {
      "enabled": true,
      "rate_limit": 100
    },
    "akshare": {
      "enabled": true,
      "rate_limit": 50
    }
  }
}
```

#### YAML格式 (mcp_config.yaml)
```yaml
transport: stdio
tools:
  get_stock_data:
    enabled: true
    rate_limit: 100
  get_market_overview:
    enabled: true
providers:
  yahoo_finance:
    enabled: true
    rate_limit: 100
  akshare:
    enabled: true
    rate_limit: 50
```

## MCP工具接口

### get_stock_data - 获取股票数据

**功能**: 获取指定股票的历史价格数据

**输入参数:**
```typescript
interface GetStockDataInput {
  symbol: string;        // 股票代码，如 "AAPL"
  market?: string;       // 市场代码，默认 "US"
  timeframe?: string;    // 时间周期，默认 "1d"
  start_date?: string;   // 开始日期 (YYYY-MM-DD)
  end_date?: string;     // 结束日期 (YYYY-MM-DD)
  limit?: number;        // 数据条数限制，默认 100
}
```

**使用示例 (Claude Desktop):**
```
使用 vprism 获取苹果公司最近100天的日线数据
```

**返回数据格式:**
```json
{
  "symbol": "AAPL",
  "market": "US", 
  "timeframe": "1d",
  "count": 100,
  "data": [
    {
      "timestamp": "2024-07-15T00:00:00Z",
      "open": 223.96,
      "high": 225.50,
      "low": 221.52,
      "close": 224.72,
      "volume": 45678900
    }
  ],
  "provider": "yahoo_finance",
  "last_updated": "2024-07-21T10:30:00Z"
}
```

### get_market_overview - 获取市场概览

**功能**: 获取市场整体表现数据

**输入参数:**
```typescript
interface GetMarketOverviewInput {
  market: string;        // 市场代码，如 "US", "CN", "HK"
  indices?: string[];    // 指数列表，可选
  sectors?: string[];    // 板块列表，可选
}
```

**使用示例:**
```
获取美国股市整体概览，包括主要指数表现
```

**返回数据格式:**
```json
{
  "market": "US",
  "indices": {
    "SPY": {
      "price": 456.78,
      "change": 2.34,
      "change_percent": 0.51,
      "volume": 45678900
    },
    "QQQ": {
      "price": 387.65,
      "change": 1.23,
      "change_percent": 0.32,
      "volume": 34567800
    }
  },
  "timestamp": "2024-07-21T10:30:00Z"
}
```

### get_symbols_list - 获取股票代码列表

**功能**: 获取指定市场的可交易股票代码列表

**输入参数:**
```typescript
interface GetSymbolsListInput {
  market: string;        // 市场代码
  exchange?: string;     // 交易所代码，可选
  search?: string;       // 搜索关键词，可选
  limit?: number;        // 返回数量限制，默认 100
}
```

**使用示例:**
```
列出纳斯达克交易所的所有科技股票代码
```

### analyze_trend - 分析股票趋势

**功能**: 分析股票的技术指标和趋势

**输入参数:**
```typescript
interface AnalyzeTrendInput {
  symbol: string;
  market?: string;
  timeframe?: string;
  indicators?: string[];  // 技术指标列表
  period?: number;        // 分析周期，默认 20
}
```

**使用示例:**
```
分析特斯拉股票的最近趋势，包括RSI和移动平均线
```

**返回数据格式:**
```json
{
  "symbol": "TSLA",
  "analysis": {
    "rsi": 65.4,
    "moving_average_20": 245.67,
    "moving_average_50": 238.45,
    "trend": "bullish",
    "support_level": 240.0,
    "resistance_level": 250.0
  }
}
```

## Claude Desktop配置

### 配置文件位置
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### 配置示例

#### 使用stdio传输
```json
{
  "mcpServers": {
    "vprism-finance": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "cwd": "/path/to/vprism"
    }
  }
}
```

#### 使用HTTP传输
```json
{
  "mcpServers": {
    "vprism-finance": {
      "command": "python", 
      "args": ["-m", "mcp.server", "--transport", "http", "--port", "8080"],
      "cwd": "/path/to/vprism"
    }
  }
}
```

#### 使用配置文件
```json
{
  "mcpServers": {
    "vprism-finance": {
      "command": "python",
      "args": ["-m", "mcp.server", "--config", "/path/to/mcp_config.json"],
      "cwd": "/path/to/vprism"
    }
  }
}
```

## 使用示例

### 与Claude的对话示例

#### 示例1: 获取股票数据
```
用户: 帮我获取苹果公司最近一个月的股票数据
Claude: 我来为您获取苹果公司(AAPL)最近一个月的日线数据。
[调用 vprism MCP工具]
Claude: 已获取苹果公司最近30天的交易数据。数据显示：
- 最新收盘价: $224.72
- 本月涨跌幅: +5.4%  
- 最高价: $234.50 (7月10日)
- 最低价: $210.32 (7月1日)
- 平均成交量: 45.6M股/日
```

#### 示例2: 市场分析
```
用户: 分析一下美国股市今天的整体表现
Claude: 让我查看美国股市的整体表现。
[调用 vprism MCP工具]
Claude: 根据最新数据，美国股市今日表现如下：
- S&P 500指数上涨0.51%，收于4,567.8点
- 纳斯达克指数上涨0.32%，收于15,234.5点  
- 道琼斯指数下跌0.12%，收于34,567.8点
整体市场表现积极，科技股领涨。
```

#### 示例3: 技术分析
```
用户: 特斯拉股票的技术面怎么样？会涨还是会跌？
Claude: 让我分析一下特斯拉的技术指标。
[调用 vprism MCP工具]
Claude: 基于特斯拉股票的技术分析：
- RSI指标为65.4，接近超买区域，但仍有上升空间
- 股价位于20日均线($245.67)之上，短期趋势向上
- 50日均线($238.45)提供支撑，中期趋势良好
- 关键支撑位在$240，阻力位在$250
技术面显示短期看涨，但需关注阻力位突破情况。
```

## 传输模式

### stdio模式 (默认)
适用于本地桌面应用的标准输入输出通信。

启动命令:
```bash
python -m mcp.server --transport stdio
```

### HTTP模式
适用于网络服务的HTTP通信。

启动命令:
```bash
python -m mcp.server --transport http --host 0.0.0.0 --port 8080
```

### SSE模式  
适用于实时数据推送的服务器发送事件模式。

启动命令:
```bash
python -m mcp.server --transport sse --host 0.0.0.0 --port 8080
```

## 安全和认证

### 环境变量配置
```bash
export MCP_API_KEY=your_api_key_here
export MCP_RATE_LIMIT=1000
export MCP_LOG_LEVEL=INFO
```

### 安全配置示例
```json
{
  "security": {
    "api_key_required": true,
    "rate_limiting": {
      "requests_per_minute": 100,
      "requests_per_hour": 1000
    },
    "allowed_origins": ["localhost", "claude.ai"]
  }
}
```

## 调试和故障排除

### 启用详细日志
```bash
python -m mcp.server --log-level DEBUG
```

### 测试连接
```bash
# 测试MCP服务器响应
curl -X POST http://localhost:8080/mcp/tools \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_stock_data", "arguments": {"symbol": "AAPL"}}'
```

### 常见问题

1. **连接失败**: 检查Python环境和依赖是否正确安装
2. **权限错误**: 确认配置文件路径和权限设置
3.  **超时问题**: 调整数据提供商的超时设置
4. **数据不一致**: 验证提供商配置和数据源状态

## 高级配置

### 自定义提供商
```json
{
  "custom_providers": {
    "my_custom_provider": {
      "endpoint": "https://api.example.com/data",
      "headers": {"Authorization": "Bearer token"},
      "rate_limit": 50
    }
  }
}
```

### 缓存策略
```json
{
  "cache": {
    "enabled": true,
    "ttl": 3600,
    "memory_limit": 1000,
    "disk_cache": true
  }
}
```

## 性能优化

### 并发请求管理
- 合理设置rate limit避免触发限流
- 使用批量查询减少请求次数
- 启用缓存减少重复请求

### 数据压缩
```json
{
  "compression": {
    "enabled": true,
    "algorithm": "gzip",
    "level": 6
  }
}
```

## 监控和指标

### Prometheus指标
- `mcp_requests_total`: MCP请求总数
- `mcp_request_duration_seconds`: 请求处理时间
- `mcp_errors_total`: MCP错误总数
- `provider_latency_seconds`: 数据提供商延迟