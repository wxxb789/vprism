"""
Core exception classes for vprism.

This module defines the exception hierarchy used throughout the platform,
providing structured error handling and debugging information.
"""

import json
import traceback
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from contextvars import ContextVar

from loguru import logger


class ErrorCode(str, Enum):
    """Standardized error codes for vprism exceptions."""
    
    # General errors
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    
    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DATA_VALIDATION_ERROR = "DATA_VALIDATION_ERROR"
    QUERY_VALIDATION_ERROR = "QUERY_VALIDATION_ERROR"
    
    # Provider errors
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    
    # Data errors
    DATA_NOT_FOUND = "DATA_NOT_FOUND"
    DATA_CORRUPTED = "DATA_CORRUPTED"
    DATA_FORMAT_ERROR = "DATA_FORMAT_ERROR"
    
    # Configuration errors
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    MISSING_CONFIGURATION = "MISSING_CONFIGURATION"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    
    # Network errors
    NETWORK_ERROR = "NETWORK_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    
    # Cache errors
    CACHE_ERROR = "CACHE_ERROR"
    CACHE_MISS = "CACHE_MISS"
    CACHE_WRITE_ERROR = "CACHE_WRITE_ERROR"
    
    # Service errors
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    NO_PROVIDER_AVAILABLE = "NO_PROVIDER_AVAILABLE"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"


class ErrorSeverity(str, Enum):
    """Error severity levels for logging and monitoring."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Context variable for tracking request/operation context
_request_context: ContextVar[Dict[str, Any]] = ContextVar('request_context', default={})


class ErrorTracker:
    """Tracks error patterns and provides analytics."""
    
    def __init__(self):
        self._error_counts: Dict[str, int] = {}
        self._error_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
    
    def record_error(self, error_code: str, details: Dict[str, Any]) -> None:
        """Record an error occurrence."""
        with self._lock:
            self._error_counts[error_code] = self._error_counts.get(error_code, 0) + 1
            self._error_history.append({
                "error_code": error_code,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details
            })
            
            # Keep only last 1000 errors to prevent memory issues
            if len(self._error_history) > 1000:
                self._error_history = self._error_history[-1000:]
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        with self._lock:
            return {
                "total_errors": sum(self._error_counts.values()),
                "error_counts": self._error_counts.copy(),
                "recent_errors": self._error_history[-10:] if self._error_history else []
            }
    
    def clear_stats(self) -> None:
        """Clear error statistics."""
        with self._lock:
            self._error_counts.clear()
            self._error_history.clear()


# Global error tracker instance
_error_tracker = ErrorTracker()


class ErrorMessages:
    """Centralized error messages with internationalization support."""
    
    # Default language is English
    _messages = {
        "en": {
            ErrorCode.UNKNOWN_ERROR: "An unknown error occurred",
            ErrorCode.INTERNAL_ERROR: "An internal error occurred",
            ErrorCode.VALIDATION_ERROR: "Validation failed",
            ErrorCode.DATA_VALIDATION_ERROR: "Data validation failed",
            ErrorCode.QUERY_VALIDATION_ERROR: "Query validation failed",
            ErrorCode.PROVIDER_ERROR: "Provider error occurred",
            ErrorCode.PROVIDER_UNAVAILABLE: "Provider is unavailable",
            ErrorCode.PROVIDER_TIMEOUT: "Provider request timed out",
            ErrorCode.RATE_LIMIT_EXCEEDED: "Rate limit exceeded",
            ErrorCode.AUTHENTICATION_FAILED: "Authentication failed",
            ErrorCode.AUTHORIZATION_FAILED: "Authorization failed",
            ErrorCode.DATA_NOT_FOUND: "Requested data not found",
            ErrorCode.DATA_CORRUPTED: "Data is corrupted",
            ErrorCode.DATA_FORMAT_ERROR: "Data format error",
            ErrorCode.CONFIGURATION_ERROR: "Configuration error",
            ErrorCode.MISSING_CONFIGURATION: "Missing required configuration",
            ErrorCode.INVALID_CONFIGURATION: "Invalid configuration",
            ErrorCode.NETWORK_ERROR: "Network error occurred",
            ErrorCode.CONNECTION_ERROR: "Connection error",
            ErrorCode.TIMEOUT_ERROR: "Operation timed out",
            ErrorCode.CACHE_ERROR: "Cache error occurred",
            ErrorCode.CACHE_MISS: "Cache miss",
            ErrorCode.CACHE_WRITE_ERROR: "Cache write error",
            ErrorCode.SERVICE_UNAVAILABLE: "Service is unavailable",
            ErrorCode.NO_PROVIDER_AVAILABLE: "No available data provider",
            ErrorCode.CIRCUIT_BREAKER_OPEN: "Circuit breaker is open",
        },
        "zh": {
            ErrorCode.UNKNOWN_ERROR: "发生未知错误",
            ErrorCode.INTERNAL_ERROR: "发生内部错误",
            ErrorCode.VALIDATION_ERROR: "验证失败",
            ErrorCode.DATA_VALIDATION_ERROR: "数据验证失败",
            ErrorCode.QUERY_VALIDATION_ERROR: "查询验证失败",
            ErrorCode.PROVIDER_ERROR: "数据提供商错误",
            ErrorCode.PROVIDER_UNAVAILABLE: "数据提供商不可用",
            ErrorCode.PROVIDER_TIMEOUT: "数据提供商请求超时",
            ErrorCode.RATE_LIMIT_EXCEEDED: "超出速率限制",
            ErrorCode.AUTHENTICATION_FAILED: "身份验证失败",
            ErrorCode.AUTHORIZATION_FAILED: "授权失败",
            ErrorCode.DATA_NOT_FOUND: "未找到请求的数据",
            ErrorCode.DATA_CORRUPTED: "数据已损坏",
            ErrorCode.DATA_FORMAT_ERROR: "数据格式错误",
            ErrorCode.CONFIGURATION_ERROR: "配置错误",
            ErrorCode.MISSING_CONFIGURATION: "缺少必需的配置",
            ErrorCode.INVALID_CONFIGURATION: "无效配置",
            ErrorCode.NETWORK_ERROR: "网络错误",
            ErrorCode.CONNECTION_ERROR: "连接错误",
            ErrorCode.TIMEOUT_ERROR: "操作超时",
            ErrorCode.CACHE_ERROR: "缓存错误",
            ErrorCode.CACHE_MISS: "缓存未命中",
            ErrorCode.CACHE_WRITE_ERROR: "缓存写入错误",
            ErrorCode.SERVICE_UNAVAILABLE: "服务不可用",
            ErrorCode.NO_PROVIDER_AVAILABLE: "没有可用的数据提供商",
            ErrorCode.CIRCUIT_BREAKER_OPEN: "熔断器已打开",
        },
        "es": {
            ErrorCode.UNKNOWN_ERROR: "Ocurrió un error desconocido",
            ErrorCode.INTERNAL_ERROR: "Ocurrió un error interno",
            ErrorCode.VALIDATION_ERROR: "Falló la validación",
            ErrorCode.DATA_VALIDATION_ERROR: "Falló la validación de datos",
            ErrorCode.QUERY_VALIDATION_ERROR: "Falló la validación de consulta",
            ErrorCode.PROVIDER_ERROR: "Ocurrió un error del proveedor",
            ErrorCode.PROVIDER_UNAVAILABLE: "El proveedor no está disponible",
            ErrorCode.PROVIDER_TIMEOUT: "Tiempo de espera del proveedor agotado",
            ErrorCode.RATE_LIMIT_EXCEEDED: "Límite de velocidad excedido",
            ErrorCode.AUTHENTICATION_FAILED: "Falló la autenticación",
            ErrorCode.AUTHORIZATION_FAILED: "Falló la autorización",
            ErrorCode.DATA_NOT_FOUND: "Datos solicitados no encontrados",
            ErrorCode.DATA_CORRUPTED: "Los datos están corruptos",
            ErrorCode.DATA_FORMAT_ERROR: "Error de formato de datos",
            ErrorCode.CONFIGURATION_ERROR: "Error de configuración",
            ErrorCode.MISSING_CONFIGURATION: "Configuración requerida faltante",
            ErrorCode.INVALID_CONFIGURATION: "Configuración inválida",
            ErrorCode.NETWORK_ERROR: "Ocurrió un error de red",
            ErrorCode.CONNECTION_ERROR: "Error de conexión",
            ErrorCode.TIMEOUT_ERROR: "Operación agotó tiempo de espera",
            ErrorCode.CACHE_ERROR: "Ocurrió un error de caché",
            ErrorCode.CACHE_MISS: "Fallo de caché",
            ErrorCode.CACHE_WRITE_ERROR: "Error de escritura de caché",
            ErrorCode.SERVICE_UNAVAILABLE: "El servicio no está disponible",
            ErrorCode.NO_PROVIDER_AVAILABLE: "No hay proveedor de datos disponible",
            ErrorCode.CIRCUIT_BREAKER_OPEN: "El cortacircuitos está abierto",
        }
    }
    
    @classmethod
    def get_message(cls, error_code: ErrorCode, language: str = "en") -> str:
        """Get localized error message."""
        messages = cls._messages.get(language, cls._messages["en"])
        return messages.get(error_code, str(error_code))
    
    @classmethod
    def add_language(cls, language: str, messages: Dict[ErrorCode, str]) -> None:
        """Add messages for a new language."""
        cls._messages[language] = messages
    
    @classmethod
    def get_supported_languages(cls) -> List[str]:
        """Get list of supported languages."""
        return list(cls._messages.keys())
    
    @classmethod
    def format_message(cls, error_code: ErrorCode, language: str = "en", **kwargs) -> str:
        """Format error message with parameters."""
        message = cls.get_message(error_code, language)
        try:
            return message.format(**kwargs)
        except (KeyError, ValueError):
            return message


class VPrismException(Exception):
    """
    Base exception class for all vprism errors.

    Provides structured error information including error codes,
    messages, and additional context for debugging.
    """

    def __init__(
        self,
        message: Optional[str] = None,
        error_code: Union[ErrorCode, str] = ErrorCode.UNKNOWN_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        language: str = "en",
        auto_log: bool = True,
    ) -> None:
        """
        Initialize VPrismException.

        Args:
            message: Human-readable error message (auto-generated if None)
            error_code: Structured error code for programmatic handling
            details: Additional error context and debugging information
            cause: Original exception that caused this error
            severity: Error severity level for logging and monitoring
            language: Language for error message localization
            auto_log: Whether to automatically log the exception
        """
        # Convert string error codes to ErrorCode enum
        if isinstance(error_code, str):
            try:
                error_code = ErrorCode(error_code)
            except ValueError:
                error_code = ErrorCode.UNKNOWN_ERROR
        
        self.error_code = error_code
        self.message = message or ErrorMessages.get_message(error_code, language)
        self.details = details or {}
        self.cause = cause
        self.severity = severity
        self.language = language
        self.timestamp = datetime.now(timezone.utc)
        self.trace_id = self._generate_trace_id()
        
        # Add system context to details
        self.details.update({
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "severity": self.severity.value,
            "error_code": self.error_code.value,
        })
        
        # Add traceback information if there's a cause
        if cause:
            self.details["cause_type"] = type(cause).__name__
            self.details["cause_message"] = str(cause)
            self.details["traceback"] = traceback.format_exception(
                type(cause), cause, cause.__traceback__
            )
        
        super().__init__(self.message)
        
        # Auto-log the exception if enabled
        if auto_log:
            self._log_exception()

    def _generate_trace_id(self) -> str:
        """Generate a unique trace ID for this exception."""
        import uuid
        return str(uuid.uuid4())[:8]

    def _log_exception(self) -> None:
        """Log the exception with appropriate severity level and structured data."""
        # Get current request context if available
        context = _request_context.get({})
        
        log_data = {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "trace_id": self.trace_id,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "context": context,
        }
        
        # Add stack trace for higher severity errors
        if self.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            log_data["stack_trace"] = traceback.format_stack()
        
        # Record error in tracker
        _error_tracker.record_error(self.error_code.value, {
            "message": self.message,
            "details": self.details,
            "severity": self.severity.value,
            "context": context,
        })
        
        if self.severity == ErrorSeverity.LOW:
            logger.debug("VPrism exception occurred", **log_data)
        elif self.severity == ErrorSeverity.MEDIUM:
            logger.info("VPrism exception occurred", **log_data)
        elif self.severity == ErrorSeverity.HIGH:
            logger.warning("VPrism exception occurred", **log_data)
        elif self.severity == ErrorSeverity.CRITICAL:
            logger.error("VPrism exception occurred", **log_data)

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Convert exception to dictionary for serialization.
        
        Args:
            include_sensitive: Whether to include potentially sensitive information
        """
        result = {
            "error": self.error_code.value,
            "message": self.message,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "language": self.language,
        }
        
        # Filter details based on sensitivity
        if include_sensitive:
            result["details"] = self.details
            result["cause"] = str(self.cause) if self.cause else None
        else:
            # Filter out potentially sensitive keys
            sensitive_keys = {"api_key", "password", "token", "secret", "auth", "credentials"}
            filtered_details = {}
            for key, value in self.details.items():
                if not any(sensitive in key.lower() for sensitive in sensitive_keys):
                    filtered_details[key] = value
                else:
                    filtered_details[key] = "[REDACTED]"
            result["details"] = filtered_details
            result["cause"] = "[REDACTED]" if self.cause else None
        
        return result

    def to_json(self, include_sensitive: bool = False, indent: Optional[int] = None) -> str:
        """
        Convert exception to JSON string.
        
        Args:
            include_sensitive: Whether to include potentially sensitive information
            indent: JSON indentation for pretty printing
        """
        return json.dumps(
            self.to_dict(include_sensitive=include_sensitive), 
            default=str, 
            ensure_ascii=False,
            indent=indent
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VPrismException":
        """Create exception from dictionary."""
        try:
            error_code = ErrorCode(data.get("error", ErrorCode.UNKNOWN_ERROR))
        except ValueError:
            error_code = ErrorCode.UNKNOWN_ERROR
        
        try:
            severity = ErrorSeverity(data.get("severity", ErrorSeverity.MEDIUM))
        except ValueError:
            severity = ErrorSeverity.MEDIUM
        
        # Extract details and remove system fields
        details = data.get("details", {}).copy()
        for key in ["timestamp", "trace_id", "severity", "error_code"]:
            details.pop(key, None)
        
        return cls(
            message=data.get("message"),
            error_code=error_code,
            details=details,
            severity=severity,
            language=data.get("language", "en"),
            auto_log=False,  # Don't auto-log when deserializing
        )

    @classmethod
    def from_json(cls, json_str: str) -> "VPrismException":
        """Create exception from JSON string."""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # If deserialization fails, create a generic exception
            return cls(
                message=f"Failed to deserialize exception: {e}",
                error_code=ErrorCode.INTERNAL_ERROR,
                details={"original_json": json_str},
                auto_log=False
            )

    def add_context(self, key: str, value: Any) -> "VPrismException":
        """Add additional context to the exception."""
        self.details[key] = value
        return self

    def with_cause(self, cause: Exception) -> "VPrismException":
        """Add a cause to the exception."""
        self.cause = cause
        self.details["cause_type"] = type(cause).__name__
        self.details["cause_message"] = str(cause)
        return self


class ValidationException(VPrismException):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: Optional[str] = None,
        field: Optional[str] = None,
        value: Any = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if field:
            error_details["field"] = field
        if value is not None:
            error_details["value"] = str(value)

        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details=error_details,
            **kwargs,
        )


class DataValidationException(ValidationException):
    """Raised when data or query validation fails."""

    def __init__(
        self,
        message: Optional[str] = None,
        field: Optional[str] = None,
        value: Any = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            message=message,
            field=field,
            value=value,
            details=details,
            error_code=ErrorCode.DATA_VALIDATION_ERROR,
            **kwargs,
        )


class QueryValidationException(ValidationException):
    """Raised when query validation fails."""

    def __init__(
        self,
        message: Optional[str] = None,
        field: Optional[str] = None,
        value: Any = None,
        query_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if query_type:
            error_details["query_type"] = query_type
            
        super().__init__(
            message=message,
            field=field,
            value=value,
            details=error_details,
            **kwargs,
        )
        # Override error code after initialization
        self.error_code = ErrorCode.QUERY_VALIDATION_ERROR


class ProviderException(VPrismException):
    """Base class for data provider related errors."""

    def __init__(
        self,
        message: Optional[str] = None,
        provider: Optional[str] = None,
        error_code: Union[ErrorCode, str] = ErrorCode.PROVIDER_ERROR,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if provider:
            error_details["provider"] = provider

        super().__init__(
            message=message,
            error_code=error_code,
            details=error_details,
            **kwargs,
        )


class RateLimitException(ProviderException):
    """Raised when rate limits are exceeded."""

    def __init__(
        self,
        provider: Optional[str] = None,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if retry_after:
            error_details["retry_after_seconds"] = retry_after

        message = None
        if provider:
            message = f"Rate limit exceeded for provider {provider}"
            if retry_after:
                message += f". Retry after {retry_after} seconds"

        super().__init__(
            message=message,
            provider=provider,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            details=error_details,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


class AuthenticationException(ProviderException):
    """Raised when authentication with a provider fails."""

    def __init__(
        self,
        provider: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        message = None
        if provider:
            message = f"Authentication failed for provider {provider}"

        super().__init__(
            message=message,
            provider=provider,
            error_code=ErrorCode.AUTHENTICATION_FAILED,
            details=details,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


class AuthorizationException(ProviderException):
    """Raised when authorization with a provider fails."""

    def __init__(
        self,
        provider: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if resource:
            error_details["resource"] = resource
            
        message = None
        if provider:
            message = f"Authorization failed for provider {provider}"
            if resource:
                message += f" accessing resource {resource}"

        super().__init__(
            message=message,
            provider=provider,
            error_code=ErrorCode.AUTHORIZATION_FAILED,
            details=error_details,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


class DataNotFoundException(VPrismException):
    """Raised when requested data is not found."""

    def __init__(
        self,
        message: Optional[str] = None,
        query: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if query:
            error_details["query"] = query

        super().__init__(
            message=message,
            error_code=ErrorCode.DATA_NOT_FOUND,
            details=error_details,
            severity=ErrorSeverity.LOW,
            **kwargs,
        )


class DataCorruptedException(VPrismException):
    """Raised when data is corrupted or invalid."""

    def __init__(
        self,
        message: Optional[str] = None,
        data_source: Optional[str] = None,
        corruption_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if data_source:
            error_details["data_source"] = data_source
        if corruption_type:
            error_details["corruption_type"] = corruption_type

        super().__init__(
            message=message,
            error_code=ErrorCode.DATA_CORRUPTED,
            details=error_details,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


class DataFormatException(VPrismException):
    """Raised when data format is invalid or unexpected."""

    def __init__(
        self,
        message: Optional[str] = None,
        expected_format: Optional[str] = None,
        actual_format: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if expected_format:
            error_details["expected_format"] = expected_format
        if actual_format:
            error_details["actual_format"] = actual_format

        super().__init__(
            message=message,
            error_code=ErrorCode.DATA_FORMAT_ERROR,
            details=error_details,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )


class ConfigurationException(VPrismException):
    """Raised when configuration is invalid or missing."""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key

        super().__init__(
            message=message, error_code=ErrorCode.CONFIGURATION_ERROR, details=error_details, **kwargs
        )


class MissingConfigurationException(ConfigurationException):
    """Raised when required configuration is missing."""

    def __init__(
        self,
        config_key: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        if not message:
            message = f"Missing required configuration: {config_key}"
            
        super().__init__(
            message=message,
            config_key=config_key,
            details=details,
            **kwargs,
        )
        # Override error code for missing configuration
        self.error_code = ErrorCode.MISSING_CONFIGURATION


class InvalidConfigurationException(ConfigurationException):
    """Raised when configuration is invalid."""

    def __init__(
        self,
        config_key: str,
        config_value: Any = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if config_value is not None:
            error_details["config_value"] = str(config_value)
            
        if not message:
            message = f"Invalid configuration for key: {config_key}"
            
        super().__init__(
            message=message,
            config_key=config_key,
            details=error_details,
            **kwargs,
        )
        # Override error code for invalid configuration
        self.error_code = ErrorCode.INVALID_CONFIGURATION


class CacheException(VPrismException):
    """Raised when cache operations fail."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if operation:
            error_details["operation"] = operation

        super().__init__(
            message=message,
            error_code=ErrorCode.CACHE_ERROR,
            details=error_details,
            cause=cause,
            **kwargs,
        )


class CacheMissException(CacheException):
    """Raised when cache miss occurs."""

    def __init__(
        self,
        cache_key: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        error_details["cache_key"] = cache_key
        
        if not message:
            message = f"Cache miss for key: {cache_key}"

        super().__init__(
            message=message,
            operation="get",
            details=error_details,
            **kwargs,
        )
        # Override error code for cache miss
        self.error_code = ErrorCode.CACHE_MISS


class CacheWriteException(CacheException):
    """Raised when cache write operations fail."""

    def __init__(
        self,
        cache_key: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        error_details["cache_key"] = cache_key
        
        if not message:
            message = f"Failed to write to cache for key: {cache_key}"

        super().__init__(
            message=message,
            operation="set",
            details=error_details,
            cause=cause,
            **kwargs,
        )
        # Override error code for cache write error
        self.error_code = ErrorCode.CACHE_WRITE_ERROR


class NetworkException(VPrismException):
    """Raised when network operations fail."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if url:
            error_details["url"] = url
        if status_code:
            error_details["status_code"] = status_code

        super().__init__(
            message=message,
            error_code=ErrorCode.NETWORK_ERROR,
            details=error_details,
            cause=cause,
            **kwargs,
        )


class ConnectionException(NetworkException):
    """Raised when connection operations fail."""

    def __init__(
        self,
        message: str = "Connection failed",
        host: str | None = None,
        port: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if host:
            error_details["host"] = host
        if port:
            error_details["port"] = port

        super().__init__(
            message=message,
            details=error_details,
            cause=cause,
            **kwargs,
        )
        # Override error code for connection-specific errors
        self.error_code = ErrorCode.CONNECTION_ERROR


class TimeoutException(VPrismException):
    """Raised when operations timeout."""

    def __init__(
        self,
        message: str = "Operation timed out",
        timeout_seconds: float | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if timeout_seconds:
            error_details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message, error_code=ErrorCode.TIMEOUT_ERROR, details=error_details, **kwargs
        )


class NoAvailableProviderException(VPrismException):
    """Raised when no suitable data provider is available."""

    def __init__(
        self,
        message: str = "No available data provider for request",
        query: str | None = None,
        attempted_providers: list[str] | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if query:
            error_details["query"] = query
        if attempted_providers:
            error_details["attempted_providers"] = attempted_providers

        super().__init__(
            message=message, error_code=ErrorCode.NO_PROVIDER_AVAILABLE, details=error_details, **kwargs
        )


class ServiceUnavailableException(VPrismException):
    """Raised when a service is unavailable."""

    def __init__(
        self,
        service_name: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if service_name:
            error_details["service_name"] = service_name
            
        if not message:
            message = f"Service unavailable: {service_name}" if service_name else "Service unavailable"

        super().__init__(
            message=message,
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            details=error_details,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


class CircuitBreakerException(VPrismException):
    """Raised when circuit breaker is open."""

    def __init__(
        self,
        service_name: str | None = None,
        failure_count: int | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if service_name:
            error_details["service_name"] = service_name
        if failure_count is not None:
            error_details["failure_count"] = failure_count
            
        if not message:
            message = f"Circuit breaker open for service: {service_name}" if service_name else "Circuit breaker is open"

        super().__init__(
            message=message,
            error_code=ErrorCode.CIRCUIT_BREAKER_OPEN,
            details=error_details,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


# Utility functions for exception handling

def set_request_context(**context: Any) -> None:
    """Set context information for the current request/operation."""
    current_context = _request_context.get({})
    current_context.update(context)
    _request_context.set(current_context)


def get_request_context() -> Dict[str, Any]:
    """Get current request context."""
    return _request_context.get({})


def clear_request_context() -> None:
    """Clear current request context."""
    _request_context.set({})


def get_error_stats() -> Dict[str, Any]:
    """Get global error statistics."""
    return _error_tracker.get_error_stats()


def clear_error_stats() -> None:
    """Clear global error statistics."""
    _error_tracker.clear_stats()


class ExceptionContext:
    """Context manager for setting request context."""
    
    def __init__(self, **context: Any):
        self.context = context
        self.previous_context = None
    
    def __enter__(self):
        self.previous_context = _request_context.get({})
        new_context = self.previous_context.copy()
        new_context.update(self.context)
        _request_context.set(new_context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        _request_context.set(self.previous_context or {})


def handle_exception_chain(exception: Exception) -> VPrismException:
    """
    Convert any exception to a VPrismException, preserving the chain.
    
    This function is useful for wrapping third-party exceptions in our
    structured exception format while maintaining the original cause.
    """
    if isinstance(exception, VPrismException):
        return exception
    
    # Map common exception types to appropriate error codes
    error_code_mapping = {
        ValueError: ErrorCode.VALIDATION_ERROR,
        TypeError: ErrorCode.VALIDATION_ERROR,
        KeyError: ErrorCode.DATA_NOT_FOUND,
        FileNotFoundError: ErrorCode.DATA_NOT_FOUND,
        ConnectionError: ErrorCode.CONNECTION_ERROR,
        TimeoutError: ErrorCode.TIMEOUT_ERROR,
        PermissionError: ErrorCode.AUTHORIZATION_FAILED,
    }
    
    error_code = error_code_mapping.get(type(exception), ErrorCode.INTERNAL_ERROR)
    
    return VPrismException(
        message=str(exception),
        error_code=error_code,
        cause=exception,
        details={
            "original_exception_type": type(exception).__name__,
            "original_exception_module": type(exception).__module__,
        }
    )


def create_error_response(exception: VPrismException, include_debug: bool = False) -> Dict[str, Any]:
    """
    Create a standardized error response dictionary.
    
    Args:
        exception: The VPrismException to convert
        include_debug: Whether to include debug information
    
    Returns:
        Standardized error response dictionary
    """
    response = {
        "success": False,
        "error": {
            "code": exception.error_code.value,
            "message": exception.message,
            "trace_id": exception.trace_id,
            "timestamp": exception.timestamp.isoformat(),
        }
    }
    
    if include_debug:
        response["error"]["details"] = exception.details
        response["error"]["severity"] = exception.severity.value
        if exception.cause:
            response["error"]["cause"] = str(exception.cause)
    
    return response


def wrap_async_exception(func):
    """
    Decorator to wrap async functions and convert exceptions to VPrismException.
    
    Usage:
        @wrap_async_exception
        async def my_function():
            # Function that might raise exceptions
            pass
    """
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except VPrismException:
            # Re-raise VPrism exceptions as-is
            raise
        except Exception as e:
            # Convert other exceptions to VPrismException
            raise handle_exception_chain(e)
    
    return wrapper


def wrap_sync_exception(func):
    """
    Decorator to wrap sync functions and convert exceptions to VPrismException.
    
    Usage:
        @wrap_sync_exception
        def my_function():
            # Function that might raise exceptions
            pass
    """
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except VPrismException:
            # Re-raise VPrism exceptions as-is
            raise
        except Exception as e:
            # Convert other exceptions to VPrismException
            raise handle_exception_chain(e)
    
    return wrapper


def log_exception_metrics(exception: VPrismException) -> None:
    """
    Log exception metrics for monitoring and alerting.
    
    This function can be extended to integrate with monitoring systems
    like Prometheus, DataDog, etc.
    """
    metrics_data = {
        "error_code": exception.error_code.value,
        "severity": exception.severity.value,
        "timestamp": exception.timestamp.isoformat(),
        "trace_id": exception.trace_id,
    }
    
    # Add provider information if available
    if "provider" in exception.details:
        metrics_data["provider"] = exception.details["provider"]
    
    # Log metrics (can be extended to send to monitoring systems)
    logger.info("Exception metrics", **metrics_data)


def create_exception_summary(exceptions: List[VPrismException]) -> Dict[str, Any]:
    """
    Create a summary of multiple exceptions for batch error reporting.
    
    Args:
        exceptions: List of VPrismException instances
        
    Returns:
        Summary dictionary with aggregated error information
    """
    if not exceptions:
        return {"total_errors": 0, "error_summary": {}}
    
    error_counts = {}
    severity_counts = {}
    provider_errors = {}
    
    for exc in exceptions:
        # Count by error code
        error_counts[exc.error_code.value] = error_counts.get(exc.error_code.value, 0) + 1
        
        # Count by severity
        severity_counts[exc.severity.value] = severity_counts.get(exc.severity.value, 0) + 1
        
        # Count by provider if available
        if "provider" in exc.details:
            provider = exc.details["provider"]
            provider_errors[provider] = provider_errors.get(provider, 0) + 1
    
    return {
        "total_errors": len(exceptions),
        "error_counts": error_counts,
        "severity_counts": severity_counts,
        "provider_errors": provider_errors,
        "time_range": {
            "earliest": min(exc.timestamp for exc in exceptions).isoformat(),
            "latest": max(exc.timestamp for exc in exceptions).isoformat(),
        }
    }


def filter_exceptions_by_severity(
    exceptions: List[VPrismException], 
    min_severity: ErrorSeverity = ErrorSeverity.MEDIUM
) -> List[VPrismException]:
    """
    Filter exceptions by minimum severity level.
    
    Args:
        exceptions: List of exceptions to filter
        min_severity: Minimum severity level to include
        
    Returns:
        Filtered list of exceptions
    """
    severity_order = {
        ErrorSeverity.LOW: 1,
        ErrorSeverity.MEDIUM: 2,
        ErrorSeverity.HIGH: 3,
        ErrorSeverity.CRITICAL: 4,
    }
    
    min_level = severity_order[min_severity]
    
    return [
        exc for exc in exceptions 
        if severity_order.get(exc.severity, 0) >= min_level
    ]


def group_exceptions_by_error_code(exceptions: List[VPrismException]) -> Dict[str, List[VPrismException]]:
    """
    Group exceptions by their error codes.
    
    Args:
        exceptions: List of exceptions to group
        
    Returns:
        Dictionary mapping error codes to lists of exceptions
    """
    grouped = {}
    for exc in exceptions:
        code = exc.error_code.value
        if code not in grouped:
            grouped[code] = []
        grouped[code].append(exc)
    
    return grouped


class CircuitBreakerOpenException(VPrismException):
    """Raised when circuit breaker is open and blocking requests."""

    def __init__(
        self,
        message: Optional[str] = None,
        circuit_breaker_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if circuit_breaker_name:
            error_details["circuit_breaker"] = circuit_breaker_name

        super().__init__(
            message=message,
            error_code=ErrorCode.CIRCUIT_BREAKER_OPEN,
            details=error_details,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


class ServiceUnavailableException(VPrismException):
    """Raised when a service is unavailable."""

    def __init__(
        self,
        message: Optional[str] = None,
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if service_name:
            error_details["service"] = service_name

        super().__init__(
            message=message,
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            details=error_details,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


class TimeoutException(VPrismException):
    """Raised when an operation times out."""

    def __init__(
        self,
        message: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if timeout_seconds:
            error_details["timeout_seconds"] = timeout_seconds
        if operation:
            error_details["operation"] = operation

        super().__init__(
            message=message,
            error_code=ErrorCode.TIMEOUT_ERROR,
            details=error_details,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )


class NoAvailableProviderException(VPrismException):
    """Raised when no data provider is available to handle a request."""

    def __init__(
        self,
        message: Optional[str] = None,
        query: Optional[str] = None,
        attempted_providers: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        error_details = details or {}
        if query:
            error_details["query"] = query
        if attempted_providers:
            error_details["attempted_providers"] = attempted_providers

        super().__init__(
            message=message,
            error_code=ErrorCode.NO_PROVIDER_AVAILABLE,
            details=error_details,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )