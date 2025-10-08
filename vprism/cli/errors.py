"""Shared CLI error handling utilities."""

from __future__ import annotations

from typing import Mapping

from vprism.core.exceptions.base import VPrismError
from vprism.core.exceptions.codes import ErrorCode

from .constants import (
    DATA_QUALITY_EXIT_CODE,
    PROVIDER_EXIT_CODE,
    RECONCILE_EXIT_CODE,
    SYSTEM_EXIT_CODE,
    VALIDATION_EXIT_CODE,
)
from .utils import emit_error

ErrorCodeLike = ErrorCode | str


_ERROR_CODE_TO_EXIT: dict[str, int] = {
    ErrorCode.VALIDATION.value: VALIDATION_EXIT_CODE,
    ErrorCode.VALIDATION_ERROR.value: VALIDATION_EXIT_CODE,
    ErrorCode.DATA_VALIDATION_ERROR.value: VALIDATION_EXIT_CODE,
    ErrorCode.INVALID_QUERY.value: VALIDATION_EXIT_CODE,
    ErrorCode.UNSUPPORTED_PARAMETERS.value: VALIDATION_EXIT_CODE,
    ErrorCode.QUERY_ERROR.value: VALIDATION_EXIT_CODE,
    "SYMBOL_UNRESOLVED": VALIDATION_EXIT_CODE,
    ErrorCode.PROVIDER.value: PROVIDER_EXIT_CODE,
    ErrorCode.PROVIDER_ERROR.value: PROVIDER_EXIT_CODE,
    ErrorCode.PROVIDER_NOT_FOUND.value: PROVIDER_EXIT_CODE,
    ErrorCode.PROVIDER_UNAVAILABLE.value: PROVIDER_EXIT_CODE,
    ErrorCode.PROVIDER_TIMEOUT.value: PROVIDER_EXIT_CODE,
    ErrorCode.ROUTING.value: PROVIDER_EXIT_CODE,
    ErrorCode.AUTHENTICATION_ERROR.value: PROVIDER_EXIT_CODE,
    ErrorCode.AUTHORIZATION_ERROR.value: PROVIDER_EXIT_CODE,
    ErrorCode.API_KEY_INVALID.value: PROVIDER_EXIT_CODE,
    ErrorCode.API_KEY_EXPIRED.value: PROVIDER_EXIT_CODE,
    ErrorCode.RATE_LIMIT_ERROR.value: PROVIDER_EXIT_CODE,
    ErrorCode.RATE_LIMIT_EXCEEDED.value: PROVIDER_EXIT_CODE,
    ErrorCode.QUOTA_EXCEEDED.value: PROVIDER_EXIT_CODE,
    ErrorCode.NO_CAPABLE_PROVIDER.value: PROVIDER_EXIT_CODE,
    ErrorCode.NETWORK_ERROR.value: PROVIDER_EXIT_CODE,
    ErrorCode.CONNECTION_TIMEOUT.value: PROVIDER_EXIT_CODE,
    ErrorCode.CONNECTION_REFUSED.value: PROVIDER_EXIT_CODE,
    ErrorCode.DNS_RESOLUTION_ERROR.value: PROVIDER_EXIT_CODE,
    ErrorCode.DATA_QUALITY.value: DATA_QUALITY_EXIT_CODE,
    ErrorCode.DATA_NOT_FOUND.value: DATA_QUALITY_EXIT_CODE,
    ErrorCode.DATA_FORMAT_ERROR.value: DATA_QUALITY_EXIT_CODE,
    ErrorCode.DATA_INCOMPLETE.value: DATA_QUALITY_EXIT_CODE,
    "DRIFT_COMPUTATION_ERROR": DATA_QUALITY_EXIT_CODE,
    ErrorCode.RECONCILE.value: RECONCILE_EXIT_CODE,
    "RECONCILIATION_ERROR": RECONCILE_EXIT_CODE,
    ErrorCode.SYSTEM.value: SYSTEM_EXIT_CODE,
    ErrorCode.GENERAL_ERROR.value: SYSTEM_EXIT_CODE,
    ErrorCode.CONFIGURATION_ERROR.value: SYSTEM_EXIT_CODE,
    ErrorCode.INTERNAL_ERROR.value: SYSTEM_EXIT_CODE,
    ErrorCode.UNEXPECTED_ERROR.value: SYSTEM_EXIT_CODE,
}


def _normalize_error_code(code: ErrorCodeLike) -> str:
    if isinstance(code, ErrorCode):
        return code.value
    return str(code).upper()


def _resolve_exit_code(code: str) -> int:
    normalized = code.upper()
    if normalized in _ERROR_CODE_TO_EXIT:
        return _ERROR_CODE_TO_EXIT[normalized]
    if "VALID" in normalized:
        return VALIDATION_EXIT_CODE
    if "PROVIDER" in normalized or "AUTH" in normalized or "NETWORK" in normalized:
        return PROVIDER_EXIT_CODE
    if "QUALITY" in normalized or "DRIFT" in normalized:
        return DATA_QUALITY_EXIT_CODE
    if "RECONCILE" in normalized:
        return RECONCILE_EXIT_CODE
    return SYSTEM_EXIT_CODE


def map_exit_code(error_code: ErrorCodeLike) -> int:
    """Map an error code string or :class:`ErrorCode` to a CLI exit code."""

    normalized = _normalize_error_code(error_code)
    return _resolve_exit_code(normalized)


def handle_cli_error(error: VPrismError) -> int:
    """Emit a structured error payload and return the process exit code."""

    message = getattr(error, "message", str(error))
    code = getattr(error, "error_code", ErrorCode.UNEXPECTED_ERROR.value)
    details: Mapping[str, object] | None = getattr(error, "details", None)
    emit_error(message, str(code), details=details)
    return map_exit_code(code)


__all__ = ["handle_cli_error", "map_exit_code"]
