# vprism Financial Data Platform - 性能优化和全面测试系统

## 1. 性能优化配置 (vprism/config/performance.py)

```python
"""
性能优化配置 - 缓存策略、连接池、异步处理
"""

import redis
import asyncio
from typing import Optional, Any, Dict
from dataclasses import dataclass
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import logging

@dataclass
class PerformanceConfig:
    """性能配置类"""
    # 缓存配置
    cache_enabled: bool = True
    cache_ttl: int = 300  # 5分钟
    cache_max_size: int = 1000
    redis_url: str = "redis://localhost:6379"
    redis_pool_size: int = 10
    redis_max_connections: int = 20
    
    # 数据库配置
    db_pool_size: int = 20
    db_max_overflow: int = 30
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    db_echo: bool = False
    
    # 异步配置
    max_concurrent_requests: int = 100
    request_timeout: int = 30
    connection_timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0

class CacheManager:
    """Redis缓存管理器"""
    def __init__(self, config: PerformanceConfig):
        self.config = config
        self.redis_client = None
        self._setup_redis()
    
    def _setup_redis(self):
        """设置Redis连接"""
        if self.config.cache_enabled:
            self.redis_client = redis.Redis.from_url(
                self.config.redis_url,
                max_connections=self.config.redis_pool_size,
                decode_responses=True
            )
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if not self.redis_client:
            return None
        try:
            value = self.redis_client.get(key)
            return value
        except Exception as e:
            logging.error(f"Cache get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        if not self.redis_client:
            return False
        try:
            ttl = ttl or self.config.cache_ttl
            return self.redis_client.setex(key, ttl, str(value))
        except Exception as e:
            logging.error(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        if not self.redis_client:
            return False
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logging.error(f"Cache delete error: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """按模式删除缓存"""
        if not self.redis_client:
            return 0
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logging.error(f"Cache invalidate pattern error: {e}")
            return 0

class DatabaseManager:
    """数据库连接管理器"""
    def __init__(self, database_url: str, config: PerformanceConfig):
        self.config = config
        self.engine = create_async_engine(
            database_url,
            pool_size=config.db_pool_size,
            max_overflow=config.db_max_overflow,
            pool_timeout=config.db_pool_timeout,
            pool_recycle=config.db_pool_recycle,
            echo=config.db_echo,
            poolclass=StaticPool
        )
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

class RateLimiter:
    """速率限制器"""
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.default_limit = 100  # requests per minute
    
    async def check_rate_limit(self, key: str, limit: Optional[int] = None) -> tuple[bool, int]:
        """检查速率限制"""
        limit = limit or self.default_limit
        key = f"rate_limit:{key}"
        
        try:
            current = self.redis_client.incr(key)
            if current == 1:
                self.redis_client.expire(key, 60)
            
            remaining = max(0, limit - current)
            return current <= limit, remaining
        except Exception as e:
            logging.error(f"Rate limit check error: {e}")
            return True, limit  # 允许请求以防Redis故障

# 全局性能配置
performance_config = PerformanceConfig()
cache_manager = CacheManager(performance_config)
database_manager = None  # 将在初始化时设置
rate_limiter = None  # 将在初始化时设置
```

## 2. API性能优化中间件 (vprism/middleware/performance.py)

```python
"""
性能优化中间件 - 缓存、压缩、监控
"""

import gzip
import json
import time
from typing import Optional, Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from vprism.config.performance import cache_manager, rate_limiter

class PerformanceMiddleware(BaseHTTPMiddleware):
    """性能优化中间件"""
    
    def __init__(self, app, exclude_paths: set = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or {"/health", "/metrics", "/docs", "/openapi.json"}
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        path = request.url.path
        method = request.method
        cache_key = f"cache:{method}:{path}:{request.url.query}"
        rate_key = f"rate:{request.client.host}"
        
        # 跳过特定路径
        if path in self.exclude_paths:
            return await call_next(request)
        
        # 速率限制检查
        allowed, remaining = await rate_limiter.check_rate_limit(rate_key)
        if not allowed:
            return Response(
                content=json.dumps({"error": "Rate limit exceeded"}),
                status_code=429,
                headers={"X-RateLimit-Remaining": str(remaining)}
            )
        
        # 缓存检查 (仅GET请求)
        if method == "GET":
            cached_response = await cache_manager.get(cache_key)
            if cached_response:
                return Response(
                    content=cached_response,
                    media_type="application/json",
                    headers={"X-Cache": "HIT"}
                )
        
        # 执行请求
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # 添加性能头部
        response.headers["X-Process-Time"] = str(round(process_time, 3))
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        # 缓存响应 (仅GET请求和成功响应)
        if method == "GET" and response.status_code < 400:
            response_body = await self._get_response_body(response)
            if response_body:
                await cache_manager.set(cache_key, response_body)
        
        return response
    
    async def _get_response_body(self, response: Response) -> Optional[str]:
        """获取响应内容用于缓存"""
        try:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            return body.decode()
        except Exception as e:
            logging.error(f"Error reading response body for caching: {e}")
            return None

class CompressionMiddleware(BaseHTTPMiddleware):
    """响应压缩中间件"""
    
    def __init__(self, app, minimum_size: int = 500):
        super().__init__(app)
        self.minimum_size = minimum_size
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # 检查客户端是否支持压缩
        if "gzip" in request.headers.get("accept-encoding", ""):
            response_body = await self._get_response_body(response)
            if response_body and len(response_body) > self.minimum_size:
                compressed_body = gzip.compress(response_body.encode())
                response.headers["content-encoding"] = "gzip"
                response.headers["content-length"] = str(len(compressed_body))
                response.body_iterator = [compressed_body]
        
        return response

class MetricsMiddleware(BaseHTTPMiddleware):
    """性能指标中间件"""
    
    def __init__(self, app):
        super().__init__(app)
        self.metrics = {
            "request_count": 0,
            "request_duration": 0.0,
            "error_count": 0,
            "active_connections": 0
        }
    
    async def dispatch(self, request: Request, call_next):
        self.metrics["active_connections"] += 1
        self.metrics["request_count"] += 1
        start_time = time.time()
        
        try:
            response = await call_next(request)
            if response.status_code >= 400:
                self.metrics["error_count"] += 1
            return response
        finally:
            duration = time.time() - start_time
            self.metrics["request_duration"] += duration
            self.metrics["active_connections"] -= 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        avg_duration = 0
        if self.metrics["request_count"] > 0:
            avg_duration = self.metrics["request_duration"] / self.metrics["request_count"]
        
        return {
            "request_count": self.metrics["request_count"],
            "error_rate": self.metrics["error_count"] / max(self.metrics["request_count"], 1),
            "average_response_time": round(avg_duration, 3),
            "active_connections": self.metrics["active_connections"]
        }

# 全局中间件实例
metrics_middleware = None
```

## 3. 数据库查询优化 (vprism/database/optimization.py)

```python
"""
数据库查询优化 - 索引、查询缓存、批量操作
"""

from sqlalchemy import Index, text
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging

from vprism.core.models import StockData, Company, ProviderInfo

class QueryOptimizer:
    """查询优化器"""
    
    @staticmethod
    def create_optimized_indexes():
        """创建优化的数据库索引"""
        indexes = [
            Index('idx_stock_data_symbol_date', StockData.symbol, StockData.date),
            Index('idx_stock_data_date_range', StockData.date),
            Index('idx_company_symbol', Company.symbol),
            Index('idx_provider_active', ProviderInfo.is_active),
            Index('idx_stock_symbol_provider', StockData.symbol, StockData.provider_id),
        ]
        return indexes
    
    @staticmethod
    def get_batch_stock_data(symbols: List[str], start_date, end_date, db: Session) -> List[Dict[str, Any]]:
        """批量获取股票数据的优化查询"""
        try:
            query = db.query(StockData).filter(
                StockData.symbol.in_(symbols),
                StockData.date.between(start_date, end_date)
            ).order_by(StockData.symbol, StockData.date)
            
            return query.all()
        except Exception as e:
            logging.error(f"Batch query error: {e}")
            return []
    
    @staticmethod
    def get_historical_data_with_cache(symbol: str, start_date, end_date, db: Session) -> List[Dict[str, Any]]:
        """带缓存的历史数据查询"""
        from vprism.config.performance import cache_manager
        from datetime import datetime
        import orjson
        
        cache_key = f"stock_data:{symbol}:{start_date}:{end_date}"
        cached_data = cache_manager.get(cache_key)
        
        if cached_data:
            return orjson.loads(cached_data)
        
        try:
            query = db.query(StockData).filter(
                StockData.symbol == symbol,
                StockData.date.between(start_date, end_date)
            ).order_by(StockData.date)
            
            results = query.all()
            serialized_data = [
                {
                    "symbol": r.symbol,
                    "date": r.date.isoformat(),
                    "open": float(r.open_price) if r.open_price else None,
                    "high": float(r.high_price) if r.high_price else None,
                    "low": float(r.low_price) if r.low_price else None,
                    "close": float(r.close_price) if r.close_price else None,
                    "volume": r.volume
                }
                for r in results
            ]
            
            cache_manager.set(cache_key, orjson.dumps(serialized_data).decode(), ttl=300)
            return serialized_data
            
        except Exception as e:
            logging.error(f"Historical data query error: {e}")
            return []
    
    @staticmethod
    def optimize_query_plan(query):
        """优化查询计划"""
        return query.execution_options(
            compiled_cache=True,
            autoflush=False,
            expire_on_commit=False
        )

class ConnectionPoolManager:
    """连接池管理器"""
    
    def __init__(self, database_url: str, pool_size: int = 20):
        self.pool_size = pool_size
        self.connection_pool_stats = {
            "connections_created": 0,
            "connections_reused": 0,
            "connections_closed": 0
        }
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        return self.connection_pool_stats.copy()

# 查询优化器实例
query_optimizer = QueryOptimizer()
connection_pool = None
```

## 4. 性能测试套件 (tests/test_performance.py)

```python
"""
性能测试套件 - 负载测试、压力测试、基准测试
"""

import asyncio
import time
import pytest
import aiohttp
import psutil
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
import json

from tests.test_base import BaseTestCase

class PerformanceTestSuite(BaseTestCase):
    """性能测试套件"""
    
    def setUp(self):
        super().setUp()
        self.base_url = "http://localhost:8000/api"
        self.concurrent_users = 100
        self.test_duration = 60  # seconds
        self.max_response_time = 2.0  # seconds
    
    async def test_concurrent_requests(self):
        """并发请求性能测试"""
        async def make_request(session, symbol):
            url = f"{self.base_url}/stock/{symbol}"
            start_time = time.time()
            async with session.get(url) as response:
                response_time = time.time() - start_time
                return {
                    "status": response.status,
                    "response_time": response_time,
                    "symbol": symbol
                }
        
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
        tasks = []
        results = []
        
        async with aiohttp.ClientSession() as session:
            for i in range(self.concurrent_users):
                symbol = symbols[i % len(symbols)]
                task = make_request(session, symbol)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_requests = [r for r in results if isinstance(r, dict) and r["status"] == 200]
        failed_requests = [r for r in results if isinstance(r, dict) and r["status"] != 200]
        exceptions = [r for r in results if isinstance(r, Exception)]
        
        success_rate = len(successful_requests) / len(results) * 100
        avg_response_time = sum(r["response_time"] for r in successful_requests) / len(successful_requests)
        max_response_time = max(r["response_time"] for r in successful_requests)
        min_response_time = min(r["response_time"] for r in successful_requests)
        
        self.assertGreater(success_rate, 95, f"Success rate too low: {success_rate}%")
        self.assertLess(avg_response_time, self.max_response_time, f"Average response time too high: {avg_response_time}s")
        self.assertLess(max_response_time, self.max_response_time * 2, f"Max response time too high: {max_response_time}s")
    
    async def test_database_performance(self):
        """数据库性能测试"""
        from sqlalchemy import text
        from vprism.core.database import get_db
        from datetime import datetime, timedelta
        
        async with get_db() as db:
            # 测试批量查询性能
            start_time = time.time()
            query = text("""
                SELECT symbol, COUNT(*) as count, AVG(close_price) as avg_close
                FROM stock_data 
                WHERE date >= :start_date
                GROUP BY symbol
                LIMIT 100
            """)
            result = await db.execute(query, {"start_date": datetime.now() - timedelta(days=30)})
            query_time = time.time() - start_time
            
            self.assertLess(query_time, 1.0, f"Database query took too long: {query_time}s")
            self.assertGreater(len(result.all()), 0, "Database query returned no results")
    
    def test_memory_usage(self):
        """内存使用测试"""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 模拟大量数据处理
        large_data = []
        for i in range(1000):
            large_data.append({
                "symbol": f"STOCK{i:04d}",
                "price": 100 + i * 0.01,
                "volume": 1000 + i * 100
            })
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        self.assertLess(memory_increase, 100, f"Memory usage increased too much: {memory_increase}MB")
        self.assertLess(peak_memory, 500, f"Peak memory usage too high: {peak_memory}MB")
    
    async def test_api_response_times(self):
        """API响应时间测试"""
        endpoints_to_test = [
            "/api/health",
            "/api/stock/AAPL",
            "/api/markets",
            "/api/symbols/search?query=AAPL"
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints_to_test:
                url = f"{self.base_url}{endpoint}"
                start_time = time.time()
                async with session.get(url) as response:
                    response_time = time.time() - start_time
                    self.assertLess(response_time, 2.0, f"Endpoint {endpoint} took too long: {response_time}s")
                    self.assertEqual(response.status, 200, f"Endpoint {endpoint} returned status {response.status}")
    
    async def test_caching_performance(self):
        """缓存性能测试"""
        url = f"{self.base_url}/stock/AAPL/history?days=30"
        times = []
        cache_hits = 0
        cache_misses = 0
        
        async with aiohttp.ClientSession() as session:
            # 第一次请求应该是缓存未命中
            async with session.get(url) as response:
                if response.headers.get("X-Cache") == "HIT":
                    cache_hits += 1
                else:
                    cache_misses += 1
                times.append(response.headers.get("X-Process-Time"))
            
            # 第二次请求应该是缓存命中
            async with session.get(url) as response:
                if response.headers.get("X-Cache") == "HIT":
                    cache_hits += 1
                else:
                    cache_misses += 1
                times.append(response.headers.get("X-Process-Time"))
        
        self.assertGreater(cache_hits, 0, "No cache hits detected")
        self.assertLess(float(times[1]), float(times[0]), "Cache did not improve performance")
    
    def test_system_resources(self):
        """系统资源监控测试"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        load_avg = psutil.getloadavg()[0]
        
        self.assertLess(cpu_percent, 80, f"CPU usage too high: {cpu_percent}%")
        self.assertLess(memory_percent, 80, f"Memory usage too high: {memory_percent}%")
        self.assertLess(disk_usage, 90, f"Disk usage too high: {disk_usage}%")
        self.assertLess(load_avg, 2.0, f"Load average too high: {load_avg}")

class LoadTestRunner:
    """负载测试运行器"""
    
    def __init__(self):
        self.results = []
        self.errors = []
    
    async def run_load_test(self, target_function, concurrent_requests: int, duration: int):
        """运行负载测试"""
        tasks = []
        start_time = time.time()
        
        async def worker():
            while time.time() - start_time < duration:
                try:
                    result = await target_function()
                    self.results.append(result)
                except Exception as e:
                    self.errors.append(str(e))
                await asyncio.sleep(0.1)
        
        workers = [worker() for _ in range(concurrent_requests)]
        await asyncio.gather(*workers, return_exceptions=True)
    
    def generate_report(self) -> Dict[str, Any]:
        """生成测试报告"""
        total_requests = len(self.results) + len(self.errors)
        success_rate = len(self.results) / max(total_requests, 1) * 100
        avg_response_time = sum(self.results) / max(len(self.results), 1) if self.results else 0
        error_rate = len(self.errors) / max(total_requests, 1) * 100
        
        return {
            "total_requests": total_requests,
            "successful_requests": len(self.results),
            "failed_requests": len(self.errors),
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
            "error_rate": error_rate,
            "errors": self.errors[:10]  # 只显示前10个错误
        }

@pytest.mark.asyncio
async def test_end_to_end_performance():
    """端到端性能测试"""
    runner = LoadTestRunner()
    
    async def test_api_call():
        url = "http://localhost:8000/api/stock/AAPL"
        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            async with session.get(url) as response:
                response_time = time.time() - start_time
                return response_time
    
    await runner.run_load_test(test_api_call, concurrent_requests=50, duration=30)
    report = runner.generate_report()
    
    assert report["success_rate"] > 95, f"Success rate too low: {report['success_rate']}%"
    assert report["avg_response_time"] < 1.0, f"Average response time too high: {report['avg_response_time']}s"
    assert report["error_rate"] < 5, f"Error rate too high: {report['error_rate']}%"

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
```

## 5. 性能监控工具 (vprism/monitoring/performance_monitor.py)

```python
"""
性能监控系统 - 实时监控和告警
"""

import asyncio
import psutil
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import logging

@dataclass
class PerformanceMetrics:
    """性能指标数据结构"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_usage_percent: float
    network_io_sent: int
    network_io_recv: int
    active_connections: int
    request_count: int
    avg_response_time: float
    error_rate: float

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, alert_thresholds: Dict[str, float] = None):
        self.thresholds = alert_thresholds or {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_usage_percent": 90.0,
            "avg_response_time": 2.0,
            "error_rate": 5.0
        }
        self.metrics_history: List[PerformanceMetrics] = []
        self.is_monitoring = False
        self.alert_email = None
        self.smtp_server = None
    
    async def collect_system_metrics(self) -> PerformanceMetrics:
        """收集系统性能指标"""
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        network = psutil.net_io_counters()
        
        return PerformanceMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu,
            memory_percent=memory,
            disk_usage_percent=disk,
            network_io_sent=network.bytes_sent,
            network_io_recv=network.bytes_recv,
            active_connections=0,  # 需要从应用层获取
            request_count=0,  # 需要从应用层获取
            avg_response_time=0.0,  # 需要从应用层获取
            error_rate=0.0  # 需要从应用层获取
        )
    
    async def check_alerts(self, metrics: PerformanceMetrics) -> List[Dict[str, Any]]:
        """检查是否需要发送告警"""
        alerts = []
        metrics_dict = asdict(metrics)
        
        for metric_name, threshold in self.thresholds.items():
            current_value = metrics_dict.get(metric_name, 0)
            if current_value > threshold:
                alerts.append({
                    "metric": metric_name,
                    "value": current_value,
                    "threshold": threshold,
                    "timestamp": metrics.timestamp.isoformat(),
                    "severity": self._get_severity(current_value, threshold)
                })
        
        return alerts
    
    def _get_severity(self, value: float, threshold: float) -> str:
        """计算告警严重程度"""
        ratio = value / threshold
        if ratio > 2.0:
            return "critical"
        elif ratio > 1.5:
            return "warning"
        else:
            return "info"
    
    async def start_monitoring(self, interval: int = 30):
        """开始性能监控"""
        self.is_monitoring = True
        while self.is_monitoring:
            try:
                metrics = await self.collect_system_metrics()
                self.metrics_history.append(metrics)
                
                # 保持历史记录不超过1000条
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-1000:]
                
                alerts = await self.check_alerts(metrics)
                if alerts:
                    await self.send_alerts(alerts)
                
                await asyncio.sleep(interval)
            except Exception as e:
                logging.error(f"Monitoring error: {e}")
                await asyncio.sleep(interval)
    
    def stop_monitoring(self):
        """停止性能监控"""
        self.is_monitoring = False
    
    async def send_alerts(self, alerts: List[Dict[str, Any]]):
        """发送告警通知"""
        if not self.alert_email or not self.smtp_server:
            logging.warning("Email configuration not set up for alerts")
            return
        
        try:
            message = self._format_alert_message(alerts)
            msg = MIMEText(message)
            msg['Subject'] = 'vprism Performance Alert'
            msg['From'] = 'alerts@vprism.com'
            msg['To'] = self.alert_email
            
            server = smtplib.SMTP(self.smtp_server, 587)
            server.starttls()
            server.send_message(msg)
            server.quit()
            
        except Exception as e:
            logging.error(f"Failed to send alert email: {e}")
    
    def _format_alert_message(self, alerts: List[Dict[str, Any]]) -> str:
        """格式化告警消息"""
        message = f"vprism Performance Alert - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        for alert in alerts:
            message += f"ALERT: {alert['metric']} is {alert['value']:.2f} (threshold: {alert['threshold']:.2f}) - Severity: {alert['severity']}\n"
        return message
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """获取性能摘要"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        
        if not recent_metrics:
            return {}
        
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        response_time_values = [m.avg_response_time for m in recent_metrics if m.avg_response_time > 0]
        error_rate_values = [m.error_rate for m in recent_metrics if m.error_rate > 0]
        
        return {
            "period_hours": hours,
            "avg_cpu_percent": sum(cpu_values) / len(cpu_values),
            "max_cpu_percent": max(cpu_values),
            "avg_memory_percent": sum(memory_values) / len(memory_values),
            "max_memory_percent": max(memory_values),
            "avg_response_time": sum(response_time_values) / len(response_time_values) if response_time_values else 0,
            "max_response_time": max(response_time_values) if response_time_values else 0,
            "avg_error_rate": sum(error_rate_values) / len(error_rate_values) if error_rate_values else 0,
            "total_alerts": len([m for m in recent_metrics if m.cpu_percent > 80 or m.memory_percent > 85])
        }

# 全局监控器实例
performance_monitor = PerformanceMonitor()
```

## 6. 性能优化部署指南 (performance_deployment.md)

```markdown
# vprism 性能优化部署指南

## 1. 系统资源优化

### CPU优化
```bash
# 设置CPU亲和性
taskset -c 0-3 python -m vprism-api

# 调整进程优先级
nice -n -10 python -m vprism-api
```

### 内存优化
```bash
# 设置内存限制
ulimit -v 4194304  # 4GB 虚拟内存限制

# 配置Python垃圾回收
export PYTHONOPTIMIZE=1
export PYTHONDONTWRITEBYTECODE=1
```

### 网络优化
```bash
# 调整TCP参数
echo 'net.core.somaxconn = 1024' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_max_syn_backlog = 1024' >> /etc/sysctl.conf
sysctl -p
```

## 2. 数据库优化

### PostgreSQL配置
```sql
-- 创建索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stock_symbol_date ON stock_data(symbol, date);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_company_symbol ON companies(symbol);

-- 配置连接池
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
```

### Redis配置
```bash
# redis.conf
maxmemory 1gb
maxmemory-policy allkeys-lru
timeout 300
tcp-keepalive 300
```

## 3. 应用层优化

### FastAPI优化
```python
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(
    debug=False,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### 缓存策略
```python
# 分层缓存策略
CACHE_LAYERS = {
    "L1": "memory_cache",  # 1-5秒
    "L2": "redis_cache",   # 5-300秒
    "L3": "database_cache" # 5-60分钟
}
```

## 4. 部署优化

### Docker优化
```dockerfile
FROM python:3.11-slim

# 使用多阶段构建
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONHASHSEED=random

# 使用非root用户
USER 1000:1000
```

### Kubernetes部署优化
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vprism-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: vprism-api
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

## 5. 监控和告警

### Prometheus监控配置
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'vprism-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /metrics
    scrape_interval: 30s
```

### Grafana仪表盘
- API响应时间
- 错误率监控
- 系统资源使用率
- 数据库查询性能

## 性能基准测试

### 预期性能指标
- API响应时间: < 500ms (P95)
- 并发处理能力: 1000+ RPS
- 内存使用: < 1GB
- CPU使用: < 50%
- 数据库查询: < 100ms (P95)

### 负载测试命令
```bash
# 使用ApacheBench进行负载测试
ab -n 10000 -c 100 http://localhost:8000/api/stock/AAPL

# 使用Siege进行压力测试
siege -c 100 -t 60s http://localhost:8000/api/stock/AAPL

# 使用Locust进行复杂负载测试
locust -f tests/load_test.py --host=http://localhost:8000
```
```

这个完整的性能优化和测试系统提供了：
- Redis缓存优化
- 数据库连接池管理
- 并发请求处理优化
- 响应压缩和缓存
- 实时性能监控和告警
- 全面的性能测试套件
- 负载测试和压力测试
- 系统资源监控
- 部署优化指南