# vprism FAQ - 常见问题解答

## 基础概念

### Q1: vprism是什么？和akshare有什么区别？

**vprism**是一个现代化的金融数据获取库，提供统一的API接口，底层可以接入多个数据源包括akshare、Yahoo Finance等。主要区别：

| 特性 | vprism | akshare |
|------|--------|---------|
| API设计 | 统一、现代化 | 1000+个分散函数 |
| 缓存机制 | 内置多层缓存 | 无缓存 |
| 错误处理 | 标准化异常 | 各种错误类型 |
| 并发支持 | 异步批量操作 | 同步操作 |
| 数据质量 | 自动验证清洗 | 原始数据 |

### Q2: vprism支持哪些市场和数据源？

**支持的市场**：
- 🇺🇸 美国市场 (NYSE, NASDAQ)
- 🇨🇳 中国市场 (沪深股市、港股)
- 🇭🇰 香港市场 (HKEX)
- 🇮🇳 印度市场 (NSE, BSE)
- 🇯🇵 日本市场 (TSE)

**主要数据源**：
- Yahoo Finance
- Akshare (新浪财经、东方财富等)
- Alpha Vantage (需API密钥)
- Quandl

### Q3: 为什么有时候获取的数据和实际价格有差异？

数据延迟可能来自：
1. 数据源延迟：Yahoo Finance通常延迟15-20分钟
2. 缓存延迟：默认缓存1小时，可配置
3. 非交易时间：获取的是最后交易价格
4. 数据源差异：不同提供商数据可能有微小差异

## 使用技巧

### Q4: 如何获取实时数据？

```python
# 获取尽可能实时的数据
import vprism

# 方法1：减少缓存时间
vprism.configure({
    "cache": {"ttl": 60}  # 1分钟缓存
})

# 方法2：强制刷新缓存
data = vprism.get("AAPL", market="US", refresh=True)

# 方法3：使用分钟级数据获取最新价
latest = vprism.get("AAPL", timeframe="1m", limit=1)
print("最新价格:", latest.iloc[0]['close'])
```

### Q5: 如何获取历史分红数据？

vprism主要提供价格数据，分红数据可通过：

```python
# 获取包含复权价格的历史数据
# 前复权价格会自动调整分红影响
data = vprism.get("AAPL", market="US", timeframe="1d", adjusted=True)

# 如需详细分红信息,建议使用yfinance库作为补充
import yfinance as yf
stock = yf.Ticker("AAPL")
dividends = stock.dividends
print(dividends.tail())
```

### Q6: 如何获取期权数据？

当前版本主要支持股票数据，期权数据可通过扩展实现：

```python
# 使用底层提供商获取期权链
from vprism.infrastructure.providers import YahooProvider

provider = YahooProvider()
options_chain = provider.get_options_chain("AAPL")
print("期权链数据:", options_chain)
```

## 数据处理

### Q7: 如何处理缺失的交易数据？

```python
import pandas as pd

# 获取数据
data = vprism.get("AAPL", timeframe="1d", limit=100)

# 检查缺失值
print("缺失值统计:", data.isnull().sum())

# 处理方法1：前向填充
data_filled = data.fillna(method='ffill')

# 处理方法2：线性插值  
data_interp = data.interpolate(method='linear')

# 处理方法3：标记缺失日期
full_range = pd.date_range(start=data.index.min(), end=data.index.max(), freq='D')
data = data.reindex(full_range)
print("完整日期范围:", len(data), "天")
```

### Q8: 如何获取复权价格？

```python
# vprism默认返回前复权价格
data = vprism.get("AAPL", timeframe="1d", limit=1000)
print("价格已自动复权处理")

# 如需原始价格，可指定参数 (部分提供商支持)
raw_data = vprism.get("AAPL", timeframe="1d", adjusted=False)
```

### Q9: 如何处理美股盘前盘后数据？

```python
# 获取更细粒度的分钟数据来包含盘前盘后
intraday_data = vprism.get(
    "AAPL", 
    timeframe="1m", 
    start_date="2024-01-15", 
    end_date="2024-01-15"
)

# 盘前数据 (9:30AM之前)
pre_market = intraday_data[intraday_data.index.hour < 9]

# 盘后数据 (4:00PM之后)
after_hours = intraday_data[intraday_data.index.hour >= 16]
```

## 中国市场特殊处理

### Q10: A股股票代码格式是怎样的？

```python
# 沪市主板 (600开头)
vprism.get("600519", market="CN")  # 贵州茅台

# 深市主板 (000开头)
vprism.get("000001", market="CN")  # 平安银行

# 中小板 (002开头)
vprism.get("002415", market="CN")  # 海康威视

# 创业板 (300开头)
vprism.get("300750", market="CN")  # 宁德时代

# 科创板 (688开头)
vprism.get("688981", market="CN")  # 中芯国际
```

### Q11: 如何处理A股停牌数据？

```python
# 停牌期间的数据处理
data = vprism.get("600519", market="CN", timeframe="1d", limit=100)

# 识别停牌日 (成交量为0)
trading_days = data[data['volume'] > 0]
halted_days = data[data['volume'] == 0]

print(f"交易日: {len(trading_days)}天")
print(f"停牌日: {len(halted_days)}天")

# 停牌日前后价格对比
if len(halted_days) > 0:
    last_trading_price = data.loc[trading_days.index[-1], 'close']
    first_after_halt = data.loc[trading_days.index[0], 'close'] if len(trading_days) > 0 else None
    print(f"停牌前价格: {last_trading_price}")
    if first_after_halt:
        print(f"复牌后价格: {first_after_halt}")
```

### Q12: 如何处理港股通股票？

```python
# 港股通股票列表
hk_stocks = [
    "00700",  # 腾讯控股
    "03690",  # 美团-W
    "09988",  # 阿里巴巴-SW
]

# 获取港股数据
for symbol in hk_stocks:
    try:
        data = vprism.get(symbol, market="HK", timeframe="1d", limit=30)
        print(f"{symbol}: 最新价 HK${data.iloc[-1]['close']:.2f}")
    except Exception as e:
        print(f"获取{symbol}失败: {e}")
```

## 性能优化

### Q13: 如何优化大批量数据获取？

```python
import asyncio
import time

# 方法1：异步批量获取
async def batch_download_async(symbols):
    tasks = [vprism.get_async(s, timeframe="1d", limit=252) for s in symbols]
    return await asyncio.gather(*tasks)

# 方法2：分批次处理避免API限制
symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"] * 100  # 500只股票
batch_size = 5
results = {}

for i in range(0, len(symbols), batch_size):
    batch = symbols[i:i+batch_size]
    batch_results = vprism.batch_get(batch, timeframe="1d", limit=252)
    results.update(batch_results)
    time.sleep(1)  # API限制保护

print(f"完成下载 {len(results)} 只股票数据")
```

### Q14: 如何减少内存占用？

```python
# 策略1：只获取需要的列
# vprism默认返回OHLCV完整数据

# 策略2：分批处理大数据集
import gc

symbols = ["AAPL", "GOOGL", "MSFT", ...]  # 大量股票
chunk_size = 50

for i in range(0, len(symbols), chunk_size):
    chunk_symbols = symbols[i:i+chunk_size]
    chunk_data = vprism.batch_get(chunk_symbols, timeframe="1d")
    
    # 处理这批数据
    for symbol, data in chunk_data.items():
        # 内存中的数据处理
        processed = calculate_indicators(data)
        save_to_disk(symbol, processed)
    
    del chunk_data  # 手动释放内存
    gc.collect()
```

## 错误处理

### Q15: 遇到"Provider Error"如何处理？

```python
from vprism.exceptions import ProviderError, NetworkError

def robust_data_fetch(symbol, max_retries=3):
    for attempt in range(max_retries):
        try:
            return vprism.get(symbol, market="US", timeframe="1d")
        except ProviderError as e:
            print(f"提供商错误 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
            else:
                # 降级到备用提供商
                return vprism.get(symbol, market="US", provider="akshare")
        except NetworkError as e:
            print(f"网络错误: {e}")
            raise
```

### Q16: 如何处理数据中断的问题？

```python
# 检测数据中断
import pandas as pd

def detect_data_gaps(data, expected_freq='D'):
    """检测数据中断"""
    expected_range = pd.date_range(
        start=data.index.min(), 
        end=data.index.max(), 
        freq=expected_freq
    )
    missing_dates = expected_range.difference(data.index)
    return missing_dates

# 使用示例
data = vprism.get("AAPL", timeframe="1d", limit=100)
gaps = detect_data_gaps(data)
print(f"数据中断日期: {len(gaps)}天")
print("缺失日期前5个:", gaps[:5])
```

## 部署相关

### Q17: 如何在生产环境中部署vprism Web服务？

```bash
# Docker部署
docker run -d \
  --name vprism-prod \
  -p 8000:8000 \
  -e VPRISM_WEB_WORKERS=4 \
  -e VPRISM_REDIS_URL=redis://redis:6379/0 \
  -e VPRISM_LOG_LEVEL=INFO \
  vprism:latest web

# Kubernetes部署
kubectl apply -f k8s/vprism-deployment.yaml
kubectl apply -f k8s/vprism-service.yaml
kubectl apply -f k8s/vprism-ingress.yaml
```

### Q18: 如何配置HTTPS和SSL证书？

```nginx
# Nginx配置示例
server {
    listen 443 ssl http2;
    server_name finance-api.your-domain.com;

    ssl_certificate /etc/ssl/certs/vprism.crt;
    ssl_certificate_key /etc/ssl/private/vprism.key;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
}

# Let's Encrypt证书自动续期
certbot --nginx -d finance-api.your-domain.com
```

## 高级功能

### Q19: 如何获取期权数据？

```python
# 期权数据扩展 (需要额外配置)
from vprism.extensions.options import OptionsData

options = OptionsData()
chain = options.get_chain("AAPL", expiration="2024-08-16")
print(f"AAPL期权链: {len(chain)}个合约")

# 获取隐含波动率
iv_data = options.get_implied_volatility("AAPL", strike=220, expiration="2024-08-16")
print(f"隐含波动率: {iv_data:.2f}%")
```

### Q20: 如何获取外汇数据？

```python
# 外汇数据获取
pairs = ["USDJPY=X", "EURUSD=X", "GBPUSD=X"]
for pair in pairs:
    forex_data = vprism.get(pair, market="FX", timeframe="1d", limit=30)
    print(f"{pair}: 最新汇率 {forex_data.iloc[-1]['close']:.4f}")
```

## 版本更新和兼容性

### Q21: 版本升级后API变化如何处理？

```python
# 版本检查
import vprism
if hasattr(vprism, 'get_version'):
    version = vprism.get_version()
    major = version.split('.')[0]
    print(f"当前主版本: v{major}")

# 兼容性处理
try:
    # 新API
    data = vprism.get("AAPL")
except AttributeError:
    # 旧API兼容
    data = vprism.stock.get("AAPL")
```

### Q22: 如何回滚到旧版本？

```bash
# 查看已安装版本
pip list | grep vprism

# 回滚到特定版本
pip install vprism==0.1.0

# 使用requirements.txt锁定版本
echo "vprism==0.1.0" > requirements.txt
pip install -r requirements.txt
```

## 性能和扩展性

### Q23: vprism能处理多少只股票？

vprism设计支持大规模数据处理：
- 单机模式：建议同时处理不超过1000只股票
- Web服务模式：可水平扩展到数万只股票
- 批处理模式：支持分批处理任意数量股票

### Q24: 内存使用量大概是多少？

内存使用估算：
- 单只股票1年日线数据：约5KB
- 100只股票1年数据：约500KB
- 1000只股票1年数据：约5MB
- 包含缓存时：约原始数据的2-3倍

通过以上FAQ，您可以快速解决使用vprism过程中遇到的各种问题。如果仍有疑问，建议查阅完整文档或在社区中提问。