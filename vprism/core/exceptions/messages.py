"""标准化错误消息模板."""

from typing import Any

from vprism.core.exceptions.codes import ErrorCode


class ErrorMessageTemplate:
    """错误消息模板管理器."""

    _templates: dict[ErrorCode, str] = {
        # 通用错误
        ErrorCode.GENERAL_ERROR: "发生未知错误",
        ErrorCode.VALIDATION_ERROR: "数据验证失败: {details}",
        ErrorCode.CONFIGURATION_ERROR: "配置错误: {details}",
        # 提供商相关错误
        ErrorCode.PROVIDER_ERROR: "数据提供商{provider}发生错误: {message}",
        ErrorCode.PROVIDER_NOT_FOUND: "找不到数据提供商: {provider}",
        ErrorCode.PROVIDER_UNAVAILABLE: "数据提供商{provider}当前不可用",
        ErrorCode.PROVIDER_TIMEOUT: "数据提供商{provider}请求超时",
        # 认证和授权错误
        ErrorCode.AUTHENTICATION_ERROR: "认证失败: {message}",
        ErrorCode.AUTHORIZATION_ERROR: "权限不足: {message}",
        ErrorCode.API_KEY_INVALID: "API密钥无效",
        ErrorCode.API_KEY_EXPIRED: "API密钥已过期",
        # 速率限制错误
        ErrorCode.RATE_LIMIT_ERROR: "请求被限制",
        ErrorCode.RATE_LIMIT_EXCEEDED: "超出速率限制，请{retry_after}秒后重试",
        ErrorCode.QUOTA_EXCEEDED: "超出配额限制",
        # 数据相关错误
        ErrorCode.DATA_NOT_FOUND: "找不到请求的数据: {query}",
        ErrorCode.DATA_VALIDATION_ERROR: "数据验证失败: {validation_errors}",
        ErrorCode.DATA_FORMAT_ERROR: "数据格式错误: {format_error}",
        ErrorCode.DATA_INCOMPLETE: "数据不完整，缺少: {missing_fields}",
        # 缓存相关错误
        ErrorCode.CACHE_ERROR: "缓存错误: {message}",
        ErrorCode.CACHE_MISS: "缓存未命中",
        ErrorCode.CACHE_CONNECTION_ERROR: "缓存连接失败",
        # 网络相关错误
        ErrorCode.NETWORK_ERROR: "网络错误: {message}",
        ErrorCode.CONNECTION_TIMEOUT: "连接超时",
        ErrorCode.CONNECTION_REFUSED: "连接被拒绝",
        ErrorCode.DNS_RESOLUTION_ERROR: "DNS解析失败",
        # 查询相关错误
        ErrorCode.QUERY_ERROR: "查询错误: {message}",
        ErrorCode.INVALID_QUERY: "无效查询: {message}",
        ErrorCode.UNSUPPORTED_PARAMETERS: "不支持的参数: {parameters}",
        ErrorCode.NO_CAPABLE_PROVIDER: "没有提供商能处理该查询: {query_details}",
        # 存储相关错误
        ErrorCode.STORAGE_ERROR: "存储错误: {message}",
        ErrorCode.DATABASE_ERROR: "数据库错误: {message}",
        ErrorCode.DATABASE_CONNECTION_ERROR: "数据库连接失败",
        # 系统内部错误
        ErrorCode.INTERNAL_ERROR: "内部错误",
        ErrorCode.UNEXPECTED_ERROR: "发生未预期的错误",
    }

    @classmethod
    def get_message(cls, error_code: ErrorCode, **kwargs: Any) -> str:
        """获取标准化错误消息.

        Args:
            error_code: 错误代码
            **kwargs: 模板变量

        Returns:
            格式化后的错误消息
        """
        template = cls._templates.get(error_code, "发生未知错误")
        try:
            return template.format(**kwargs)
        except KeyError:
            # 如果缺少模板变量，返回带错误代码的通用消息
            return f"{cls._templates[ErrorCode.GENERAL_ERROR]} (错误代码: {error_code.value})"


class ErrorContext:
    """错误上下文信息."""

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        provider: str | None = None,
        operation: str | None = None,
        timestamp: str | None = None,
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.provider = provider
        self.operation = operation
        self.timestamp = timestamp

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式."""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "provider": self.provider,
            "operation": self.operation,
            "timestamp": self.timestamp,
        }


def format_error_response(error_code: ErrorCode, message: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """格式化错误响应.

    Args:
        error_code: 错误代码
        message: 自定义错误消息(可选)
        **kwargs: 额外的错误详情

    Returns:
        标准化的错误响应字典
    """
    if message is None:
        message = ErrorMessageTemplate.get_message(error_code, **kwargs)

    return {
        "error": {
            "code": error_code.value,
            "message": message,
            "details": kwargs,
            "timestamp": None,  # 将在调用处设置
        }
    }
