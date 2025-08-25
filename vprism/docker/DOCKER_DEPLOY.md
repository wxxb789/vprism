# vprism Financial Data Platform - Complete Docker Deployment Guide

## 🚀 快速开始

### 1. 环境要求
- **Docker** & **Docker Compose** v2.0+
- **至少 4GB RAM**
- **10GB 可用磁盘空间**
- **支持的操作系统**: Linux/macOS/Windows

### 2. 一键启动
```bash
# 克隆项目
git clone <repository-url>
cd vprism

# 启动完整服务栈
docker-compose -f src/vprism_docker/docker-compose.yml up -d

# 查看服务状态
docker-compose -f src/vprism_docker/docker-compose.yml ps
```

### 3. 服务访问
- **📊 API 服务**: http://localhost:8000/api/docs
- **🤖 MCP 服务器**: http://localhost:8001/mcp
- **📡 SSE 端点**: http://localhost:8001/sse
- **🔍 数据库**: localhost:5432
- **⚡ Redis**: localhost:6379

## 🏗️ 服务架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx 代理    │────│   vprism API    │────│   PostgreSQL    │
│   :80/:443      │    │   :8000         │    │   :5432         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐    ┌─────────────────┐
         │              │   vprism MCP    │────│      Redis      │
         └──────────────│   :8001         │    │   :6379         │
                        └─────────────────┘    └─────────────────┘
                                 │
                        ┌─────────────────┐
                        │ 数据收集服务    │
                        │ vprism-data     │
                        └─────────────────┘
```

## 📋 部署模式

### 开发环境 🔧
```bash
# 开发模式（热重载）
docker-compose -f src/vprism_docker/docker-compose.yml \
               -f src/vprism_docker/docker-compose.dev.yml up -d

# 实时日志
docker-compose -f src/vprism_docker/docker-compose.yml logs -f
```

### 生产环境 🚀
```bash
# 生产模式（高可用）
docker-compose -f src/vprism_docker/docker-compose.yml \
               -f src/vprism_docker/docker-compose.prod.yml up -d

# 启用SSL/TLS
docker-compose -f src/vprism_docker/docker-compose.yml \
               -f src/vprism_docker/docker-compose.prod.yml \
               -f src/vprism_docker/docker-compose.ssl.yml up -d
```

### 测试环境 🧪
```bash
# 测试模式（临时数据）
docker-compose -f src/vprism_docker/docker-compose.test.yml up --build
```

## 🔧 配置选项

### 环境变量
```bash
# 数据库配置
DATABASE_URL=postgresql://vprism:vprism_password@postgres:5432/vprism

# Redis配置
REDIS_URL=redis://redis:6379/0

# 日志级别
LOG_LEVEL=INFO|DEBUG|WARNING|ERROR

# 运行环境
ENVIRONMENT=development|staging|production

# SSL配置
SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
SSL_KEY_PATH=/etc/nginx/ssl/key.pem
```

### 端口映射
| 服务 | 内部端口 | 外部端口 | 描述 |
|------|----------|----------|------|
| API服务 | 8000 | 8000 | REST API |
| MCP服务 | 8001 | 8001 | MCP协议 |
| 数据库 | 5432 | 5432 | PostgreSQL |
| 缓存 | 6379 | 6379 | Redis |
| 代理 | 80/443 | 80/443 | Nginx |

## 🗄️ 数据持久化

### 数据卷管理
```bash
# 查看数据卷
docker volume ls | grep vprism

# 备份数据
docker exec vprism-postgres-1 pg_dump -U vprism vprism > backup.sql

# 恢复数据
docker exec -i vprism-postgres-1 psql -U vprism vprism < backup.sql

# 清理数据
docker-compose -f src/vprism_docker/docker-compose.yml down -v
```

### 数据目录结构
```
vprism/
├── src/vprism_docker/
│   ├── docker-compose.yml          # 主配置
│   ├── docker-compose.dev.yml      # 开发配置
│   ├── docker-compose.prod.yml     # 生产配置
│   ├── docker-compose.test.yml     # 测试配置
│   ├── docker-compose.ssl.yml      # SSL配置
│   ├── docker-compose.monitoring.yml # 监控配置
│   ├── docker-compose.logging.yml  # 日志配置
│   ├── nginx/                      # Nginx配置
│   │   ├── nginx.conf
│   │   ├── nginx.prod.conf
│   │   ├── nginx.ssl.conf
│   │   └── ssl/
│   ├── monitoring/                 # 监控配置
│   │   ├── prometheus.yml
│   │   └── grafana/
│   └── logging/                    # 日志配置
│       ├── logstash.conf
│       └── elasticsearch/
├── logs/                           # 应用日志
├── data/                          # 持久化数据
└── backup/                        # 备份文件
```

## 📊 监控和运维

### 性能监控
```bash
# 启动监控栈
docker-compose -f src/vprism_docker/docker-compose.yml \
               -f src/vprism_docker/docker-compose.monitoring.yml up -d

# 访问监控面板
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

### 日志管理
```bash
# 启动日志聚合
docker-compose -f src/vprism_docker/docker-compose.yml \
               -f src/vprism_docker/docker-compose.logging.yml up -d

# 查看日志
# Kibana: http://localhost:5601
```

### 健康检查
```bash
# 检查API健康
curl http://localhost:8000/health

# 检查MCP服务
curl http://localhost:8001/mcp

# 检查数据库
pg_isready -h localhost -p 5432 -U vprism
```

## 🔒 安全设置

### SSL/TLS 配置
```bash
# 生成自签名证书
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout src/vprism_docker/nginx/ssl/key.pem \
  -out src/vprism_docker/nginx/ssl/cert.pem

# 使用Let's Encrypt证书
certbot certonly --standalone -d yourdomain.com
```

### 访问控制
```bash
# 生产环境启用认证
export API_KEY_REQUIRED=true
export CORS_ORIGINS=https://yourdomain.com
```

## 🚀 扩展部署

### 水平扩展
```bash
# 启动多个API实例
docker-compose -f src/vprism_docker/docker-compose.yml up --scale vprism-api=3 -d

# 启动多个MCP实例
docker-compose -f src/vprism_docker/docker-compose.yml up --scale mcp=2 -d
```

### 高可用部署
```bash
# Docker Swarm模式
docker swarm init
docker stack deploy -c src/vprism_docker/docker-compose.prod.yml vprism

# Kubernetes部署
kubectl apply -f src/vprism_docker/k8s/
```

## 🛠️ 故障排除

### 常见问题
```bash
# 重新构建镜像
docker-compose -f src/vprism_docker/docker-compose.yml build --no-cache

# 清理并重启
docker-compose -f src/vprism_docker/docker-compose.yml down -v
docker-compose -f src/vprism_docker/docker-compose.yml up -d

# 进入容器调试
docker-compose -f src/vprism_docker/docker-compose.yml exec vprism-api bash

# 查看资源使用
docker stats
```

### 性能调优
```bash
# 调整资源限制
docker-compose -f src/vprism_docker/docker-compose.yml up --scale vprism-api=2 \
               --scale postgres=1 --scale redis=1
```

## 📈 性能基准

### 预期性能指标
- **API响应时间**: < 500ms (P95)
- **并发处理能力**: 1000+ RPS
- **内存使用**: < 1GB 每容器
- **CPU使用**: < 50% 正常负载
- **数据库查询**: < 100ms (P95)

### 负载测试
```bash
# 使用ApacheBench
ab -n 10000 -c 100 http://localhost:8000/api/stock/AAPL

# 使用Siege
siege -c 100 -t 60s http://localhost:8000/api/stock/AAPL

# 使用Locust
locust -f tests/load_test.py --host=http://localhost:8000
```

## 🎯 一键部署脚本

```bash
#!/bin/bash
# deploy.sh - 一键部署脚本

ENV=${1:-production}
SSL=${2:-false}

if [ "$ENV" = "dev" ]; then
    docker-compose -f src/vprism_docker/docker-compose.yml \
                   -f src/vprism_docker/docker-compose.dev.yml up -d
elif [ "$ENV" = "prod" ]; then
    if [ "$SSL" = "true" ]; then
        docker-compose -f src/vprism_docker/docker-compose.yml \
                       -f src/vprism_docker/docker-compose.prod.yml \
                       -f src/vprism_docker/docker-compose.ssl.yml up -d
    else
        docker-compose -f src/vprism_docker/docker-compose.yml \
                       -f src/vprism_docker/docker-compose.prod.yml up -d
    fi
fi
echo "🚀 vprism部署完成！访问 http://localhost:8000/api/docs"
```

## 📞 支持

### 获取帮助
```bash
# 查看帮助
docker-compose -f src/vprism_docker/docker-compose.yml --help

# 查看日志
docker-compose -f src/vprism_docker/docker-compose.yml logs --tail=100

# 重启服务
docker-compose -f src/vprism_docker/docker-compose.yml restart vprism-api
```