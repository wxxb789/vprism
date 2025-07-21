# 多阶段构建的 vprism Web 服务
FROM python:3.11-slim as builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Web 服务依赖
COPY ../vprism-web/requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# 生产阶段
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 创建非root用户
RUN useradd -m -u 1000 vprism

# 复制依赖
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY ../vprism src/
COPY ../vprism-web/main.py ./
COPY README.md ./

# 设置环境变量
ENV PYTHONPATH=/app
ENV VPRISM_HOST=0.0.0.0
ENV VPRISM_PORT=8000

# 切换到非root用户
USER vprism

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/v1/health')"

# 启动命令
CMD ["python", "main.py", "web"]