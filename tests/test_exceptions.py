"""Test VPrismError exception hierarchy and details."""

from vprism.core.exceptions import (
    AuthenticationError,
    CacheError,
    DataValidationError,
    NetworkError,
    NoAvailableProviderError,
    NoCapableProviderError,
    ProviderError,
    RateLimitError,
    VPrismError,
)


class TestExceptionHierarchy:
    """Test exception hierarchy."""

    def test_vprism_error_base_class(self) -> None:
        """Test VPrismError base class."""
        error = VPrismError("测试消息", "PROVIDER_ERROR", {"detail": "value"})

        assert str(error) == "测试消息"
        assert error.error_code == "PROVIDER_ERROR"
        assert error.details["detail"] == "value"

    def test_provider_error_hierarchy(self) -> None:
        """Test ProviderError hierarchy."""
        error = ProviderError("提供商错误", "akshare", "PROVIDER_ERROR")

        assert isinstance(error, VPrismError)
        assert error.provider_name == "akshare"

    def test_rate_limit_error(self) -> None:
        """Test RateLimitError."""
        error = RateLimitError("速率限制", "yahoo", retry_after=60)

        assert isinstance(error, ProviderError)
        assert error.retry_after == 60
        assert error.provider_name == "yahoo"

    def test_data_validation_error(self) -> None:
        """Test DataValidationError."""
        validation_errors = {"field": "required"}
        error = DataValidationError("验证失败", validation_errors)

        assert error.validation_errors["field"] == "required"

    def test_network_error(self) -> None:
        """Test NetworkError."""
        error = NetworkError("网络错误", "yahoo", status_code=404)

        assert error.provider_name == "yahoo"
        assert error.details["status_code"] == 404

    def test_cache_error(self) -> None:
        """Test CacheError."""
        error = CacheError("缓存错误", cache_type="redis")

        assert error.details["cache_type"] == "redis"

    def test_no_capable_provider_error(self) -> None:
        """Test NoCapableProviderError."""
        query_details = {"asset": "stock", "market": "cn"}
        error = NoCapableProviderError("没有可用提供商", query_details)

        assert error.details["query"]["asset"] == "stock"

    def test_no_available_provider_error(self) -> None:
        """Test NoAvailableProviderError."""
        failed_providers = [{"provider": "akshare", "reason": "timeout"}, {"provider": "yahoo", "reason": "error"}]
        error = NoAvailableProviderError("所有提供商都失败", failed_providers)

        assert error.details["failed_providers"] == failed_providers

    def test_authentication_error(self) -> None:
        """Test AuthenticationError."""
        error = AuthenticationError("认证失败", "akshare", "API_KEY")

        assert error.provider_name == "akshare"
        assert error.details["auth_method"] == "API_KEY"


class TestExceptionWithDetails:
    """Test exceptions with details."""

    def test_provider_error_with_details(self) -> None:
        """Test ProviderError with details."""
        details = {"status": 500, "response": "服务器错误"}
        error = ProviderError("提供商错误", "akshare", "PROVIDER_ERROR", details)

        assert error.details["status"] == 500
        assert error.details["response"] == "服务器错误"

    def test_rate_limit_error_with_retry_after(self) -> None:
        """Test RateLimitError with retry_after."""
        error = RateLimitError("超出限制", "yahoo", retry_after=120)

        assert error.retry_after == 120
        assert error.details["retry_after"] == 120

    def test_data_validation_error_with_validation_errors(self) -> None:
        """Test DataValidationError with validation errors."""
        validation_errors = {
            "symbol": "symbol is required",
            "market": "invalid market type",
        }
        error = DataValidationError("验证失败", validation_errors)

        assert error.validation_errors["symbol"] == "symbol is required"
        assert error.validation_errors["market"] == "invalid market type"
