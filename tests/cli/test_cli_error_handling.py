from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from vprism.cli.constants import (
    DATA_QUALITY_EXIT_CODE,
    PROVIDER_EXIT_CODE,
    RECONCILE_EXIT_CODE,
    SYSTEM_EXIT_CODE,
    VALIDATION_EXIT_CODE,
)
from vprism.cli.errors import handle_cli_error
from vprism.cli.main import app
from vprism.core.exceptions.codes import ErrorCode
from vprism.core.exceptions.domain import DomainError


class DummyDomainError(DomainError):
    def __init__(self, message: str, code: ErrorCode):
        super().__init__(message, code=code, layer="cli-test")


@pytest.mark.parametrize(
    ("code", "expected_exit"),
    [
        (ErrorCode.VALIDATION, VALIDATION_EXIT_CODE),
        (ErrorCode.PROVIDER, PROVIDER_EXIT_CODE),
        (ErrorCode.DATA_QUALITY, DATA_QUALITY_EXIT_CODE),
        (ErrorCode.RECONCILE, RECONCILE_EXIT_CODE),
        (ErrorCode.SYSTEM, SYSTEM_EXIT_CODE),
    ],
)
def test_handle_cli_error_emits_payload_and_exit_code(
    code: ErrorCode, expected_exit: int, capsys: pytest.CaptureFixture[str]
) -> None:
    error = DummyDomainError("boom", code)

    exit_code = handle_cli_error(error)

    assert exit_code == expected_exit

    captured = capsys.readouterr()
    payload = json.loads(captured.err.strip())
    assert payload["code"] == code.value
    assert payload["message"] == "boom"
    assert payload["details"]["layer"] == "cli-test"


@pytest.mark.parametrize(
    ("code", "expected_exit"),
    [
        (ErrorCode.VALIDATION, VALIDATION_EXIT_CODE),
        (ErrorCode.PROVIDER, PROVIDER_EXIT_CODE),
        (ErrorCode.DATA_QUALITY, DATA_QUALITY_EXIT_CODE),
        (ErrorCode.RECONCILE, RECONCILE_EXIT_CODE),
        (ErrorCode.SYSTEM, SYSTEM_EXIT_CODE),
    ],
)
def test_cli_commands_surface_domain_errors(
    monkeypatch: pytest.MonkeyPatch,
    code: ErrorCode,
    expected_exit: int,
) -> None:
    runner = CliRunner()

    def controller_factory() -> object:
        class Controller:
            def promote(self, force: bool) -> None:
                raise DummyDomainError("boom", code)

        return Controller()

    monkeypatch.setattr("vprism.cli.shadow.get_shadow_controller", controller_factory)

    result = runner.invoke(app, ["shadow", "promote"])

    assert result.exit_code == expected_exit

    payload = json.loads(result.stderr.strip())
    assert payload["code"] == code.value
    assert payload["message"] == "boom"
