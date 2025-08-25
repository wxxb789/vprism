# vprism 故障排除指南和FAQ

## 常见问题速查表

### 🚀 安装问题

#### Q1: pip安装失败怎么办？
```bash
# 问题现象
ERROR: Could not build wheels for vprism

# 解决方案
pip install --upgrade pip setuptools wheel
pip install vprism --no-cache-dir

# 如仍有问题，使用conda
conda install -c conda-forge vprism
```

#### Q2: 依赖冲突如何解决？
```bash
# 创建虚拟环境
python -m venv vprism-env
source vprism-env/bin/activate  # Linux/Mac
# vprism-env\Scripts\activate   # Windows

pip install vprism
```

### 📊 数据获取问题

#### Q3: 股票代码找不到怎么办？
```python
# 问题代码
vprism.get("INVALID_CODE")  # 抛出 SYMBOL_NOT_FOUND

# 解决方案
# 1. 检查股票代码格式
symbols = vprism.get_symbols_list(market="US", search="Apple")
print("苹果公司代码:", symbols[0] if symbols else "未找到")

# 2. 确认市场代码
market_codes = ["US", "CN", "HK", "IN", "JP"]
print("支持的市场:", market_codes)
```

#### Q4: 中国市场数据获取失败？
```python
# 正确获取中国股票
# 沪市股票 (600开头)
vprism.get("600519", market="CN", timeframe="1d")  # 贵州茅台

# 深市股票 (000开头)  
vprism.get("000001", market="CN", timeframe="1d")  # 平安银行

# 创业板 (300开头)
vprism.get("300750", market="CN", timeframe="1d")  # 宁德时代
```

#### Q5: 数据返回为空或None？
```python
# 检查网络连接
import requests
try:
    response = requests.get("https://finance.yahoo.com", timeout=5)
    print("网络连接正常" if response.status_code == 200 else "网络问题")
except requests.exceptions.RequestException as e:
    print(f"网络错误: {e}")

# 检查提供商状态
vprism.check_provider_status("yahoo_finance")
```

### ⚡ 性能问题

#### Q6: 程序运行很慢怎么办？
```python
# 启用缓存优化性能
vprism.configure({
    "cache": {
        "enabled": True,
        "ttl": 3600,
        "memory_size": 5000
    }
})

# 使用批量操作替代循环
# ❌ 不推荐
for symbol in symbols:
    data = vprism.get(symbol)  # 效率低

# ✅ 推荐
batch_data = vprism.batch_get(symbols)  # 效率高
```

#### Q7: 内存占用过高？
```python
# 限制内存使用
vprism.configure({
    "cache": {
        "memory_size": 1000,  # 减少内存缓存
        "disk_cache": True    # 启用磁盘缓存
    }
})

# 及时清理缓存
import gc
gc.collect()  # 手动触发垃圾回收
```

### 🔐 认证和限流问题

#### Q8: 达到API限制怎么办？
```python
# 错误信息
RATE_LIMIT_EXCEEDED: Too many requests to yahoo_finance

# 解决方案
vprism.configure({
    "providers": {
        "yahoo_finance": {
            "rate_limit": 50,  # 降低请求频率
            "timeout": 30,
            "retries": 0
        }
    }
})

# 使用多个提供商轮换
providers = ["yahoo_finance", "akshare", "alpha_vantage"]
vprism.set_fallback_providers(providers)
```

#### Q9: API密钥配置错误？
```python
# 正确配置Alpha Vantage的API密钥
vprism.configure({
    "providers": {
        "alpha_vantage": {
            "enabled": True,
            "api_key": "YOUR_ALPHA_VANTAGE_API_KEY",
            "rate_limit": 5  # Alpha Vantage免费版限制
        }
    }
})

# 环境变量方式配置
export ALPHA_VANTAGE_API_KEY="your-key-here"
```

### 🐛 错误代码详解

#### 网络连接错误
```python
from vprism.exceptions import VPrismError

try:
    data = vprism.get("AAPL")
except VPrismError as e:
    if e.code == "NETWORK_ERROR":
        print("检查网络连接或尝试稍后重试")
    elif e.code == "TIMEOUT":
        print("请求超时，尝试增加超时时间")
        vprism.configure({"providers": {"timeout": 60}})
    elif e.code == "PROVIDER_DOWN":
        print("数据提供商暂时不可用")
        print("备用提供商:", e.fallback_providers)
```

#### 数据质量问题
```python
# 数据缺失值处理
import pandas as pd

data = vprism.get("AAPL", timeframe="1d", limit=100)
print("原始数据形状:", data.shape)
print("缺失值统计:", data.isnull().sum())

# 自动填充缺失值
data = data.fillna(method='ffill')  # 向前填充
print("处理后数据形状:", data.shape)
```

### 🐳 Docker部署问题

#### Q10: Docker容器启动失败
```bash
# 检查Docker日志
docker logs vprism-container

# 常见错误解决
docker run -d \
  --name vprism-web \
  -p 8000:8000 \
  -e VPRISM_WEB_PORT=8000 \
  -v $(pwd)/config:/app/config \
  vprism:latest web

# 端口冲突解决
netstat -tulpn | grep 8000  # 查看占用端口的进程
```

#### Q11: Docker内存不足
```bash
# Docker内存设置
docker run -d \
  --name vprism-web \
  -p 8000:8000 \
  --memory=1g \
  --memory-swap=2g \
  vprism:latest web

# Docker Compose内存限制
version: '3.8'
services:
  vprism-web:
    image: vprism:latest
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
```

### 🔧 配置问题

#### Q12: 配置文件不生效
```python
# 检查配置文件路径
import os
print("配置文件搜索路径:")
for path in vprism.get_config_paths():
    print(f"- {path}")

# 强制使用特定配置文件
vprism.load_config("/absolute/path/to/config.json")

# 验证配置是否生效
config = vprism.get_current_config()
print("当前缓存配置:", config.get('cache', {}))
```

#### Q13: 日志配置问题
```python
# 设置详细日志
import logging
vprism.configure({
    "logging": {
        "level": "DEBUG",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": None  # 输出到控制台
    }
})

# 查看日志文件位置
import os
log_file = os.path.expanduser("~/.vprism/vprism.log")
if os.path.exists(log_file):
    print(f"日志文件位置: {log_file}")
    os.system(f"tail -20 {log_file}")
```

### 📈 性能调优指南

#### 内存优化清单
```python
# 1. 限制缓存大小
vprism.configure({
    "cache": {
        "memory_size": 1000,  # 最多缓存1000条记录
        "ttl": 1800,         # 30分钟过期
        "disk_cache": True   # 溢出到磁盘
    }
})

# 2. 分批处理大数据
symbols = ["AAPL", "GOOGL", "MSFT", ...]  # 大量股票
batch_size = 10
results = {}

for i in range(0, len(symbols), batch_size):
    batch = symbols[i:i+batch_size]
    batch_results = vprism.batch_get(batch)
    results.update(batch_results)
    time.sleep(1)  # 避免API限制
```

#### 查询优化技巧
```python
# 优化查询范围
# ❌ 低效：获取整年数据后过滤
data = vprism.get("AAPL", timeframe="1d")
filtered = data[data.index > "2024-01-01"]

# ✅ 高效：直接指定日期范围
data = vprism.get(
    "AAPL", 
    timeframe="1d",
    start_date="2024-01-01",
    end_date="2024-12-31"
)

# 使用合适的时间周期
# ❌ 获取1分钟数据做长期分析
data = vprism.get("AAPL", timeframe="1m", limit=10000)

# ✅ 使用日线数据做趋势分析  
data = vprism.get("AAPL", timeframe="1d", limit=252)  # 一年数据
```

### 🚨 紧急情况处理

#### 数据提供商故障应急方案
```python
# 备份数据提供商配置
emergency_config = {
    "providers": {
        "yahoo_finance": {"enabled": True, "priority": 1},
        "akshare": {"enabled": True, "priority": 2},
        "alpha_vantage": {"enabled": True, "priority": 3}
    },
    "fallback_enabled": True,
    "max_fallback_attempts": 3
}

# 紧急模式启用
vprism.enable_emergency_mode(emergency_config)
```

#### 数据一致性检查
```python
from vprism.core.consistency import DataConsistencyValidator

validator = DataConsistencyValidator()

# 交叉验证数据
vprism_data = vprism.get("AAPL", timeframe="1d", limit=5)
akshare_data = vprism.get("AAPL", provider="akshare", timeframe="1d", limit=5)

# 检查一致性
report = validator.compare(vprism_data, akshare_data, tolerance=0.01)
print("数据一致性报告:", report.summary())
```

### 💡 最佳实践总结

#### 开发环境设置
```python
# 推荐的开发环境配置
vprism.configure({
    "cache": {
        "enabled": True,
        "ttl": 300,  # 5分钟缓存适合开发调试
        "memory_size": 500
    },
    "logging": {
        "level": "DEBUG",
        "format": "detailed"
    },
    "providers": {
        "yahoo_finance": {
            "enabled": True,
            "rate_limit": 1000,  # 开发时放宽限制
            "timeout": 30
        }
    }
})
```

#### 生产环境最佳实践
```python
# 生产环境配置模板
vprism.configure({
    "cache": {
        "enabled": True,
        "ttl": 3600,  # 1小时缓存
        "memory_size": 10000,
        "disk_cache": True,
        "compression": True
    },
    "logging": {
        "level": "INFO",
        "format": "json",
        "rotation": "daily",
        "max_files": 30
    },
    "providers": {
        "yahoo_finance": {
            "enabled": True,
            "rate_limit": 100,
            "timeout": 30,
            "retries": 3,
            "backoff_factor": 2
        }
    },
    "error_handling": {
        "max_retries": 3,
        "fallback_enabled": True
    }
})
```

### 📞 获取帮助的途径

1. **查看日志**: 首先检查详细的错误日志
2. **文档查询**: 搜索相关API文档和示例
3. **社区支持**: 在GitHub Discussions提问
4. **问题报告**: 提交详细的bug报告
5. **实时聊天**: 加入Discord社区获取即时帮助

### 🔍 调试工具集

#### 系统信息收集脚本
```bash
#!/bin/bash
echo "=== vprism 系统诊断报告 ==="
echo "生成时间: $(date)"
echo "Python版本: $(python --version)"
echo "vprism版本: $(python -c 'import vprism; print(vprism.__version__)') 2>/dev/null || echo '未安装'"
echo "操作系统: $(uname -s)"
echo "网络连接: $(curl -s -o /dev/null -w "%{http_code}" https://finance.yahoo.com)"
echo "磁盘空间: $(df -h / | tail -1)"
echo "内存使用: $(free -h | grep Mem)"
```

#### Python调试助手
```python
def debug_vprism():
    """vprism调试信息收集器"""
    import vprism
    import platform
    import pkg_resources
    
    print("=== vprism 调试信息 ===")
    print(f"vprism版本: {vprism.__version__}")
    print(f"Python版本: {platform.python_version()}")
    print(f"操作系统: {platform.platform()}")
    print(f"安装路径: {vprism.__file__}")
    print(f"可用提供商: {list(vprism.list_providers())}")
    print(f"配置路径: {vprism.get_config_path()}")
    
    # 测试基本连接
    try:
        data = vprism.get("AAPL", limit=1)
        print("✅ 数据连接正常")
        print(f"最近一条数据: {data.iloc[0]['close']}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")

# 运行调试
if __name__ == "__main__":
    debug_vprism()
```

通过以上全面的故障排除指南，您可以快速定位和解决使用vprism过程中遇到的各种问题。建议将此文档加入书签，在遇到困难时按图索骥进行排查。