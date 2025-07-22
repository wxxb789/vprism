#!/usr/bin/env python3
"""
Web 服务基础测试
"""

from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'vprism_web'))
from app import create_app


def test_basic_app():
    """测试基本应用创建"""
    app = create_app()
    assert app is not None
    assert app.title == "vprism - 下一代个人金融数据平台"


def test_health_endpoint():
    """测试健康检查端点"""
    app = create_app()

    # 使用 TestClient 进行测试
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        print(f"健康检查响应: {response.status_code}")
        print(f"响应内容: {response.json()}")


if __name__ == "__main__":
    test_basic_app()
    test_health_endpoint()
    print("✓ Web 服务基础测试通过")
