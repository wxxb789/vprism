"""
Web 服务启动脚本
"""

import uvicorn
import os
from pathlib import Path


def main():
    """启动 FastAPI Web 服务"""

    # 配置
    host = os.getenv("VPRISM_HOST", "0.0.0.0")
    port = int(os.getenv("VPRISM_PORT", "8000"))
    reload = os.getenv("VPRISM_RELOAD", "false").lower() == "true"

    # 启动服务
    uvicorn.run("app:app", host=host, port=port, reload=reload, log_level="info")


if __name__ == "__main__":
    main()
