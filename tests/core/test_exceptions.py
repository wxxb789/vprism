"""
Tests for core exception classes.

This module contains comprehensive tests for all exception classes,
ensuring proper error handling and structured error information.
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from vprism.core.exceptions import (
    AuthenticationException,
    CacheException,
    ConfigurationException,
    DataNotFoundException,
    ErrorCode,
    ErrorMessages,
    ErrorSeverity,
    ErrorTracker,
    ExceptionContext,
    NetworkException,
    NoAvailableProviderException,
    ProviderException,
    RateLimitException,
    TimeoutException,
    ValidationException,
    VPrismException,
    clear_error_stats,
    clear_request_context,
    create_error_response,
    get_error_stats,
    get_request_context,
    handle_exception_chain,
    set_request_context,
)


class TestVPrismException:
    """Test base VPrismException class."""

    def test_basic_exception_creation(self):
        """Test creating a basic VPrism exception."""
        exc = VPrismException(message="Test error", error_code=ErrorCode.VALIDATION_ERROR, auto_log=False)

        assert exc.message == "Test error"
        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        assert exc.severity == ErrorSeverity.MEDIUM
        assert exc.language == "en"
        assert exc.cause is None
        assert str(exc) == "Test error"
        assert exc.trace_id is not None
        assert isinstance(exc.timestamp, datetime)

    def test_exception_with_details(self):
        """Test exception with additional details."""
        details = {"field": "test_field", "value": "test_value"}
        exc = VPrismException(
            message="Validation failed", 
            error_code=ErrorCode.VALIDATION_ERROR, 
            details=details,
            auto_log=False
        )

        # Details should include both user-provided and system details
        assert "field" in exc.details
        assert "value" in exc.details
        assert "timestamp" in exc.details
        assert "trace_id" in exc.details

    def test_exception_with_cause(self):
        """Test exception with underlying cause."""
        original_error = ValueError("Original error")
        exc = VPrismException(
            message="Wrapped error", 
            error_code=ErrorCode.INTERNAL_ERROR, 
            cause=original_error,
            auto_log=False
        )

        assert exc.cause == original_error
        assert "cause_type" in exc.details
        assert "cause_message" in exc.details
        assert "traceback" in exc.details

    def test_to_dict_method(self):
        """Test converting exception to dictionary."""
        details = {"field": "test_field"}
        original_error = ValueError("Original error")

        exc = VPrismException(
            message="Test error",
            error_code=ErrorCode.VALIDATION_ERROR,
            details=details,
            cause=original_error,
            severity=ErrorSeverity.HIGH,
            auto_log=False
        )

        result = exc.to_dict(include_sensitive=True)

        assert result["error"] == ErrorCode.VALIDATION_ERROR.value
        assert result["message"] == "Test error"
        assert result["severity"] == ErrorSeverity.HIGH.value
        assert "timestamp" in result
        assert "trace_id" in result
        assert "details" in result
        assert "cause" in result

    def test_to_dict_without_sensitive_data(self):
        """Test to_dict method filtering sensitive data."""
        details = {"field": "test_field", "api_key": "secret123", "password": "hidden"}
        exc = VPrismException(
            message="Test error", 
            error_code=ErrorCode.VALIDATION_ERROR, 
            details=details,
            auto_log=False
        )

        result = exc.to_dict(include_sensitive=False)

        assert result["details"]["field"] == "test_field"
        assert result["details"]["api_key"] == "[REDACTED]"
        assert result["details"]["password"] == "[REDACTED]"

    def test_json_serialization(self):
        """Test JSON serialization and deserialization."""
        exc = VPrismException(
            message="Test error",
            error_code=ErrorCode.VALIDATION_ERROR,
            details={"field": "test"},
            severity=ErrorSeverity.HIGH,
            auto_log=False
        )

        json_str = exc.to_json(include_sensitive=True)
        assert isinstance(json_str, str)
        
        # Test that it's valid JSON
        data = json.loads(json_str)
        assert data["error"] == ErrorCode.VALIDATION_ERROR.value
        assert data["message"] == "Test error"

    def test_from_dict_creation(self):
        """Test creating exception from dictionary."""
        data = {
            "error": ErrorCode.VALIDATION_ERROR.value,
            "message": "Test error",
            "details": {"field": "test"},
            "severity": ErrorSeverity.HIGH.value,
            "language": "zh"
        }

        exc = VPrismException.from_dict(data)

        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        assert exc.message == "Test error"
        assert exc.severity == ErrorSeverity.HIGH
        assert exc.language == "zh"
        assert "field" in exc.details

    def test_from_json_creation(self):
        """Test creating exception from JSON string."""
        data = {
            "error": ErrorCode.VALIDATION_ERROR.value,
            "message": "Test error",
            "details": {"field": "test"},
            "severity": ErrorSeverity.HIGH.value
        }
        json_str = json.dumps(data)

        exc = VPrismException.from_json(json_str)

        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        assert exc.message == "Test error"
        assert exc.severity == ErrorSeverity.HIGH

    def test_from_json_invalid_data(self):
        """Test creating exception from invalid JSON."""
        invalid_json = "invalid json string"
        
        exc = VPrismException.from_json(invalid_json)
        
        assert exc.error_code == ErrorCode.INTERNAL_ERROR
        assert "Failed to deserialize exception" in exc.message

    def test_add_context_method(self):
        """Test adding context to exception."""
        exc = VPrismException(
            message="Test error", 
            error_code=ErrorCode.VALIDATION_ERROR,
            auto_log=False
        )

        exc.add_context("user_id", "12345")
        exc.add_context("operation", "data_fetch")

        assert exc.details["user_id"] == "12345"
        assert exc.details["operation"] == "data_fetch"

    def test_with_cause_method(self):
        """Test adding cause to exception."""
        original_error = ValueError("Original error")
        exc = VPrismException(
            message="Test error", 
            error_code=ErrorCode.VALIDATION_ERROR,
            auto_log=False
        )

        exc.with_cause(original_error)

        assert exc.cause == original_error
        assert "cause_type" in exc.details
        assert "cause_message" in exc.details

    def test_auto_logging(self):
        """Test automatic logging functionality."""
        with patch('vprism.core.exceptions.logger') as mock_logger:
            exc = VPrismException(
                message="Test error",
                error_code=ErrorCode.VALIDATION_ERROR,
                severity=ErrorSeverity.HIGH,
                auto_log=True
            )
            
            # Should have called warning for HIGH severity
            mock_logger.warning.assert_called_once()

    def test_string_error_code_conversion(self):
        """Test conversion of string error codes to ErrorCode enum."""
        exc = VPrismException(
            message="Test error",
            error_code="VALIDATION_ERROR",
            auto_log=False
        )
        
        assert exc.error_code == ErrorCode.VALIDATION_ERROR

    def test_invalid_string_error_code(self):
        """Test handling of invalid string error codes."""
        exc = VPrismException(
            message="Test error",
            error_code="INVALID_CODE",
            auto_log=False
        )
        
        assert exc.error_code == ErrorCode.UNKNOWN_ERROR


class TestValidationException:
    """Test ValidationException class."""

    def test_basic_validation_exception(self):
        """Test creating a basic validation exception."""
        exc = ValidationException("Invalid value", auto_log=False)

        assert exc.message == "Invalid value"
        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        # Details now includes system fields
        assert "timestamp" in exc.details
        assert "trace_id" in exc.details

    def test_validation_exception_with_field(self):
        """Test validation exception with field information."""
        exc = ValidationException(
            message="Invalid email format", field="email", value="invalid-email", auto_log=False
        )

        assert exc.message == "Invalid email format"
        assert exc.error_code == ErrorCode.VALIDATION_ERROR
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


class TestErrorMessages:
    """Test ErrorMessages internationalization."""

    def test_get_message_english(self):
        """Test getting English error messages."""
        message = ErrorMessages.get_message(ErrorCode.VALIDATION_ERROR, "en")
        assert message == "Validation failed"

    def test_get_message_chinese(self):
        """Test getting Chinese error messages."""
        message = ErrorMessages.get_message(ErrorCode.VALIDATION_ERROR, "zh")
        assert message == "验证失败"

    def test_get_message_spanish(self):
        """Test getting Spanish error messages."""
        message = ErrorMessages.get_message(ErrorCode.VALIDATION_ERROR, "es")
        assert message == "Falló la validación"

    def test_get_message_unsupported_language(self):
        """Test getting message for unsupported language falls back to English."""
        message = ErrorMessages.get_message(ErrorCode.VALIDATION_ERROR, "fr")
        assert message == "Validation failed"  # Falls back to English

    def test_add_language(self):
        """Test adding a new language."""
        french_messages = {
            ErrorCode.VALIDATION_ERROR: "Échec de la validation"
        }
        ErrorMessages.add_language("fr", french_messages)
        
        message = ErrorMessages.get_message(ErrorCode.VALIDATION_ERROR, "fr")
        assert message == "Échec de la validation"

    def test_get_supported_languages(self):
        """Test getting list of supported languages."""
        languages = ErrorMessages.get_supported_languages()
        assert "en" in languages
        assert "zh" in languages
        assert "es" in languages

    def test_format_message(self):
        """Test formatting messages with parameters."""
        # Add a parameterized message for testing
        ErrorMessages.add_language("test", {
            ErrorCode.VALIDATION_ERROR: "Field {field} failed validation with value {value}"
        })
        
        message = ErrorMessages.format_message(
            ErrorCode.VALIDATION_ERROR, 
            "test", 
            field="email", 
            value="invalid"
        )
        assert message == "Field email failed validation with value invalid"


class TestErrorTracker:
    """Test ErrorTracker functionality."""

    def test_record_error(self):
        """Test recording errors."""
        tracker = ErrorTracker()
        
        tracker.record_error("TEST_ERROR", {"detail": "test"})
        tracker.record_error("TEST_ERROR", {"detail": "test2"})
        tracker.record_error("OTHER_ERROR", {"detail": "other"})
        
        stats = tracker.get_error_stats()
        assert stats["total_errors"] == 3
        assert stats["error_counts"]["TEST_ERROR"] == 2
        assert stats["error_counts"]["OTHER_ERROR"] == 1
        assert len(stats["recent_errors"]) == 3

    def test_clear_stats(self):
        """Test clearing error statistics."""
        tracker = ErrorTracker()
        
        tracker.record_error("TEST_ERROR", {"detail": "test"})
        tracker.clear_stats()
        
        stats = tracker.get_error_stats()
        assert stats["total_errors"] == 0
        assert len(stats["error_counts"]) == 0
        assert len(stats["recent_errors"]) == 0

    def test_error_history_limit(self):
        """Test that error history is limited to prevent memory issues."""
        tracker = ErrorTracker()
        
        # Record more than 1000 errors
        for i in range(1100):
            tracker.record_error(f"ERROR_{i}", {"detail": f"test{i}"})
        
        stats = tracker.get_error_stats()
        # Should be limited to 1000
        assert len(tracker._error_history) == 1000


class TestContextManagement:
    """Test request context management."""

    def test_set_and_get_request_context(self):
        """Test setting and getting request context."""
        clear_request_context()
        
        set_request_context(user_id="12345", operation="test")
        context = get_request_context()
        
        assert context["user_id"] == "12345"
        assert context["operation"] == "test"

    def test_clear_request_context(self):
        """Test clearing request context."""
        set_request_context(user_id="12345")
        clear_request_context()
        
        context = get_request_context()
        assert len(context) == 0

    def test_exception_context_manager(self):
        """Test ExceptionContext context manager."""
        clear_request_context()
        
        with ExceptionContext(user_id="12345", operation="test"):
            context = get_request_context()
            assert context["user_id"] == "12345"
            assert context["operation"] == "test"
        
        # Context should be cleared after exiting
        context = get_request_context()
        assert len(context) == 0

    def test_exception_context_manager_nested(self):
        """Test nested ExceptionContext managers."""
        clear_request_context()
        set_request_context(base="value")
        
        with ExceptionContext(user_id="12345"):
            with ExceptionContext(operation="test"):
                context = get_request_context()
                assert context["base"] == "value"
                assert context["user_id"] == "12345"
                assert context["operation"] == "test"
            
            context = get_request_context()
            assert context["base"] == "value"
            assert context["user_id"] == "12345"
            assert "operation" not in context
        
        context = get_request_context()
        assert context["base"] == "value"
        assert "user_id" not in context


class TestUtilityFunctions:
    """Test utility functions."""

    def test_handle_exception_chain_vprism_exception(self):
        """Test handling VPrismException (should return as-is)."""
        original = VPrismException("Test", ErrorCode.VALIDATION_ERROR, auto_log=False)
        result = handle_exception_chain(original)
        
        assert result is original

    def test_handle_exception_chain_value_error(self):
        """Test handling ValueError."""
        original = ValueError("Invalid value")
        result = handle_exception_chain(original)
        
        assert isinstance(result, VPrismException)
        assert result.error_code == ErrorCode.VALIDATION_ERROR
        assert result.cause == original
        assert "original_exception_type" in result.details

    def test_handle_exception_chain_connection_error(self):
        """Test handling ConnectionError."""
        original = ConnectionError("Connection failed")
        result = handle_exception_chain(original)
        
        assert isinstance(result, VPrismException)
        assert result.error_code == ErrorCode.CONNECTION_ERROR
        assert result.cause == original

    def test_handle_exception_chain_unknown_error(self):
        """Test handling unknown exception type."""
        class CustomError(Exception):
            pass
        
        original = CustomError("Custom error")
        result = handle_exception_chain(original)
        
        assert isinstance(result, VPrismException)
        assert result.error_code == ErrorCode.INTERNAL_ERROR
        assert result.cause == original

    def test_create_error_response_basic(self):
        """Test creating basic error response."""
        exc = VPrismException(
            "Test error", 
            ErrorCode.VALIDATION_ERROR,
            auto_log=False
        )
        
        response = create_error_response(exc, include_debug=False)
        
        assert response["success"] is False
        assert response["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert response["error"]["message"] == "Test error"
        assert "trace_id" in response["error"]
        assert "timestamp" in response["error"]
        assert "details" not in response["error"]

    def test_create_error_response_with_debug(self):
        """Test creating error response with debug information."""
        exc = VPrismException(
            "Test error",
            ErrorCode.VALIDATION_ERROR,
            details={"field": "test"},
            cause=ValueError("Original"),
            severity=ErrorSeverity.HIGH,
            auto_log=False
        )
        
        response = create_error_response(exc, include_debug=True)
        
        assert response["success"] is False
        assert "details" in response["error"]
        assert "severity" in response["error"]
        assert "cause" in response["error"]

    def test_get_and_clear_error_stats(self):
        """Test global error statistics functions."""
        clear_error_stats()
        
        # Create an exception to trigger error recording
        VPrismException("Test", ErrorCode.VALIDATION_ERROR, auto_log=True)
        
        stats = get_error_stats()
        assert stats["total_errors"] > 0
        
        clear_error_stats()
        stats = get_error_stats()
        assert stats["total_errors"] == 0


class TestExceptionLogging:
    """Test exception logging functionality."""

    @patch('vprism.core.exceptions.logger')
    def test_logging_with_context(self, mock_logger):
        """Test that exceptions log with request context."""
        clear_request_context()
        set_request_context(user_id="12345", operation="test")
        
        exc = VPrismException(
            "Test error",
            ErrorCode.VALIDATION_ERROR,
            severity=ErrorSeverity.MEDIUM,
            auto_log=True
        )
        
        # Should have logged with context
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "context" in call_args[1]
        assert call_args[1]["context"]["user_id"] == "12345"

    @patch('vprism.core.exceptions.logger')
    def test_logging_severity_levels(self, mock_logger):
        """Test different logging severity levels."""
        # Test LOW severity
        VPrismException(
            "Low error",
            ErrorCode.VALIDATION_ERROR,
            severity=ErrorSeverity.LOW,
            auto_log=True
        )
        mock_logger.debug.assert_called_once()
        
        # Test CRITICAL severity
        VPrismException(
            "Critical error",
            ErrorCode.INTERNAL_ERROR,
            severity=ErrorSeverity.CRITICAL,
            auto_log=True
        )
        mock_logger.error.assert_called_once()

    @patch('vprism.core.exceptions.logger')
    def test_logging_includes_stack_trace_for_high_severity(self, mock_logger):
        """Test that high severity errors include stack trace."""
        VPrismException(
            "High error",
            ErrorCode.INTERNAL_ERROR,
            severity=ErrorSeverity.HIGH,
            auto_log=True
        )
        
        call_args = mock_logger.warning.call_args
        assert "stack_trace" in call_args[1]
