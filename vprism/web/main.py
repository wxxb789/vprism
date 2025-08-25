"""
Web 服务启动脚本
"""

import os

import uvicorn


def vprism_main() -> None:
    """启动 FastAPI Web 服务"""

    # 配置
    vprism_host = os.getenv("VPRISM_HOST", "0.0.0.0")
    vprism_port = int(os.getenv("VPRISM_PORT", "8000"))
    vprism_reload = os.getenv("VPRISM_RELOAD", "false").lower() == "true"

    # 启动服务
    uvicorn.run("app:app", host=vprism_host, port=vprism_port, reload=vprism_reload, log_level="info")


if __name__ == "__main__":
    vprism_main()
