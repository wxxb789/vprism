# vprism 快速开始指南

## 5分钟快速上手

### 第1分钟：安装

#### 安装vprism库
```bash
pip install vprism
```

#### 验证安装
```python
import vprism
print("vprism版本:", vprism.__version__)
```

### 第2分钟：获取第一条数据

#### 获取苹果股票数据
```python
import vprism

# 获取苹果公司最近10天的数据
data = vprism.get("AAPL", market="US", timeframe="1d", limit=10)
print("成功获取数据! 数据形状:", data.shape)
print(data.head())
```

#### 获取中国股票数据
```python
# 获取贵州茅台的数据
data = vprism.get("600519", market="CN", timeframe="1d", limit=5)
print("贵州茅台最新数据:")
print(data.tail(1))
```

### 第3分钟：批量操作

#### 同时获取多只股票
```python
# 批量获取多只美股数据
symbols = ["AAPL", "GOOGL", "MSFT", "TSLA"]
all_data = vprism.batch_get(symbols, market="US", timeframe="1d", limit=30)

for symbol, data in all_data.items():
    latest_price = data.iloc[-1]['close']
    print(f"{symbol}: ${latest_price:.2f}")
```

#### 异步批量获取
```python
import asyncio

async def get_all_data():
    symbols = ["NVDA", "AMD", "INTC"]
    tasks = [vprism.get_async(s, market="US", timeframe="1d", limit=20) for s in symbols]
    results = await asyncio.gather(*tasks)
    return dict(zip(symbols, results))

# 运行异步任务
results = asyncio.run(get_all_data())
```

### 第4分钟：数据可视化

#### 简单图表
```python
import matplotlib.pyplot as plt

# 获取特斯拉数据，并绘制收盘价图
tsla_data = vprism.get("TSLA", market="US", timeframe="1d", limit=60)

plt.figure(figsize=(12, 6))
plt.plot(tsla_data.index, tsla_data['close'])
plt.title('Tesla Stock Price (Last 60 Days)')
plt.xlabel('Date')
plt.ylabel('Price ($)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

#### 多股票对比
```python
import pandas as pd

# 获取多只科技股数据
symbols = ["AAPL", "GOOGL", "MSFT", "AMZN"]
stock_data = {}

for symbol in symbols:
    data = vprism.get(symbol, market="US", timeframe="1d", limit=30)
    stock_data[symbol] = data['close']

# 创建对比DataFrame
comparison_df = pd.DataFrame(stock_data)
comparison_df.plot(figsize=(14, 8), title='Tech Stocks Comparison')
plt.show()
```

### 第5分钟：高级功能

#### 使用查询构建器
```python
# 使用构建器模式创建复杂查询
query = vprism.query() \
    .asset("AAPL") \
    .market("US") \
    .timeframe("1h") \
    .start_date("2024-07-01") \
    .end_date("2024-07-21") \
    .build()

hourly_data = vprism.execute(query)
print(f"获取了 {len(hourly_data)} 小时数据")
```

#### 数据质量保证
```python
# 检查数据质量
from vprism.core.quality import DataQualityValidator

# 验证数据完整性
validator = DataQualityValidator()
quality_score = validator.validate(data)
print(f"数据质量评分: {quality_score:.2f}/100")
```

## 实战项目示例

### 示例1：个人投资组合追踪器

```python
import vprism
import pandas as pd
from datetime import datetime

class PortfolioTracker:
    def __init__(self, holdings):
        self.holdings = holdings  # {'AAPL': 100, 'GOOGL': 50}
        self.market = "US"
    
    def get_current_values(self):
        values = {}
        total_value = 0
        
        for symbol, shares in self.holdings.items():
            data = vprism.get(symbol, market=self.market, timeframe="1d", limit=1)
            current_price = data.iloc[0]['close']
            value = shares * current_price
            values[symbol] = {
                'price': current_price,
                'shares': shares,
                'value': value
            }
            total_value += value
        
        return values, total_value
    
    def generate_report(self):
        values, total = self.get_current_values()
        print(f"投资组合报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 50)
        for symbol, info in values.items():
            print(f"{symbol}: {info['shares']}股 × ${info['price']:.2f} = ${info['value']:,.2f}")
        print("-" * 50)
        print(f"总资产价值: ${total:,.2f}")

# 使用示例
portfolio = PortfolioTracker({'AAPL': 100, 'GOOGL': 50, 'MSFT': 75})
portfolio.generate_report()
```

### 示例2：股票市场监控器

```python
import asyncio
import time
from datetime import datetime

class MarketMonitor:
    def __init__(self, watchlist):
        self.watchlist = watchlist
        self.previous_prices = {}
    
    async def monitor_prices(self, interval=60):
        while True:
            current_data = await vprism.batch_get_async(
                self.watchlist, market="US", timeframe="1d", limit=1
            )
            
            alerts = []
            for symbol, data in current_data.items():
                current_price = data.iloc[0]['close']
                prev_price = self.previous_prices.get(symbol, current_price)
                change = ((current_price - prev_price) / prev_price) * 100
                
                # 价格变动超过5%时发送警报
                if abs(change) >= 5:
                    alerts.append(f"{symbol}: ${current_price:.2f} ({change:+.1f}%)")
                
                self.previous_prices[symbol] = current_price
            
            if alerts:
                print(f"🚨 {datetime.now().strftime('%H:%M:%S')} 价格警报:")
                for alert in alerts:
                    print(f"  {alert}")
            else:
                print(f"✅ {datetime.now().strftime('%H:%M:%S')} 监控中...")
            
            await asyncio.sleep(interval)

# 使用示例
monitor = MarketMonitor(['AAPL', 'GOOGL', 'TSLA', 'NVDA'])
# asyncio.run(monitor.monitor_prices())
```

### 示例3：技术指标计算器

```python
import pandas as pd
import numpy as np

class TechnicalIndicators:
    @staticmethod
    def calculate_sma(data, window):
        return data['close'].rolling(window=window).mean()
    
    @staticmethod
    def calculate_rsi(data, window=14):
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def calculate_bollinger_bands(data, window=20, num_std=2):
        sma = TechnicalIndicators.calculate_sma(data, window)
        std = data['close'].rolling(window=window).std()
        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)
        return upper_band, sma, lower_band

# 使用示例
aapl_data = vprism.get("AAPL", market="US", timeframe="1d", limit=100)
indicators = TechnicalIndicators()

# 计算技术指标
aapl_data['SMA20'] = indicators.calculate_sma(aapl_data, 20)
aapl_data['RSI14'] = indicators.calculate_rsi(aapl_data, 14)
aapl_data['Upper'], aapl_data['Middle'], aapl_data['Lower'] = indicators.calculate_bollinger_bands(aapl_data)

print("AAPL 技术指标:")
print(aapl_data[['close', 'SMA20', 'RSI14', 'Upper', 'Lower']].tail())
```

## 配置优化

### 开发环境配置
```python
# 开发环境优化配置
vprism.configure({
    "cache": {
        "enabled": True,
        "ttl": 300,  # 开发环境缓存时间短
        "memory_size": 100
    },
    "providers": {
        "yahoo_finance": {
            "enabled": True,
            "rate_limit": 1000,  # 开发环境放宽限制
            "timeout": 60
        }
    },
    "logging": {
        "level": "DEBUG",  # 详细日志
        "file": None  # 控制台输出
    }
})
```

### 生产环境配置
```python
# 生产环境优化配置
vprism.configure({
    "cache": {
        "enabled": True,
        "ttl": 3600,  # 生产环境缓存时间长
        "memory_size": 10000,
        "disk_cache": True
    },
    "providers": {
        "yahoo_finance": {
            "enabled": True,
            "rate_limit": 100,  # 遵守API限制
            "timeout": 30,
            "retries": 3
        }
    },
    "logging": {
        "level": "INFO",
        "file": "/var/log/vprism/app.log",
        "format": "json"
    }
})
```

## 下一步学习

1. **深入API文档**: 查看完整的[库模式API文档](api/library.md)
2. **Web服务部署**: 学习如何部署[vprism Web服务](deployment/web.md)
3. **MCP集成**: 了解如何与AI助手集成[MCP服务](api/mcp.md)
4. **高级功能**: 探索数据质量保证、性能优化等高级功能

## 获取帮助

- 📖 [完整文档](README.md)
- 🐛 [报告问题](https://github.com/your-repo/issues)
- 💬 [社区讨论](https://github.com/your-repo/discussions)
- 📧 [邮件支持](mailto:support@vprism.com)