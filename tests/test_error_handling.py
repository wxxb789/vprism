"""测试错误处理模块."""

import pytest

from core.exceptions.base import (
    CacheError,
    DataValidationError,
    NetworkError,
    ProviderError,
    RateLimitError,
    VPrismError,
)
from core.exceptions.codes import ErrorCode
from core.exceptions.handler import ErrorContextManager, ErrorHandler, ErrorTracker
from core.exceptions.messages import (
    ErrorContext,
    ErrorMessageTemplate,
    format_error_response,
)


class TestErrorCodes:
    """测试错误代码."""

    def test_error_code_enum(self):
        """测试错误代码枚举."""
        assert ErrorCode.GENERAL_ERROR == "GENERAL_ERROR"
        assert ErrorCode.PROVIDER_ERROR == "PROVIDER_ERROR"
        assert ErrorCode.RATE_LIMIT_ERROR == "RATE_LIMIT_ERROR"


class TestErrorMessageTemplate:
    """测试错误消息模板."""

    def test_get_message_with_valid_template(self):
        """测试获取有效模板消息."""
        message = ErrorMessageTemplate.get_message(ErrorCode.PROVIDER_ERROR, provider="akshare", message="连接失败")
        assert "akshare" in message
        assert "连接失败" in message

    def test_get_message_with_missing_params(self):
        """测试获取缺少参数的模板消息."""
        message = ErrorMessageTemplate.get_message(ErrorCode.PROVIDER_ERROR)
        assert "发生未知错误" in message

    def test_get_message_with_rate_limit(self):
        """测试获取速率限制消息."""
        message = ErrorMessageTemplate.get_message(ErrorCode.RATE_LIMIT_EXCEEDED, retry_after=60)
        assert "60秒" in message


class TestErrorHandler:
    """测试错误处理器."""

    @pytest.fixture
    def error_handler(self):
        """创建错误处理器实例."""
        return ErrorHandler(log_level="DEBUG")

    def test_create_error_response_with_vprism_error(self, error_handler):
        """测试创建VPrismError的错误响应."""
        error = VPrismError("测试错误", ErrorCode.GENERAL_ERROR, {"test": "data"})
        response = error_handler.create_error_response(error)

        assert response["error"]["code"] == ErrorCode.GENERAL_ERROR.value
        assert response["error"]["message"] == "测试错误"
        assert response["error"]["details"]["test"] == "data"

    def test_create_error_response_with_standard_exception(self, error_handler):
        """测试创建标准异常的错误响应."""
        error = ValueError("值错误")
        response = error_handler.create_error_response(error)

        assert response["error"]["code"] == "INTERNAL_ERROR"
        assert "值错误" in response["error"]["message"]

    def test_handle_exception_with_vprism_error(self, error_handler):
        """测试处理VPrismError异常."""
        original_error = VPrismError("原始错误", "ORIGINAL_ERROR")
        handled_error = error_handler.handle_exception(original_error, operation="test_operation")

        assert handled_error is original_error

    def test_handle_exception_with_timeout_error(self, error_handler):
        """测试处理超时异常."""
        timeout_error = TimeoutError("请求超时")
        handled_error = error_handler.handle_exception(timeout_error, operation="fetch_data", provider="akshare")

        assert isinstance(handled_error, ProviderError)
        assert handled_error.provider_name == "akshare"
        assert handled_error.error_code == "PROVIDER_TIMEOUT"

    def test_handle_exception_with_network_error(self, error_handler):
        """测试处理网络异常."""
        network_error = ConnectionError("网络连接失败")
        handled_error = error_handler.handle_exception(network_error, operation="connect", provider="yahoo")

        assert isinstance(handled_error, NetworkError)
        assert handled_error.provider_name == "yahoo"

    def test_handle_exception_with_validation_error(self, error_handler):
        """测试处理验证异常."""
        validation_error = ValueError("数据格式无效")
        handled_error = error_handler.handle_exception(
            validation_error,
            operation="validate_data",
            validation_errors={"field": "required"},
        )

        assert isinstance(handled_error, DataValidationError)
        assert handled_error.validation_errors["field"] == "required"


class TestErrorTracker:
    """测试错误追踪器."""

    @pytest.fixture
    def error_tracker(self):
        """创建错误追踪器实例."""
        return ErrorTracker()

    def test_record_error(self, error_tracker):
        """测试记录错误."""
        error_tracker.record_error(error_code="PROVIDER_ERROR", provider="akshare", operation="fetch_data")

        key = "PROVIDER_ERROR:akshare:fetch_data"
        assert key in error_tracker.error_counts
        assert error_tracker.error_counts[key] == 1

    def test_record_multiple_errors(self, error_tracker):
        """测试记录多个错误."""
        for _ in range(3):
            error_tracker.record_error(error_code="RATE_LIMIT_ERROR", provider="yahoo")

        key = "RATE_LIMIT_ERROR:yahoo:None"
        assert error_tracker.error_counts[key] == 3

    def test_get_error_stats(self, error_tracker):
        """测试获取错误统计."""
        error_tracker.record_error("PROVIDER_ERROR", "akshare")
        error_tracker.record_error("RATE_LIMIT_ERROR", "yahoo")

        stats = error_tracker.get_error_stats()

        assert stats["total_errors"] == 2
        assert len(stats["error_counts"]) == 2
        assert "PROVIDER_ERROR:akshare:None" in stats["error_counts"]


class TestErrorContextManager:
    """测试错误上下文管理器."""

    @pytest.fixture
    def error_context_manager(self):
        """创建错误上下文管理器实例."""
        return ErrorContextManager(ErrorHandler())

    def test_set_context(self, error_context_manager):
        """测试设置上下文."""
        error_context_manager.set_context(operation="test_operation", provider="test_provider", extra_data="test")

        assert error_context_manager.operation == "test_operation"
        assert error_context_manager.provider == "test_provider"
        assert error_context_manager.context["extra_data"] == "test"

    def test_error_context_with_success(self, error_context_manager):
        """测试成功的错误上下文."""
        with error_context_manager.error_context("test_operation", "test_provider"):
            result = 1 + 1

        assert result == 2

    def test_error_context_with_exception(self, error_context_manager):
        """测试异常的错误上下文."""
        with pytest.raises(VPrismError) as exc_info:
            with error_context_manager.error_context("test_operation", "test_provider"):
                raise ValueError("测试异常")

        assert isinstance(exc_info.value, VPrismError)
        assert exc_info.value.details["operation"] == "test_operation"
        assert exc_info.value.details["provider"] == "test_provider"

    def test_safe_execute_with_success(self, error_context_manager):
        """测试安全执行成功."""

        def success_func(x, y):
            return x + y

        error_context_manager.set_context("test_operation")
        result = error_context_manager.safe_execute(success_func, 2, 3)

        assert result == 5

    def test_safe_execute_with_exception(self, error_context_manager):
        """测试安全执行异常."""

        def error_func():
            raise ValueError("测试异常")

        error_context_manager.set_context("test_operation")

        with pytest.raises(VPrismError) as exc_info:
            error_context_manager.safe_execute(error_func)

        assert isinstance(exc_info.value, VPrismError)


class TestExceptionHierarchy:
    """测试异常层次结构."""

    def test_vprism_error_base_class(self):
        """测试VPrismError基类."""
        error = VPrismError("测试消息", "TEST_CODE", {"detail": "value"})

        assert str(error) == "测试消息"
        assert error.error_code == "TEST_CODE"
        assert error.details["detail"] == "value"

    def test_provider_error_hierarchy(self):
        """测试ProviderError层次结构."""
        error = ProviderError("提供商错误", "akshare", "PROVIDER_ERROR")

        assert isinstance(error, VPrismError)
        assert error.provider_name == "akshare"

    def test_rate_limit_error(self):
        """测试RateLimitError."""
        error = RateLimitError("速率限制", "yahoo", retry_after=60)

        assert isinstance(error, ProviderError)
        assert error.retry_after == 60
        assert error.provider_name == "yahoo"

    def test_data_validation_error(self):
        """测试DataValidationError."""
        validation_errors = {"field": "required"}
        error = DataValidationError("验证失败", validation_errors)

        assert error.validation_errors["field"] == "required"

    def test_network_error(self):
        """测试NetworkError."""
        error = NetworkError("网络错误", "yahoo", status_code=404)

        assert error.provider_name == "yahoo"
        assert error.details["status_code"] == 404

    def test_cache_error(self):
        """测试CacheError."""
        error = CacheError("缓存错误", cache_type="redis")

        assert error.details["cache_type"] == "redis"


class TestErrorResponseFormat:
    """测试错误响应格式."""

    def test_format_error_response(self):
        """测试格式化错误响应."""
        response = format_error_response(ErrorCode.PROVIDER_ERROR, provider="akshare", message="连接失败")

        assert "error" in response
        assert response["error"]["code"] == "PROVIDER_ERROR"
        assert "akshare" in str(response["error"]["details"])
        assert "连接失败" in response["error"]["message"]

    def test_error_context_to_dict(self):
        """测试错误上下文转字典."""

        context = ErrorContext(
            error_code=ErrorCode.PROVIDER_ERROR,
            message="提供商错误",
            provider="akshare",
            operation="fetch_data",
        )

        dict_context = context.to_dict()
        assert dict_context["error_code"] == "PROVIDER_ERROR"
        assert dict_context["provider"] == "akshare"
        assert dict_context["operation"] == "fetch_data"


# 集成测试
class TestErrorHandlingIntegration:
    """错误处理集成测试."""

    def test_full_error_flow(self):
        """测试完整的错误处理流程."""
        handler = ErrorHandler()

        try:
            raise ProviderError(
                "提供商不可用",
                "akshare",
                "PROVIDER_UNAVAILABLE",
                {"provider": "akshare", "symbol": "000001"},
            )
        except Exception as e:
            handled_error = handler.handle_exception(e, "fetch_data", "akshare", symbol="000001")

            response = handler.create_error_response(handled_error)

            assert response["error"]["code"] == "PROVIDER_UNAVAILABLE"
            assert response["error"]["details"]["provider"] == "akshare"
            assert response["error"]["details"]["symbol"] == "000001"

    def test_error_tracking_integration(self):
        """测试错误追踪集成."""
        tracker = ErrorTracker()

        # 模拟多个错误
        errors = [
            ("PROVIDER_ERROR", "akshare", "fetch_data"),
            ("RATE_LIMIT_ERROR", "yahoo", "fetch_data"),
            ("PROVIDER_ERROR", "akshare", "fetch_data"),
        ]

        for error_code, provider, operation in errors:
            tracker.record_error(error_code, provider, operation)

        stats = tracker.get_error_stats()

        assert stats["total_errors"] == 3
        assert stats["error_counts"]["PROVIDER_ERROR:akshare:fetch_data"] == 2
        assert stats["error_counts"]["RATE_LIMIT_ERROR:yahoo:fetch_data"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
