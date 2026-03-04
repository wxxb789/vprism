"""Health check system tests."""

import asyncio
from typing import Any

import pytest

from vprism.core.health import HealthChecker, HealthStatus, get_health_checker


class TestHealthChecker:
    """Test health checker."""

    def test_initialization(self) -> None:
        """Test health checker initialization."""
        checker = HealthChecker()
        assert checker.start_time > 0
        assert len(checker.checks) > 0  # should have default checks

    def test_register_custom_check(self) -> None:
        """Test registering a custom health check."""
        checker = HealthChecker()

        async def custom_check() -> dict[str, Any]:
            return {"status": "healthy", "details": {"custom": True}}

        checker.register_check("custom", custom_check)
        assert "custom" in checker.checks

    @pytest.mark.asyncio
    async def test_check_health_success(self) -> None:
        """Test health check success scenario."""
        await asyncio.sleep(0.01)  # ensure a small delay
        checker = HealthChecker()
        health = await checker.check_health()

        assert isinstance(health, HealthStatus)
        assert health.status in ["healthy", "degraded", "unhealthy"]
        assert health.uptime_seconds >= 0
        assert isinstance(health.checks, dict)

    @pytest.mark.asyncio
    async def test_check_health_with_failing_check(self) -> None:
        """Test health check with a failing component."""
        checker = HealthChecker()

        async def failing_check() -> dict[str, Any]:
            raise Exception("Test failure")

        checker.register_check("failing", failing_check)
        health = await checker.check_health()

        assert health.status == "unhealthy"
        assert "failing" in health.checks
        assert health.checks["failing"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_check_providers(self) -> None:
        """Test provider status check."""
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
    async def test_system_health_check(self) -> None:
        """Test system health check."""
        checker = HealthChecker()
        health_status = await checker._check_system_health()

        assert isinstance(health_status, dict)
        assert "status" in health_status
        assert health_status["status"] in ["healthy", "degraded"]
        assert "details" in health_status

    def test_global_instance(self) -> None:
        """Test global health checker instance."""
        checker1 = get_health_checker()
        checker2 = get_health_checker()
        assert checker1 is checker2  # should be the same instance


class TestHealthIntegration:
    """Test health check integration."""

    @pytest.mark.asyncio
    async def test_custom_check_integration(self) -> None:
        """Test custom check integration."""
        checker = HealthChecker()

        async def mock_check() -> dict[str, Any]:
            return {"status": "healthy", "details": {"mock": True, "value": 42}}

        checker.register_check("mock_check", mock_check)
        health = await checker.check_health()

        assert "mock_check" in health.checks
        assert health.checks["mock_check"]["status"] == "healthy"
        assert health.checks["mock_check"]["details"]["mock"] is True
