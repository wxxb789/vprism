"""
Tests for core exception classes.

This module contains comprehensive tests for all exception classes,
ensuring proper error handling and structured error information.
"""

import pytest

from vprism.core.exceptions import (
    AuthenticationException,
    CacheException,
    ConfigurationException,
    DataNotFoundException,
    NetworkException,
    NoAvailableProviderException,
    ProviderException,
    RateLimitException,
    TimeoutException,
    ValidationException,
    VPrismException,
)


class TestVPrismException:
    """Test base VPrismException class."""

    def test_basic_exception_creation(self):
        """Test creating a basic VPrism exception."""
        exc = VPrismException(message="Test error", error_code="TEST_ERROR")

        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.details == {}
        assert exc.cause is None
        assert str(exc) == "Test error"

    def test_exception_with_details(self):
        """Test exception with additional details."""
        details = {"field": "test_field", "value": "test_value"}
        exc = VPrismException(
            message="Validation failed", error_code="VALIDATION_ERROR", details=details
        )

        assert exc.details == details

    def test_exception_with_cause(self):
        """Test exception with underlying cause."""
        original_error = ValueError("Original error")
        exc = VPrismException(
            message="Wrapped error", error_code="WRAPPED_ERROR", cause=original_error
        )

        assert exc.cause == original_error

    def test_to_dict_method(self):
        """Test converting exception to dictionary."""
        details = {"field": "test_field"}
        original_error = ValueError("Original error")

        exc = VPrismException(
            message="Test error",
            error_code="TEST_ERROR",
            details=details,
            cause=original_error,
        )

        result = exc.to_dict()

        expected = {
            "error": "TEST_ERROR",
            "message": "Test error",
            "details": details,
            "cause": "Original error",
        }

        assert result == expected

    def test_to_dict_without_cause(self):
        """Test to_dict method without cause."""
        exc = VPrismException(message="Test error", error_code="TEST_ERROR")

        result = exc.to_dict()

        expected = {
            "error": "TEST_ERROR",
            "message": "Test error",
            "details": {},
            "cause": None,
        }

        assert result == expected


class TestValidationException:
    """Test ValidationException class."""

    def test_basic_validation_exception(self):
        """Test creating a basic validation exception."""
        exc = ValidationException("Invalid value")

        assert exc.message == "Invalid value"
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.details == {}

    def test_validation_exception_with_field(self):
        """Test validation exception with field information."""
        exc = ValidationException(
            message="Invalid email format", field="email", value="invalid-email"
        )

        assert exc.message == "Invalid email format"
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.details["field"] == "email"
        assert exc.details["value"] == "invalid-email"

    def test_validation_exception_with_details(self):
        """Test validation exception with additional details."""
        details = {"constraint": "length", "min": 5, "max": 50}
        exc = ValidationException(
            message="String too short", field="username", value="abc", details=details
        )

        assert exc.details["field"] == "username"
        assert exc.details["value"] == "abc"
        assert exc.details["constraint"] == "length"
        assert exc.details["min"] == 5
        assert exc.details["max"] == 50


class TestProviderException:
    """Test ProviderException class."""

    def test_basic_provider_exception(self):
        """Test creating a basic provider exception."""
        exc = ProviderException(message="Provider failed", provider="test_provider")

        assert exc.message == "Provider failed"
        assert exc.error_code == "PROVIDER_ERROR"
        assert exc.details["provider"] == "test_provider"

    def test_provider_exception_with_custom_error_code(self):
        """Test provider exception with custom error code."""
        exc = ProviderException(
            message="API quota exceeded",
            provider="test_provider",
            error_code="QUOTA_EXCEEDED",
        )

        assert exc.error_code == "QUOTA_EXCEEDED"
        assert exc.details["provider"] == "test_provider"

    def test_provider_exception_with_cause(self):
        """Test provider exception with underlying cause."""
        original_error = ConnectionError("Network timeout")
        exc = ProviderException(
            message="Failed to connect to provider",
            provider="test_provider",
            cause=original_error,
        )

        assert exc.cause == original_error
        assert exc.details["provider"] == "test_provider"


class TestRateLimitException:
    """Test RateLimitException class."""

    def test_basic_rate_limit_exception(self):
        """Test creating a basic rate limit exception."""
        exc = RateLimitException(provider="test_provider")

        assert "Rate limit exceeded for provider test_provider" in exc.message
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"
        assert exc.details["provider"] == "test_provider"

    def test_rate_limit_exception_with_retry_after(self):
        """Test rate limit exception with retry after information."""
        exc = RateLimitException(provider="test_provider", retry_after=60)

        assert "Retry after 60 seconds" in exc.message
        assert exc.details["retry_after_seconds"] == 60
        assert exc.details["provider"] == "test_provider"


class TestAuthenticationException:
    """Test AuthenticationException class."""

    def test_authentication_exception(self):
        """Test creating an authentication exception."""
        exc = AuthenticationException(provider="test_provider")

        assert exc.message == "Authentication failed for provider test_provider"
        assert exc.error_code == "AUTHENTICATION_FAILED"
        assert exc.details["provider"] == "test_provider"

    def test_authentication_exception_with_details(self):
        """Test authentication exception with additional details."""
        details = {"reason": "invalid_api_key", "status_code": 401}
        exc = AuthenticationException(provider="test_provider", details=details)

        assert exc.details["provider"] == "test_provider"
        assert exc.details["reason"] == "invalid_api_key"
        assert exc.details["status_code"] == 401


class TestDataNotFoundException:
    """Test DataNotFoundException class."""

    def test_basic_data_not_found_exception(self):
        """Test creating a basic data not found exception."""
        exc = DataNotFoundException()

        assert exc.message == "Requested data not found"
        assert exc.error_code == "DATA_NOT_FOUND"
        assert exc.details == {}

    def test_data_not_found_exception_with_query(self):
        """Test data not found exception with query information."""
        exc = DataNotFoundException(
            message="No data found for symbol", query="asset=stock&symbol=INVALID"
        )

        assert exc.message == "No data found for symbol"
        assert exc.details["query"] == "asset=stock&symbol=INVALID"


class TestConfigurationException:
    """Test ConfigurationException class."""

    def test_configuration_exception(self):
        """Test creating a configuration exception."""
        exc = ConfigurationException(
            message="Missing required configuration", config_key="api_key"
        )

        assert exc.message == "Missing required configuration"
        assert exc.error_code == "CONFIGURATION_ERROR"
        assert exc.details["config_key"] == "api_key"


class TestCacheException:
    """Test CacheException class."""

    def test_cache_exception(self):
        """Test creating a cache exception."""
        exc = CacheException(message="Cache operation failed", operation="get")

        assert exc.message == "Cache operation failed"
        assert exc.error_code == "CACHE_ERROR"
        assert exc.details["operation"] == "get"

    def test_cache_exception_with_cause(self):
        """Test cache exception with underlying cause."""
        original_error = ConnectionError("Redis connection failed")
        exc = CacheException(
            message="Failed to connect to cache",
            operation="connect",
            cause=original_error,
        )

        assert exc.cause == original_error
        assert exc.details["operation"] == "connect"


class TestNetworkException:
    """Test NetworkException class."""

    def test_network_exception(self):
        """Test creating a network exception."""
        exc = NetworkException(
            message="Network request failed",
            url="https://api.example.com/data",
            status_code=500,
        )

        assert exc.message == "Network request failed"
        assert exc.error_code == "NETWORK_ERROR"
        assert exc.details["url"] == "https://api.example.com/data"
        assert exc.details["status_code"] == 500


class TestTimeoutException:
    """Test TimeoutException class."""

    def test_basic_timeout_exception(self):
        """Test creating a basic timeout exception."""
        exc = TimeoutException()

        assert exc.message == "Operation timed out"
        assert exc.error_code == "TIMEOUT_ERROR"
        assert exc.details == {}

    def test_timeout_exception_with_duration(self):
        """Test timeout exception with timeout duration."""
        exc = TimeoutException(message="Request timed out", timeout_seconds=30.0)

        assert exc.message == "Request timed out"
        assert exc.details["timeout_seconds"] == 30.0


class TestNoAvailableProviderException:
    """Test NoAvailableProviderException class."""

    def test_basic_no_provider_exception(self):
        """Test creating a basic no provider exception."""
        exc = NoAvailableProviderException()

        assert exc.message == "No available data provider for request"
        assert exc.error_code == "NO_PROVIDER_AVAILABLE"
        assert exc.details == {}

    def test_no_provider_exception_with_details(self):
        """Test no provider exception with query and attempted providers."""
        exc = NoAvailableProviderException(
            message="No provider supports this asset type",
            query="asset=exotic_derivative",
            attempted_providers=["provider_a", "provider_b"],
        )

        assert exc.message == "No provider supports this asset type"
        assert exc.details["query"] == "asset=exotic_derivative"
        assert exc.details["attempted_providers"] == ["provider_a", "provider_b"]


class TestExceptionInheritance:
    """Test exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_vprism_exception(self):
        """Test that all custom exceptions inherit from VPrismException."""
        exception_classes = [
            ValidationException,
            ProviderException,
            RateLimitException,
            AuthenticationException,
            DataNotFoundException,
            ConfigurationException,
            CacheException,
            NetworkException,
            TimeoutException,
            NoAvailableProviderException,
        ]

        for exc_class in exception_classes:
            assert issubclass(exc_class, VPrismException)

    def test_provider_specific_exceptions_inherit_from_provider_exception(self):
        """Test that provider-specific exceptions inherit from ProviderException."""
        provider_exception_classes = [
            RateLimitException,
            AuthenticationException,
        ]

        for exc_class in provider_exception_classes:
            assert issubclass(exc_class, ProviderException)

    def test_exception_can_be_caught_as_base_exception(self):
        """Test that specific exceptions can be caught as base exceptions."""
        try:
            raise RateLimitException(provider="test")
        except ProviderException as e:
            assert isinstance(e, RateLimitException)
            assert isinstance(e, ProviderException)
            assert isinstance(e, VPrismException)
        except Exception:
            pytest.fail("Should have been caught as ProviderException")

        try:
            raise ValidationException("test")
        except VPrismException as e:
            assert isinstance(e, ValidationException)
            assert isinstance(e, VPrismException)
        except Exception:
            pytest.fail("Should have been caught as VPrismException")
