"""健康检查系统测试"""

from datetime import datetime

import pytest

from vprism.core.health import HealthChecker, HealthStatus, get_health_checker


class TestHealthChecker:
    """测试健康检查器"""

    def test_initialization(self):
        """测试健康检查器初始化"""
        checker = HealthChecker()
        assert checker.start_time > 0
        assert len(checker.checks) > 0  # 应该有默认检查

    def test_register_custom_check(self):
        """测试注册自定义健康检查"""
        checker = HealthChecker()

        async def custom_check():
            return {"status": "healthy", "details": {"custom": True}}

        checker.register_check("custom", custom_check)
        assert "custom" in checker.checks

    @pytest.mark.asyncio
    async def test_check_health_success(self):
        """测试健康检查成功场景"""
        checker = HealthChecker()
        health = await checker.check_health()

        assert isinstance(health, HealthStatus)
        assert health.status in ["healthy", "degraded", "unhealthy"]
        assert isinstance(health.timestamp, datetime)
        assert health.uptime_seconds > 0
        assert isinstance(health.checks, dict)

    @pytest.mark.asyncio
    async def test_check_health_with_failing_check(self):
        """测试包含失败检查的健康检查"""
        checker = HealthChecker()

        async def failing_check():
            raise Exception("Test failure")

        checker.register_check("failing", failing_check)
        health = await checker.check_health()

        assert health.status == "unhealthy"
        assert "failing" in health.checks
        assert health.checks["failing"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_check_providers(self):
        """测试提供商状态检查"""
        checker = HealthChecker()
        providers = ["akshare", "yahoo_finance"]

        status = await checker.check_providers(providers)
        assert isinstance(status, dict)
        assert len(status) == 2
        assert "akshare" in status
        assert "yahoo_finance" in status

        for _provider_name, provider_status in status.items():
            assert "status" in provider_status
            assert "last_check" in provider_status

    @pytest.mark.asyncio
    async def test_system_health_check(self):
        """测试系统健康检查"""
        checker = HealthChecker()
        health_status = await checker._check_system_health()

        assert isinstance(health_status, dict)
        assert "status" in health_status
        assert health_status["status"] in ["healthy", "degraded"]
        assert "details" in health_status

    def test_global_instance(self):
        """测试全局健康检查器实例"""
        checker1 = get_health_checker()
        checker2 = get_health_checker()
        assert checker1 is checker2  # 应该是同一个实例

    @pytest.mark.asyncio
    async def test_health_status_model(self):
        """测试健康状态数据模型"""
        checks = {
            "system": {"status": "healthy", "details": {}},
            "memory": {"status": "healthy", "details": {}},
        }
        health = HealthStatus(
            status="healthy",
            timestamp=datetime.utcnow(),
            checks=checks,
            uptime_seconds=123.45,
        )

        assert health.status == "healthy"
        assert health.uptime_seconds == 123.45
        assert len(health.checks) == 2
        assert "system" in health.checks
        assert "memory" in health.checks


class TestHealthEndpoints:
    """测试健康检查端点"""

    @pytest.mark.asyncio
    async def test_health_check_response_structure(self):
        """测试健康检查响应结构"""
        checker = HealthChecker()
        health = await checker.check_health()

        response_data = {
            "status": health.status,
            "timestamp": health.timestamp.isoformat(),
            "uptime_seconds": health.uptime_seconds,
            "version": health.version,
            "checks": health.checks,
        }

        assert isinstance(response_data["status"], str)
        assert isinstance(response_data["timestamp"], str)
        assert isinstance(response_data["uptime_seconds"], int | float)
        assert isinstance(response_data["checks"], dict)

    @pytest.mark.asyncio
    async def test_uptime_calculation(self):
        """测试运行时间计算"""
        checker = HealthChecker()
        health = await checker.check_health()
        assert health.uptime_seconds > 0


class TestHealthIntegration:
    """测试健康检查集成"""

    @pytest.mark.asyncio
    async def test_custom_check_integration(self):
        """测试自定义检查集成"""
        checker = HealthChecker()

        async def mock_check():
            return {"status": "healthy", "details": {"mock": True, "value": 42}}

        checker.register_check("mock_check", mock_check)
        health = await checker.check_health()

        assert "mock_check" in health.checks
        assert health.checks["mock_check"]["status"] == "healthy"
        assert health.checks["mock_check"]["details"]["mock"] is True


if __name__ == "__main__":
    pytest.main([__file__])
