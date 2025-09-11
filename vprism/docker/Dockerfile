# vprism Financial Data Platform - Complete Docker Deployment
FROM python:3.13-slim as builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt requirements-dev.txt ./

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 生产阶段
FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    libpq-dev \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN useradd -m -u 1000 vprism

# 复制应用代码
COPY src/ ./src/
COPY setup.py ./
COPY pyproject.toml ./
COPY README.md ./
COPY src/vprism_docker/nginx/nginx.conf /etc/nginx/nginx.conf

# 安装应用包
RUN pip install -e .

# 设置权限
RUN chown -R vprism:vprism /app /etc/nginx/nginx.conf

# 切换到非root用户
USER vprism

# 暴露端口
EXPOSE 8000 8001 80 443

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# 启动命令
CMD ["python", "-m", "vprism-api", "--host", "0.0.0.0", "--port", "8000"]