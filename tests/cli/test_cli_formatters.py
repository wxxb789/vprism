"""Tests for CLI output formatter implementations."""

from __future__ import annotations

import json
from io import StringIO

import pytest

pytest.importorskip("pydantic")

from vprism.cli.formatters import JSONLFormatter, TableFormatter, create_formatter


def _extract_non_empty_lines(value: str) -> list[str]:
    return [line for line in value.splitlines() if line.strip()]


def test_table_formatter_renders_rows_without_color() -> None:
    rows = [
        {"symbol": "AAPL", "price": 100.5},
        {"symbol": "MSFT", "price": 200.0},
    ]
    stream = StringIO()

    formatter = TableFormatter(no_color=True)
    formatter.render(rows, stream=stream)

    output = stream.getvalue()
    assert "\x1b" not in output

    lines = _extract_non_empty_lines(output)
    assert any("symbol" in line and "price" in line for line in lines)
    assert any("AAPL" in line and "100.5" in line for line in lines)
    assert any("MSFT" in line and "200.0" in line for line in lines)


def test_jsonl_formatter_renders_line_delimited_json() -> None:
    rows = [
        {"symbol": "AAPL", "price": 100.5},
        {"symbol": "MSFT", "price": 200.0},
    ]
    stream = StringIO()

    JSONLFormatter().render(rows, stream=stream, columns=["symbol"])

    lines = _extract_non_empty_lines(stream.getvalue())
    assert [json.loads(line) for line in lines] == [
        {"symbol": "AAPL"},
        {"symbol": "MSFT"},
    ]


def test_create_formatter_unknown_name() -> None:
    with pytest.raises(ValueError):
        create_formatter("unknown")
