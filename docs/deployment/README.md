# vprism 部署和运维指南

## 概述

vprism支持四种部署模式：Python库模式、Web服务模式、MCP模式和容器化部署。每种模式都有其适用场景和配置要求。

## 📦 部署模式对比

| 部署模式 | 适用场景 | 启动命令 | 资源需求 | 扩展性 |
|----------|----------|----------|----------|--------|
| [Python库](#python库模式) | 个人开发、数据分析 | `import vprism` | 低 | 单机 |
| [Web服务](#web服务模式) | API服务、微服务架构 | `python -m vprism_web.main` | 中 | 水平扩展 |
| [MCP服务](#mcp模式) | AI助手集成、聊天机器人 | `python -m mcp.server` | 低-中 | 单机/集群 |
| [容器化](#容器化部署) | 生产环境、云部署 | `docker run` | 可配置 | Kubernetes集群 |

## Python库模式

### 安装

```bash
# 从PyPI安装
pip install vprism

# 从源码安装
git clone https://github.com/your-repo/vprism.git
cd vprism
pip install -e .
```

### 基本配置

#### 环境变量配置
```bash
export VPRISM_CACHE_ENABLED=true
export VPRISM_CACHE_TTL=3600
export VPRISM_LOG_LEVEL=INFO
export VPRISM_DATA_DIR=~/.vprism
```

#### 配置文件 (~/.vprism/config.json)
```json
{
  "cache": {
    "enabled": true,
    "ttl": 3600,
    "memory_size": 1000,
    "disk_path": "~/.vprism/cache"
  },
  "providers": {
    "yahoo_finance": {
      "enabled": true,
      "rate_limit": 100,
      "timeout": 30
    },
    "akshare": {
      "enabled": true,
      "rate_limit": 200
    }
  },
  "logging": {
    "level": "INFO",
    "format": "json",
    "file": "~/.vprism/vprism.log"
  }
}
```

### Jupyter Notebook集成

```python
import vprism
import matplotlib.pyplot as plt

# 设置Notebook配置
vprism.configure({
    "cache": {"enabled": True},
    "logging": {"level": "WARNING"}
})

# 获取数据并可视化
data = vprism.get("AAPL", timeframe="1d", limit=100)
data['close'].plot(figsize=(12, 6))
plt.title('AAPL Stock Price')
plt.show()
```

## Web服务模式

### 快速启动

#### 开发环境
```bash
# 安装依赖
pip install -r src/vprism_web/requirements-web.txt

# 启动开发服务器
python -m vprism_web.main web --reload

# 访问API文档
open http://localhost:8000/docs
```

#### 生产环境 (Gunicorn)
```bash
# 安装生产依赖
pip install gunicorn uvloop httptools

# 启动生产服务器
gunicorn vprism_web.main:app \
  --host 0..0.0 \
  --port 8000 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --log-level info
```

### 环境配置

#### 环境变量 (.env)
```bash
# 服务器配置
VPRISM_WEB_HOST=0.0.0.0
VPRISM_WEB_PORT=8000
VPRISM_WEB_WORKERS=4
VPRISM_WEB_RELOAD=false

# 缓存配置
VPRISM_REDIS_URL=redis://localhost:6379/0
VPRISM_CACHE_TTL=3600

# 安全配置
VPRISM_API_KEY_REQUIRED=true
VPRISM_JWT_SECRET_KEY=your-secret-key-here

# 监控配置
VPRISM_METRICS_ENABLED=true
VPRISM_HEALTH_CHECK_INTERVAL=30
```

#### 系统服务 (systemd)
创建 `/etc/systemd/system/vprism_web.service`:
```ini
[Unit]
Description=vprism web service
After=network.target

[Service]
Type=exec
User=vprism
Group=vprism
WorkingDirectory=/opt/vprism
Environment=PATH=/opt/vprism/venv/bin
ExecStart=/opt/vprism/venv/bin/gunicorn vprism_web.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
sudo systemctl enable vprism_web
sudo systemctl start vprism_web
sudo systemctl status vprism_web
```

### Nginx反向代理配置

创建 `/etc/nginx/sites-available/vprism`:
```nginx
upstream vprism_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name finance-api.your-domain.com;

    location / {
        proxy_pass http://vprism_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /health {
        access_log off;
        proxy_pass http://vprism_backend/api/v1/health;
    }
}
```

## MCP模式

### Claude Desktop配置

#### macOS配置
```bash
# 配置文件路径
~/Library/Application Support/Claude/claude_desktop_config.json
```

#### Windows配置
```bash
# 配置文件路径
%APPDATA%/Claude/claude_desktop_config.json
```

#### 配置内容
```json
{
  "mcpServers": {
    "vprism-finance": {
      "command": "/usr/bin/python3",
      "args": ["-m", "mcp.server"],
      "cwd": "/opt/vprism"
    }
  }
}
```

### 高级MCP配置

#### HTTP传输模式
```json
{
  "mcpServers": {
    "vprism-finance": {
      "command": "python",
      "args": ["-m", "mcp.server", "--transport", "http", "--port", "8080"],
      "cwd": "/opt/vprism",
      "env": {
        "MCP_API_KEY": "your-secure-api-key",
        "MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

#### 多实例配置
```json
{
  "mcpServers": {
    "vprism-us-stocks": {
      "command": "python",
      "args": ["-m", "mcp.server", "--config", "config/us_market.json"],
      "cwd": "/opt/vprism"
    },
    "vprism-cn-stocks": {
      "command": "python", 
      "args": ["-m", "mcp.server", "--config", "config/cn_market.json"],
      "cwd": "/opt/vprism"
    }
  }
}
```

## 容器化部署

### Docker快速启动

#### 基础镜像
```bash
# 构建镜像
docker build -t vprism:latest -f src/vprism_docker/Dockerfile .

# 运行容器
docker run -d \
  --name vprism_web \
  -p 8000:8000 \
  -e VPRISM_WEB_PORT=8000 \
  -e VPRISM_REDIS_URL=redis://redis:6379/0 \
  vprism:latest web
```

#### Docker Compose (开发环境)
创建 `docker-compose.dev.yml`:
```yaml
version: '3.8'
services:
  vprism_web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - VPRISM_WEB_RELOAD=true
      - VPRISM_LOG_LEVEL=DEBUG
    volumes:
      - ./src:/app/src
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

#### Docker Compose (生产环境)
创建 `docker-compose.prod.yml`:
```yaml
version: '3.8'
services:
  vprism_web:
    image: vprism:latest
    ports:
      - "8000:8000"
    environment:
      - VPRISM_WEB_WORKERS=4
      - VPRISM_REDIS_URL=redis://redis:6379/0
      - VPRISM_LOG_LEVEL=INFO
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - vprism_web
    restart: unless-stopped

volumes:
  redis_data:
```

### Kubernetes部署

#### Deployment配置
创建 `k8s/vprism-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vprism_web
  labels:
    app: vprism_web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: vprism_web
  template:
    metadata:
      labels:
        app: vprism_web
    spec:
      containers:
      - name: vprism_web
        image: vprism:latest
        ports:
        - containerPort: 8000
        env:
        - name: VPRISM_WEB_WORKERS
          value: "4"  
        - name: VPRISM_REDIS_URL
          value: "redis://redis-service:6379/0"
        - name: VPRISM_LOG_LEVEL
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
            path: /api/v1/health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

#### Service配置
```yaml
apiVersion: v1
kind: Service
metadata:
  name: vprism_web-service
spec:
  selector:
    app: vprism_web
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
spec:
  selector:
    app: redis
  ports:
  - protocol: TCP
    port: 6379
    targetPort: 6379
  type: ClusterIP
```

#### Ingress配置
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: vprism-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - finance-api.your-domain.com
    secretName: vprism-tls
  rules:
  - host: finance-api.your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: vprism_web-service
            port:
              number: 80
```

### Helm Chart部署

#### 安装Helm Chart
```bash
# 添加仓库
helm repo add vprism https://charts.vprism.com
helm repo update

# 安装
helm install vprism vprism/vprism_web \
  --set image.tag=latest \
  --set ingress.enabled=true \
  --set ingress.host=finance-api.your-domain.com

# 自定义配置安装
helm install vprism vprism/vprism_web -f custom-values.yaml
```

#### 自定义values.yaml
```yaml
replicaCount: 3

image:
  repository: vprism/web-service
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: finance-api.your-domain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: vprism-tls
      hosts:
        - finance-api.your-domain.com

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 250m
    memory: 256Mi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80
```

## 监控和运维

### Prometheus监控

#### Prometheus配置
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'vprism_web'
    static_configs:
      - targets: ['vprism_web:8000']
    metrics_path: /metrics
    scrape_interval: 30s
```

#### Grafana仪表板
导入官方Grafana仪表板ID: `12345` (vprism官方仪表板)

### 日志管理

#### ELK Stack配置
```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/vprism/*.log
  json.keys_under_root: true
  json.add_error_key: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "vprism-logs-%{+yyyy.MM.dd}"
```

#### 日志轮转
创建 `/etc/logrotate.d/vprism`:
```bash
/var/log/vprism/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 vprism vprism
    postrotate
        systemctl reload vprism_web
    endscript
}
```

### 备份和灾难恢复

#### 数据库备份脚本
创建 `scripts/backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/backup/vprism"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份DuckDB数据库
cp ~/.vprism/data.duckdb $BACKUP_DIR/data_$DATE.duckdb

# 备份Redis数据 (如果使用Redis)
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# 备份配置文件
cp ~/.vprism/config.json $BACKUP_DIR/config_$DATE.json

# 清理旧备份 (保留30天)
find $BACKUP_DIR -type f -name "*.duckdb" -mtime +30 -delete
find $BACKUP_DIR -type f -name "*.rdb" -mtime +30 -delete
find $BACKUP_DIR -type f -name "*.json" -mtime +30 -delete

echo "Backup completed at $DATE"
```

#### 自动化备份
添加到crontab:
```bash
# 每天凌晨2点备份
0 2 * * * /opt/vprism/scripts/backup.sh

# 每小时备份Redis
0 * * * * redis-cli BGSAVE
```

## 性能调优

### 系统参数优化

#### 内核参数 (/etc/sysctl.conf)
```bash
# 网络优化
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.core.netdev_max_backlog = 5000

# 文件描述符
fs.file-max = 65535
```

#### 用户限制 (/etc/security/limits.conf)
```bash
vprism soft nofile 65535
vprism hard nofile 65535
```

### 应用性能优化

#### Python性能调优
```python
# gunicorn_config.py
bind = "0.0.0.0:8000"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
keepalive = 2
max_requests = 1000
max_requests_jitter = 50
preload_app = True
```

#### Docker性能优化
```dockerfile
# 多阶段构建优化
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY src/ ./src/
ENV PATH=/root/.local/bin:$PATH
CMD ["python", "-m", "vprism_web.main"]
```

## 安全最佳实践

### SSL/TLS配置

#### Nginx SSL配置
```nginx
server {
    listen 443 ssl http2;
    server_name finance-api.your-domain.com;

    ssl_certificate /etc/ssl/certs/vprism.crt;
    ssl_certificate_key /etc/ssl/private/vprism.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://vprism_backend;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

### API安全

#### API密钥管理
```python
# 密钥生成脚本
import secrets
import hashlib

def generate_api_key():
    return secrets.token_urlsafe(32)

def hash_api_key(api_key):
    return hashlib.sha256(api_key.encode()).hexdigest()
```

#### 速率限制配置
```python
# rate_limit_config.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# 不同用户等级的限制
RATE_LIMITS = {
    "anonymous": "100/minute",
    "basic": "1000/minute", 
    "premium": "10000/minute"
}
```

## 故障排除指南

### 常见问题诊断

#### 检查服务状态
```bash
#!/bin/bash
# health_check.sh

# Web服务状态
if curl -s http://localhost:8000/api/v1/health > /dev/null; then
    echo "✅ Web服务运行正常"
else
    echo "❌ Web服务异常"
fi

# Redis连接
if redis-cli ping > /dev/null; then
    echo "✅ Redis连接正常"
else
    echo "❌ Redis连接失败"
fi

# 磁盘空间
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -lt 80 ]; then
    echo "✅ 磁盘空间充足"
else
    echo "⚠️ 磁盘空间不足: ${DISK_USAGE}%"
fi

# 内存使用
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
if [ $MEMORY_USAGE -lt 80 ]; then
    echo "✅ 内存使用率正常"
else
    echo "⚠️ 内存使用率较高: ${MEMORY_USAGE}%"
fi
```

#### 日志分析工具
```bash
#!/bin/bash
# log_analyzer.sh

echo "=== 错误日志统计 ==="
grep -c "ERROR" /var/log/vprism/vprism.log | tail -100

echo -e "\n=== 最频繁的错误 ==="
grep "ERROR" /var/log/vprism/vprism.log | tail -1000 | \
  awk -F'ERROR' '{print $2}' | sort | uniq -c | sort -nr | head -10

echo -e "\n=== 响应时间统计 ==="  
grep "request_id" /var/log/vprism/vprism.log | tail -1000 | \
  jq -r '.processing_time_ms' | awk '{sum+=$1} END {print "平均响应时间:", sum/NR, "ms"}'
```

### 性能监控仪表板

#### Grafana查询示例
```promql
# 请求速率
rate(http_requests_total[5m])

# 错误率
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# 响应时间95分位数
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# 缓存命中率
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))
```

通过以上完整的部署和运维指南，您可以根据实际需求选择最适合的部署模式，并确保系统的稳定运行和高效运维。每种模式都有详细的配置示例和最佳实践，帮助您快速上手生产环境部署。