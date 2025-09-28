"""Output formatter abstractions for CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, MutableSequence, Sequence, TextIO

import json
from rich.box import SIMPLE
from rich.console import Console
from rich.table import Table


class OutputFormatter:
    """Protocol-like base class for CLI output formatters."""

    name: str

    def render(
        self,
        rows: Sequence[Mapping[str, object]],
        *,
        stream: TextIO,
        columns: Sequence[str] | None = None,
    ) -> None:
        """Render the provided rows to the target stream."""

        raise NotImplementedError


@dataclass(slots=True)
class TableFormatter(OutputFormatter):
    """Render output as a Rich table."""

    name: str = "table"
    no_color: bool = False

    def render(
        self,
        rows: Sequence[Mapping[str, object]],
        *,
        stream: TextIO,
        columns: Sequence[str] | None = None,
    ) -> None:
        console = Console(file=stream, color_system=None if self.no_color else "auto", no_color=self.no_color)

        resolved_columns: MutableSequence[str]
        if columns:
            resolved_columns = list(columns)
        elif rows:
            resolved_columns = list(rows[0].keys())
        else:
            resolved_columns = []

        if not rows:
            if resolved_columns:
                table = self._create_table(resolved_columns)
                console.print(table)
            console.print("No data available.")
            return

        table = self._create_table(resolved_columns)
        for row in rows:
            table.add_row(*(self._format_cell(row.get(column)) for column in resolved_columns))
        console.print(table)

    def _create_table(self, columns: Sequence[str]) -> Table:
        table = Table(box=SIMPLE, show_lines=False)
        header_style = "" if self.no_color else "bold"
        for column in columns:
            table.add_column(column, header_style=header_style)
        return table

    def _format_cell(self, value: object) -> str:
        if value is None:
            return "-"
        if isinstance(value, (float, int)):
            return str(value)
        return str(value)


@dataclass(slots=True)
class JSONLFormatter(OutputFormatter):
    """Render output as JSON Lines."""

    name: str = "jsonl"

    def render(
        self,
        rows: Sequence[Mapping[str, object]],
        *,
        stream: TextIO,
        columns: Sequence[str] | None = None,
    ) -> None:
        if columns:
            filtered = [
                {column: row.get(column) for column in columns}
                for row in rows
            ]
        else:
            filtered = list(rows)

        for row in filtered:
            json.dump(row, stream, ensure_ascii=False, default=str)
            stream.write("\n")
        stream.flush()


def create_formatter(name: str, *, no_color: bool = False) -> OutputFormatter:
    """Instantiate a formatter by name."""

    normalized = name.strip().lower()
    if normalized == "table":
        return TableFormatter(no_color=no_color)
    if normalized == "jsonl":
        return JSONLFormatter()
    msg = f"Unsupported format '{name}'. Available formats: table, jsonl."
    raise ValueError(msg)


__all__ = ["OutputFormatter", "TableFormatter", "JSONLFormatter", "create_formatter"]
