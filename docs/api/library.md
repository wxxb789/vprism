# vprism API 文档 - Python库模式

## 概述

vprism Python库提供了简洁而强大的接口来获取金融数据，支持同步和异步操作，具有完整的类型提示和错误处理。

## 安装

```bash
pip install vprism
```

## 快速开始

### 基本用法

```python
import vprism

# 同步获取股票数据
data = vprism.get("AAPL", market="US", timeframe="1d", limit=100)
print(data.head())

# 异步获取股票数据
import asyncio

async def main():
    data = await vprism.get_async("GOOGL", market="US", timeframe="1d")
    print(data.head())

asyncio.run(main())
```

### 配置初始化

```python
import vprism

# 全局配置
vprism.configure({
    "cache": {
        "enabled": True,
        "ttl": 3600,
        "memory_size": 1000
    },
    "providers": {
        "yahoo_finance": {
            "enabled": True,
            "rate_limit": 100
        }
    }
})

# 客户端实例化
client = vprism.VPrismClient(config={...})
```

## API参考

### vprism.get() - 同步获取数据

```python
def get(
    symbol: str,
    market: str = "US",
    timeframe: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    provider: Optional[str] = None,
    **kwargs
) -> pd.DataFrame
```

**参数说明:**
- `symbol` (str): 股票代码，如 "AAPL", "TSLA"
- `market` (str): 市场代码，默认 "US"，支持 "CN", "HK" 等
- `timeframe` (str): 时间周期，支持 "1m", "5m", "15m", "30m", "1h", "1d", "1w", "1mo"
- `start_date` (str): 开始日期，格式 "YYYY-MM-DD"
- `end_date` (str): 结束日期，格式 "YYYY-MM-DD"
- `limit` (int): 返回数据条数限制，默认100
- `provider` (str): 指定数据提供商，可选 "yahoo", "akshare" 等

**返回:**
pandas.DataFrame，包含以下列：
- open: 开盘价
- high: 最高价
- low: 最低价
- close: 收盘价
- volume: 成交量
- timestamp: 时间戳

### vprism.get_async() - 异步获取数据

```python
async def get_async(
    symbol: str,
    market: str = "US",
    timeframe: str = "1d",
    **kwargs
) -> pd.DataFrame
```

参数与同步版本相同，返回协程对象。

### QueryBuilder - 构建器模式

```python
from vprism import QueryBuilder

# 创建查询构建器
query = QueryBuilder()
result = (query
    .asset("AAPL")
    .market("US")
    .timeframe("1d")
    .start_date("2024-01-01")
    .end_date("2024-12-31")
    .limit(252)
    .build())

data = vprism.execute(query)
```

### 批量数据获取

```python
import vprism

# 同步批量获取
symbols = ["AAPL", "GOOGL", "MSFT"]
data_dict = vprism.batch_get(symbols, market="US", timeframe="1d")

# 异步批量获取
async def batch_demo():
    symbols = ["NVDA", "AMD", "INTC"]
    data_dict = await vprism.batch_get_async(symbols, timeframe="1h")
    return data_dict
```

## 数据格式规范

### 返回数据结构

DataFrame包含标准OHLCV格式：

| 列名 | 类型 | 描述 |
|------|------|------|
| open | float64 | 开盘价 |
| high | float64 | 最高价 |
| low | float64 | 最低价 |
| close | float64 | 收盘价 |
| volume | int64 | 成交量 |
| timestamp | datetime64 | 时间戳 |

### 市场代码对照表

| 市场代码 | 描述 | 示例股票 |
|----------|------|----------|
| US | 美国市场 | AAPL, TSLA |
| CN | 中国市场 | 000001, 600000 |
| HK | 香港市场 | 00700, 00005 |
| IN | 印度市场 | RELIANCE, TCS |

## 错误处理

### 异常类型

```python
from vprism.exceptions import VPrismException

try:
    data = vprism.get("INVALID_SYMBOL")
except VPrismException as e:
    print(f"错误代码: {e.code}")
    print(f"错误消息: {e.message}")
    print(f"提供商: {e.provider}")
```

### 常见错误代码

| 错误代码 | 描述 | 解决方案 |
|----------|------|----------|
| SYMBOL_NOT_FOUND | 股票代码不存在 | 检查代码拼写 |
| PROVIDER_ERROR | 数据提供商错误 | 稍后重试或更换提供商 |
| RATE_LIMIT_EXCEEDED | 请求频率超限 | 降低请求频率 |
| NETWORK_ERROR | 网络连接错误 | 检查网络连接 |

## 高级配置

### 缓存配置

```python
config = {
    "cache": {
        "enabled": True,
        "memory_cache_size": 1000,  # 内存缓存条目数
        "ttl": 3600,  # 缓存过期时间(秒)
        "disk_cache_path": "./cache",  # 磁盘缓存路径
    }
}
```

### 提供商配置

```python
config = {
    "providers": {
        "yahoo_finance": {
            "enabled": True,
            "rate_limit": 100,  # 每分钟请求数限制
            "timeout": 30,  # 超时时间(秒)
            "retries": 3,  # 重试次数
        },
        "akshare": {
            "enabled": True,
            "rate_limit": 200,
            "timeout": 60,
        }
    }
}
```

### 日志配置

```python
import logging
import vprism

# 设置日志级别
vprism.configure({
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
})
```

## 使用示例

### 获取历史数据

```python
import vprism

# 获取苹果公司2024年全年日线数据
aapl_2024 = vprism.get(
    "AAPL",
    market="US",
    timeframe="1d",
    start_date="2024-01-01",
    end_date="2024-12-31"
)
print(f"数据条数: {len(aapl_2024)}")
print(aapl_2024.head())
```

### 获取分钟级数据

```python
# 获取特斯拉最近100条1分钟数据
tsla_minutes = vprism.get(
    "TSLA",
    market="US",
    timeframe="1m",
    limit=100
)
print(tsla_minutes.tail())
```

### 中国市场数据

```python
# 获取贵州茅台日线数据
kweichow = vprism.get(
    "600519",
    market="CN",
    timeframe="1d",
    limit=30
)
print(kweichow.head())
```

### 异步并发获取

```python
import asyncio
import vprism

async def concurrent_download():
    symbols = ["AAPL", "GOOGL", "MSFT", "AMZN"]
    tasks = [
        vprism.get_async(symbol, market="US", timeframe="1d", limit=50)
        for symbol in symbols
    ]
    results = await asyncio.gather(*tasks)
    return dict(zip(symbols, results))

# 运行异步任务
results = asyncio.run(concurrent_download())
for symbol, data in results.items():
    print(f"{symbol}: {len(data)} 条数据")
```

## 性能优化建议

### 批量操作
对于大量数据请求，建议使用批量操作：

```python
# 推荐 - 批量获取
symbols = ["AAPL", "GOOGL", "MSFT"]
data = vprism.batch_get(symbols, timeframe="1d")

# 不推荐 - 逐个获取
for symbol in symbols:
    data[symbol] = vprism.get(symbol, timeframe="1d")  # 效率低
```

### 缓存利用
- 合理设置缓存TTL，平衡数据新鲜度和性能
- 对于不频繁变化的数据使用较长的TTL
- 利用批量查询减少缓存miss

### 并发控制
- 使用异步API提高并发性能
- 控制并发数量避免提供商限流
- 实现请求队列管理