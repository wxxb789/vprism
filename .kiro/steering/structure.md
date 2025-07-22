# vprism Project Structure - IMPLEMENTED & RESTRUCTURED

## CRITICAL DIRECTORY STRUCTURE RULES

**⚠️ STRICT ENFORCEMENT:**
- **Git root**: `Q:/repos/my/vprism/` (NEVER create subdirectories with source code)
- **Core module**: `Q:/repos/my/vprism/src/vprism/` (核心逻辑模块)
- **Web module**: `Q:/repos/my/vprism/src/vprism_web/` (Web服务包装器)
- **MCP module**: `Q:/repos/my/vprism/src/vprism_mcp/` (MCP服务器包装器)
- **Docker module**: `Q:/repos/my/vprism/src/vprism_docker/` (Docker配置)
- **Test code**: `Q:/repos/my/vprism/tests/` (测试代码)
- **NO EXCEPTIONS**: 所有代码必须位于相应模块目录内

## 模块化架构结构 - RESTRUCTURED

```
vprism/
├── src/
│   ├── vprism/           # 核心逻辑模块 (核心API、数据模型、业务逻辑)
│   ├── vprism_web/       # Web服务包装器 (FastAPI接口)
│   ├── vprism_mcp/       # MCP服务器包装器 (MCP协议接口)
│   └── vprism_docker/    # Docker配置 (容器化配置)
├── tests/                # 综合测试套件
├── devjournal/           # 开发日志和笔记
├── guide/                # 用户文档和指南
├── pyproject.toml        # 项目配置
├── uv.lock              # 依赖版本锁定
├── README.md            # 项目概述
├── .kiro/               # 项目指导文档
└── .git/                # Git仓库
```

## 模块详细结构 - REVAMPED

### `src/vprism/` - 核心逻辑模块 - REVAMPED
```
vprism/
├── __init__.py          # 包初始化和导出
├── core/                # 核心业务逻辑
│   ├── __init__.py
│   ├── exceptions.py    # 自定义异常层次结构
│   ├── models.py        # 核心领域模型
│   ├── config.py        # 配置管理
│   ├── logging.py       # 统一日志系统
│   └── client.py        # 主客户端接口
├── infrastructure/      # 基础设施层
│   ├── __init__.py
│   ├── providers/       # 数据提供商适配器
│   ├── cache/           # 多级缓存实现
│   ├── repositories/    # 数据持久化层
│   └── storage/         # 数据库模式和操作
```

### `src/vprism_web/` - Web服务包装器 - REVAMPED ✅
```
vprism_web/
├── __init__.py          # Web模块初始化
├── main.py              # Web服务启动脚本
├── app.py               # FastAPI应用工厂
├── models.py            # Web API请求/响应模型
├── requirements-web.txt # Web服务依赖
├── routes/              # API路由处理器
│   ├── __init__.py
│   ├── data_routes.py   # 金融数据端点
│   └── health_routes.py # 健康监控端点
└── services/            # Web服务业务逻辑
    ├── __init__.py
    ├── data_service.py  # 数据服务
    └── health_service.py # 健康检查服务
```

### `src/vprism_mcp/` - MCP服务器包装器 - REVAMPED ✅
```
vprism_mcp/
├── __init__.py          # MCP模块初始化
├── __main__.py          # CLI入口点
├── server.py            # FastMCP服务器实现
├── mcp_config.json      # MCP配置文件
└── mcp_config.yaml      # MCP配置YAML格式
```

### `src/vprism_docker/` - Docker配置模块 - REVAMPED ✅
```
vprism_docker/
├── Dockerfile                          # 多阶段容器构建
├── docker-compose.yml                  # 主服务配置
├── docker-compose.extensions.yml       # 环境扩展配置
├── DOCKER_DEPLOY.md                    # 完整部署指南
└── nginx/                              # Nginx配置
    ├── nginx.conf                      # 基础配置
    ├── nginx.prod.conf                 # 生产配置
    ├── nginx.ssl.conf                  # SSL配置
    └── ssl/                            # SSL证书目录
        ├── cert.pem
        └── key.pem
```

## DIRECTORY VIOLATION CHECKLIST

**❌ NEVER ALLOWED:**
- `Q:/repos/my/vprism/vprism/` (duplicate root)
- `Q:/repos/my/vprism/vprism/src/vprism/` (nested duplication)
- Any source code outside designated module directories
- Nested module directories (e.g., `vprism-web/web/`)
- Docker files in root directory (e.g., `docker-compose.yml`, `Dockerfile`, `docker-deploy.md`)
- Nginx configuration in root directory

**✅ ALWAYS ENSURE:**
- All `.py` files in appropriate module directories
- No duplicate package structures
- Single source of truth for each file type
- Flat module structure within each wrapper
- Docker-related files ONLY in `src/vprism_docker/`
- Configuration files grouped by concern in appropriate directories

## 模块职责划分

### 核心模块 (vprism/)
- **职责**: 核心API、数据模型、业务逻辑、缓存策略
- **依赖**: 仅依赖外部库，不依赖其他模块
- **使用方式**: 作为库被其他模块导入使用

### Web模块 (vprism_web/)
- **职责**: FastAPI接口、HTTP路由、Web服务启动
- **依赖**: 依赖核心模块 `vprism`
- **使用方式**: 独立运行Web服务

### MCP模块 (vprism_mcp/)
- **职责**: MCP协议接口、AI工具集成
- **依赖**: 依赖核心模块 `vprism`
- **使用方式**: 独立运行MCP服务器

### Docker模块 (vprism_docker/)
- **职责**: 容器化配置、环境部署
- **依赖**: 依赖所有其他模块的构建产物
- **使用方式**: 构建和运行容器化服务