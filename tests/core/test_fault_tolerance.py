"""
Tests for fault tolerance mechanisms.

This module tests the CircuitBreaker, ExponentialBackoffRetry, HealthChecker,
and FaultToleranceManager components to ensure robust fault tolerance.
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

from vprism.core.fault_tolerance import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    ExponentialBackoffRetry,
    RetryConfig,
    HealthChecker,
    HealthCheckConfig,
    HealthStatus,
    FaultToleranceManager,
    fault_tolerance_manager,
)
from vprism.core.exceptions import (
    CircuitBreakerOpenException,
    TimeoutException,
    ProviderException,
)


class TestCircuitBreaker:
    """Test CircuitBreaker functionality."""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initialization."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30,
            success_threshold=2,
            timeout=10.0,
        )
        
        cb = CircuitBreaker("test_cb", config)
        
        assert cb.name == "test_cb"
        assert cb.config == config
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.metrics.total_requests == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_success_flow(self):
        """Test circuit breaker with successful operations."""
        cb = CircuitBreaker("test_success")
        
        async def successful_func():
            return "success"
        
        # Multiple successful calls
        for _ in range(5):
            result = await cb.call(successful_func)
            assert result == "success"
        
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.metrics.successful_requests == 5
        assert cb.metrics.failed_requests == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_flow(self):
        """Test circuit breaker with failing operations."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test_failure", config)
        
        async def failing_func():
            raise ProviderException("Test failure")
        
        # First few failures should not open circuit
        for i in range(2):
            with pytest.raises(ProviderException):
                await cb.call(failing_func)
            assert cb.state == CircuitBreakerState.CLOSED
        
        # Third failure should open circuit
        with pytest.raises(ProviderException):
            await cb.call(failing_func)
        assert cb.state == CircuitBreakerState.OPEN
        
        # Subsequent calls should be rejected
        with pytest.raises(CircuitBreakerOpenException):
            await cb.call(failing_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker half-open state and recovery."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=1,  # 1 second for quick test
            success_threshold=2,
        )
        cb = CircuitBreaker("test_recovery", config)
        
        # Force circuit to open
        async def failing_func():
            raise ProviderException("Test failure")
        
        for _ in range(2):
            with pytest.raises(ProviderException):
                await cb.call(failing_func)
        
        assert cb.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        
        # Next call should transition to half-open
        async def successful_func():
            return "success"
        
        result = await cb.call(successful_func)
        assert result == "success"
        assert cb.state == CircuitBreakerState.HALF_OPEN
        
        # Another success should close the circuit
        result = await cb.call(successful_func)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_timeout(self):
        """Test circuit breaker timeout functionality."""
        config = CircuitBreakerConfig(timeout=0.1)  # 100ms timeout
        cb = CircuitBreaker("test_timeout", config)
        
        async def slow_func():
            await asyncio.sleep(0.2)  # Slower than timeout
            return "too_slow"
        
        with pytest.raises(TimeoutException):
            await cb.call(slow_func)
        
        assert cb.metrics.failed_requests == 1

    def test_circuit_breaker_metrics(self):
        """Test circuit breaker metrics collection."""
        cb = CircuitBreaker("test_metrics")
        
        # Initial metrics
        metrics = cb.get_metrics()
        assert metrics["name"] == "test_metrics"
        assert metrics["state"] == "closed"
        assert metrics["total_requests"] == 0
        assert metrics["success_rate"] == 0.0
        
        # Update metrics manually for testing
        cb._record_success()
        cb._record_success()
        cb._record_failure(Exception("test"))
        
        metrics = cb.get_metrics()
        assert metrics["total_requests"] == 3
        assert metrics["successful_requests"] == 2
        assert metrics["failed_requests"] == 1
        assert metrics["success_rate"] == 2/3

    def test_circuit_breaker_state_listeners(self):
        """Test circuit breaker state change listeners."""
        cb = CircuitBreaker("test_listeners")
        
        state_changes = []
        
        def listener(name, state):
            state_changes.append((name, state))
        
        cb.add_state_change_listener(listener)
        
        # Force state changes
        cb.force_open()
        cb.reset()
        
        assert len(state_changes) == 2
        assert state_changes[0] == ("test_listeners", CircuitBreakerState.OPEN)
        assert state_changes[1] == ("test_listeners", CircuitBreakerState.CLOSED)


class TestExponentialBackoffRetry:
    """Test ExponentialBackoffRetry functionality."""

    def test_retry_initialization(self):
        """Test retry mechanism initialization."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False,
        )
        
        retry = ExponentialBackoffRetry(config)
        assert retry.config == config

    def test_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=10.0,
            jitter=False,
        )
        retry = ExponentialBackoffRetry(config)
        
        # Test delay progression
        assert retry._calculate_delay(1) == 1.0  # 1.0 * 2^0
        assert retry._calculate_delay(2) == 2.0  # 1.0 * 2^1
        assert retry._calculate_delay(3) == 4.0  # 1.0 * 2^2
        assert retry._calculate_delay(4) == 8.0  # 1.0 * 2^3
        assert retry._calculate_delay(5) == 10.0  # Capped at max_delay

    def test_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        config = RetryConfig(
            base_delay=4.0,
            exponential_base=2.0,
            jitter=True,
        )
        retry = ExponentialBackoffRetry(config)
        
        # With jitter, delay should vary around the base value
        delays = [retry._calculate_delay(1) for _ in range(10)]
        
        # All delays should be positive and around 4.0 ± 25%
        assert all(delay > 0 for delay in delays)
        assert all(3.0 <= delay <= 5.0 for delay in delays)
        
        # Should have some variation
        assert len(set(delays)) > 1

    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self):
        """Test retry with success on first attempt."""
        retry = ExponentialBackoffRetry()
        
        async def successful_func():
            return "success"
        
        result = await retry.execute(successful_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test retry with success after some failures."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)  # Fast retry for testing
        retry = ExponentialBackoffRetry(config)
        
        attempt_count = 0
        
        async def eventually_successful_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ProviderException(f"Attempt {attempt_count} failed")
            return f"success_on_attempt_{attempt_count}"
        
        result = await retry.execute(eventually_successful_func)
        assert result == "success_on_attempt_3"
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_retry_all_attempts_fail(self):
        """Test retry when all attempts fail."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        retry = ExponentialBackoffRetry(config)
        
        attempt_count = 0
        
        async def always_failing_func():
            nonlocal attempt_count
            attempt_count += 1
            raise ProviderException(f"Attempt {attempt_count} failed")
        
        with pytest.raises(ProviderException) as exc_info:
            await retry.execute(always_failing_func)
        
        assert "Attempt 3 failed" in str(exc_info.value)
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_retry_non_retryable_exception(self):
        """Test retry with non-retryable exception."""
        config = RetryConfig(
            max_attempts=3,
            retryable_exceptions=(ProviderException,)
        )
        retry = ExponentialBackoffRetry(config)
        
        attempt_count = 0
        
        async def non_retryable_failure():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Non-retryable error")
        
        with pytest.raises(ValueError):
            await retry.execute(non_retryable_failure)
        
        # Should only attempt once for non-retryable exception
        assert attempt_count == 1


class TestHealthChecker:
    """Test HealthChecker functionality."""

    def test_health_checker_initialization(self):
        """Test health checker initialization."""
        def health_check():
            return True
        
        config = HealthCheckConfig(
            interval=60,
            timeout=5.0,
            failure_threshold=2,
            success_threshold=1,
        )
        
        hc = HealthChecker("test_service", health_check, config)
        
        assert hc.name == "test_service"
        assert hc.health_check_func == health_check
        assert hc.config == config
        assert hc.current_status == HealthStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        def successful_health_check():
            return True
        
        hc = HealthChecker("test_service", successful_health_check)
        
        result = await hc.check_health()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.error is None
        assert result.response_time_ms > 0
        assert hc.current_status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test failed health check."""
        def failing_health_check():
            raise Exception("Health check failed")
        
        config = HealthCheckConfig(failure_threshold=1)
        hc = HealthChecker("test_service", failing_health_check, config)
        
        result = await hc.check_health()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "Health check failed" in result.error
        assert hc.current_status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Test health check timeout."""
        async def slow_health_check():
            await asyncio.sleep(0.2)
            return True
        
        config = HealthCheckConfig(timeout=0.1)
        hc = HealthChecker("test_service", slow_health_check, config)
        
        result = await hc.check_health()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_health_status_transitions(self):
        """Test health status transitions based on thresholds."""
        check_should_pass = True
        
        def conditional_health_check():
            if check_should_pass:
                return True
            else:
                raise Exception("Check failed")
        
        config = HealthCheckConfig(
            failure_threshold=2,
            success_threshold=2,
        )
        hc = HealthChecker("test_service", conditional_health_check, config)
        
        # Start with successful checks
        await hc.check_health()
        await hc.check_health()
        assert hc.current_status == HealthStatus.HEALTHY
        
        # Switch to failing checks
        check_should_pass = False
        await hc.check_health()
        assert hc.current_status == HealthStatus.HEALTHY  # Still healthy after 1 failure
        
        await hc.check_health()
        assert hc.current_status == HealthStatus.UNHEALTHY  # Unhealthy after 2 failures
        
        # Switch back to successful checks
        check_should_pass = True
        await hc.check_health()
        assert hc.current_status == HealthStatus.UNHEALTHY  # Still unhealthy after 1 success
        
        await hc.check_health()
        assert hc.current_status == HealthStatus.HEALTHY  # Healthy after 2 successes

    def test_health_checker_metrics(self):
        """Test health checker metrics collection."""
        def health_check():
            return True
        
        hc = HealthChecker("test_service", health_check)
        
        metrics = hc.get_metrics()
        assert metrics["name"] == "test_service"
        assert metrics["current_status"] == "unknown"
        assert metrics["total_checks"] == 0

    def test_health_status_change_listeners(self):
        """Test health status change listeners."""
        def health_check():
            return True
        
        config = HealthCheckConfig(success_threshold=1)
        hc = HealthChecker("test_service", health_check, config)
        
        status_changes = []
        
        def listener(name, status):
            status_changes.append((name, status))
        
        hc.add_status_change_listener(listener)
        
        # Trigger status change
        asyncio.run(hc.check_health())
        
        assert len(status_changes) == 1
        assert status_changes[0] == ("test_service", HealthStatus.HEALTHY)


class TestFaultToleranceManager:
    """Test FaultToleranceManager functionality."""

    def test_manager_initialization(self):
        """Test fault tolerance manager initialization."""
        manager = FaultToleranceManager()
        
        assert len(manager.circuit_breakers) == 0
        assert len(manager.health_checkers) == 0
        assert len(manager.retry_policies) == 0

    def test_get_or_create_circuit_breaker(self):
        """Test circuit breaker creation and retrieval."""
        manager = FaultToleranceManager()
        
        # Create new circuit breaker
        cb1 = manager.get_or_create_circuit_breaker("test_cb")
        assert cb1.name == "test_cb"
        assert len(manager.circuit_breakers) == 1
        
        # Get existing circuit breaker
        cb2 = manager.get_or_create_circuit_breaker("test_cb")
        assert cb1 is cb2
        assert len(manager.circuit_breakers) == 1

    def test_get_or_create_retry_policy(self):
        """Test retry policy creation and retrieval."""
        manager = FaultToleranceManager()
        
        # Create new retry policy
        retry1 = manager.get_or_create_retry_policy("test_retry")
        assert len(manager.retry_policies) == 1
        
        # Get existing retry policy
        retry2 = manager.get_or_create_retry_policy("test_retry")
        assert retry1 is retry2
        assert len(manager.retry_policies) == 1

    def test_register_health_checker(self):
        """Test health checker registration."""
        manager = FaultToleranceManager()
        
        def health_check():
            return True
        
        hc = manager.register_health_checker("test_service", health_check)
        
        assert hc.name == "test_service"
        assert len(manager.health_checkers) == 1
        assert manager.health_checkers["test_service"] is hc

    @pytest.mark.asyncio
    async def test_execute_with_fault_tolerance(self):
        """Test executing function with full fault tolerance."""
        manager = FaultToleranceManager()
        
        call_count = 0
        
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ProviderException("First attempt fails")
            return "success"
        
        # Configure for quick retry
        circuit_config = CircuitBreakerConfig(failure_threshold=5)
        retry_config = RetryConfig(max_attempts=3, base_delay=0.01)
        
        result = await manager.execute_with_fault_tolerance(
            "test_operation",
            test_func,
            circuit_breaker_config=circuit_config,
            retry_config=retry_config,
        )
        
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_check_all_health(self):
        """Test checking health of all registered services."""
        manager = FaultToleranceManager()
        
        def healthy_check():
            return True
        
        def unhealthy_check():
            raise Exception("Service down")
        
        manager.register_health_checker("healthy_service", healthy_check)
        manager.register_health_checker("unhealthy_service", unhealthy_check)
        
        results = await manager.check_all_health()
        
        assert len(results) == 2
        assert results["healthy_service"].status == HealthStatus.HEALTHY
        assert results["unhealthy_service"].status == HealthStatus.UNHEALTHY

    def test_get_all_metrics(self):
        """Test getting metrics for all components."""
        manager = FaultToleranceManager()
        
        # Create some components
        manager.get_or_create_circuit_breaker("test_cb")
        manager.register_health_checker("test_service", lambda: True)
        
        metrics = manager.get_all_metrics()
        
        assert "circuit_breakers" in metrics
        assert "health_checkers" in metrics
        assert "test_cb" in metrics["circuit_breakers"]
        assert "test_service" in metrics["health_checkers"]

    def test_circuit_breaker_status(self):
        """Test getting circuit breaker status."""
        manager = FaultToleranceManager()
        
        cb = manager.get_or_create_circuit_breaker("test_cb")
        cb.force_open()
        
        status = manager.get_circuit_breaker_status()
        assert status["test_cb"] == "open"

    def test_health_status(self):
        """Test getting health status."""
        manager = FaultToleranceManager()
        
        def health_check():
            return True
        
        hc = manager.register_health_checker("test_service", health_check)
        
        # Manually set status for testing
        hc.current_status = HealthStatus.HEALTHY
        
        status = manager.get_health_status()
        assert status["test_service"] == "healthy"

    def test_reset_all_circuit_breakers(self):
        """Test resetting all circuit breakers."""
        manager = FaultToleranceManager()
        
        cb1 = manager.get_or_create_circuit_breaker("cb1")
        cb2 = manager.get_or_create_circuit_breaker("cb2")
        
        # Force both to open
        cb1.force_open()
        cb2.force_open()
        
        assert cb1.state == CircuitBreakerState.OPEN
        assert cb2.state == CircuitBreakerState.OPEN
        
        # Reset all
        manager.reset_all_circuit_breakers()
        
        assert cb1.state == CircuitBreakerState.CLOSED
        assert cb2.state == CircuitBreakerState.CLOSED


class TestGlobalFaultToleranceManager:
    """Test global fault tolerance manager instance."""

    def test_global_manager_exists(self):
        """Test that global manager instance exists."""
        assert fault_tolerance_manager is not None
        assert isinstance(fault_tolerance_manager, FaultToleranceManager)

    def test_global_manager_functionality(self):
        """Test basic functionality of global manager."""
        # Should be able to create circuit breakers
        cb = fault_tolerance_manager.get_or_create_circuit_breaker("global_test")
        assert cb.name == "global_test"
        
        # Should be able to create retry policies
        retry = fault_tolerance_manager.get_or_create_retry_policy("global_test")
        assert retry is not None


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple fault tolerance mechanisms."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_retry(self):
        """Test circuit breaker combined with retry mechanism."""
        manager = FaultToleranceManager()
        
        failure_count = 0
        
        async def intermittent_failure():
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 3:
                raise ProviderException(f"Failure {failure_count}")
            return "success"
        
        # Configure for multiple retries but low circuit breaker threshold
        circuit_config = CircuitBreakerConfig(failure_threshold=2)
        retry_config = RetryConfig(max_attempts=5, base_delay=0.01)
        
        # First execution should fail and open circuit breaker
        with pytest.raises(ProviderException):
            await manager.execute_with_fault_tolerance(
                "test_integration",
                intermittent_failure,
                circuit_breaker_config=circuit_config,
                retry_config=retry_config,
            )
        
        # Circuit should be open now
        cb = manager.circuit_breakers["test_integration"]
        assert cb.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_health_check_with_circuit_breaker_integration(self):
        """Test health checker integration with circuit breaker."""
        manager = FaultToleranceManager()
        
        service_healthy = True
        
        def health_check():
            if service_healthy:
                return True
            else:
                raise Exception("Service unhealthy")
        
        async def service_operation():
            if service_healthy:
                return "success"
            else:
                raise ProviderException("Service operation failed")
        
        # Register health checker
        hc = manager.register_health_checker("integrated_service", health_check)
        
        # Initially healthy
        result = await hc.check_health()
        assert result.status == HealthStatus.HEALTHY
        
        # Service operation should work
        result = await manager.execute_with_fault_tolerance(
            "integrated_service",
            service_operation,
        )
        assert result == "success"
        
        # Make service unhealthy
        service_healthy = False
        
        # Health check should detect this
        result = await hc.check_health()
        assert result.status == HealthStatus.UNHEALTHY
        
        # Service operations should start failing
        with pytest.raises(ProviderException):
            await manager.execute_with_fault_tolerance(
                "integrated_service",
                service_operation,
            )

    @pytest.mark.asyncio
    async def test_concurrent_fault_tolerance_operations(self):
        """Test concurrent operations with fault tolerance."""
        manager = FaultToleranceManager()
        
        async def concurrent_operation(operation_id: int):
            # Simulate some operations failing
            if operation_id % 3 == 0:
                raise ProviderException(f"Operation {operation_id} failed")
            await asyncio.sleep(0.01)  # Small delay
            return f"success_{operation_id}"
        
        # Execute multiple operations concurrently
        tasks = []
        for i in range(20):
            task = manager.execute_with_fault_tolerance(
                f"concurrent_op_{i}",
                concurrent_operation,
                operation_id=i,
                circuit_breaker_config=CircuitBreakerConfig(failure_threshold=1),
                retry_config=RetryConfig(max_attempts=2, base_delay=0.01),
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes and failures
        successes = [r for r in results if isinstance(r, str) and r.startswith("success_")]
        failures = [r for r in results if isinstance(r, Exception)]
        
        # Should have some successes and some failures
        assert len(successes) > 0
        assert len(failures) > 0
        assert len(successes) + len(failures) == 20