"""Web相关的工具函数"""

from fastapi import Request


def get_request_id(request: Request) -> str | None:
    """从请求头中获取 X-Request-ID"""
    return request.headers.get("X-Request-ID")
