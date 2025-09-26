"""Domain-level error hierarchy definitions."""

from __future__ import annotations

from typing import Any, Mapping

from vprism.core.exceptions.base import VPrismError
from vprism.core.exceptions.codes import ErrorCode


class DomainError(VPrismError):
    """领域错误基类，携带标准化错误上下文."""

    def __init__(
        self,
        message: str,
        code: ErrorCode,
        layer: str,
        retryable: bool = False,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        """构造领域错误实例."""

        payload = dict(context or {})
        details = {**payload, "layer": layer, "retryable": retryable}
        super().__init__(message, code.value, details)
        self.code = code
        self.layer = layer
        self.retryable = retryable
        self.context = payload

    def to_payload(self) -> dict[str, Any]:
        """Return a serializable payload representing the error."""

        return {
            "code": self.code.value,
            "message": self.message,
            "layer": self.layer,
            "retryable": self.retryable,
            "context": dict(self.context),
        }
