from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from vprism.cli.main import create_app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_help_lists_expected_command_groups(runner: CliRunner) -> None:
    app = create_app()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    for command_name in ("data", "symbol"):
        assert command_name in result.output


def test_cli_callback_normalizes_configuration(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_contexts: list[dict[str, Any]] = []
    formatter_calls: list[tuple[str, bool]] = []

    def fake_create_formatter(name: str, *, no_color: bool) -> object:
        formatter_calls.append((name, no_color))
        return object()

    def register_capture_command(app: typer.Typer) -> None:
        data_app = typer.Typer()

        @data_app.command()
        def capture(ctx: typer.Context) -> None:
            captured_contexts.append(dict(ctx.obj))

        app.add_typer(data_app, name="data")

    monkeypatch.setattr("vprism.cli.main.create_formatter", fake_create_formatter)
    monkeypatch.setattr("vprism.cli.main.register_data_commands", register_capture_command)
    for attr_name in ("register_symbol_commands",):
        monkeypatch.setattr(f"vprism.cli.main.{attr_name}", lambda app: None, raising=False)

    output_path = tmp_path / "result.jsonl"

    test_cases = [
        (
            ["--format", "TABLE", "--log-level", "debug"],
            {
                "format": "table",
                "output_path": None,
                "log_level": "DEBUG",
                "no_color": False,
            },
            ("table", False),
        ),
        (
            [
                "--format",
                " jsonl ",
                "--output",
                str(output_path),
                "--log-level",
                "warning",
                "--no-color",
            ],
            {
                "format": "jsonl",
                "output_path": output_path,
                "log_level": "WARNING",
                "no_color": True,
            },
            ("jsonl", True),
        ),
    ]

    for cli_args, expected_context, expected_formatter in test_cases:
        captured_contexts.clear()
        formatter_calls.clear()
        app = create_app()

        result = runner.invoke(app, [*cli_args, "data", "capture"])

        assert result.exit_code == 0, result.output
        assert captured_contexts == [expected_context]
        assert formatter_calls == [expected_formatter]


def test_cli_invalid_format_raises_bad_parameter(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def register_stub_command(app: typer.Typer) -> None:
        data_app = typer.Typer()

        @data_app.command()
        def noop() -> None:
            """No-op command used for argument validation."""

        app.add_typer(data_app, name="data")

    monkeypatch.setattr("vprism.cli.main.register_data_commands", register_stub_command)
    for attr_name in ("register_symbol_commands",):
        monkeypatch.setattr(f"vprism.cli.main.{attr_name}", lambda app: None, raising=False)

    app = create_app()

    result = runner.invoke(app, ["--format", "invalid", "data", "noop"])

    assert result.exit_code == 2
    assert "Unsupported format" in result.output or "invalid" in result.output.lower()
