"""Stub data provider for injecting baseline OHLCV rows into DuckDB."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

try:  # pragma: no cover - optional import for static analysis environments
    from duckdb import DuckDBPyConnection
except Exception:  # pragma: no cover
    DuckDBPyConnection = "DuckDBPyConnection"  # type: ignore[misc,assignment]

from vprism.core.data.schema import RAW_BASE_TABLE, TableSchema
from vprism.core.exceptions.base import DataValidationError


@dataclass(frozen=True)
class StubProviderRow:
    """Typed representation of a stub provider row."""

    supplier_symbol: str
    timestamp: object
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    provider: str = "stub"

    def as_mapping(self) -> Mapping[str, object]:
        """Return the row as a mapping compatible with DuckDB inserts."""

        return {
            "supplier_symbol": self.supplier_symbol,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "provider": self.provider,
        }


class VPrismStubProvider:
    """Utility for seeding DuckDB tables with deterministic stub rows."""

    def __init__(
        self,
        conn: DuckDBPyConnection,
        table_schema: TableSchema = RAW_BASE_TABLE,
        provider_name: str = "stub",
    ) -> None:
        self._conn = conn
        self._table_schema = table_schema
        self._provider_name = provider_name

    def ingest_rows(self, rows: Sequence[Mapping[str, object] | StubProviderRow]) -> None:
        """Insert validated rows into the configured DuckDB table."""

        normalized_rows = [self._normalize_row(row) for row in rows]
        validation_errors = list(self._validate_rows(normalized_rows))
        if validation_errors:
            raise DataValidationError(
                message="Stub provider detected invalid rows.",
                validation_errors={"rows": validation_errors},
                details={
                    "provider": self._provider_name,
                    "table": self._table_schema.name,
                },
            )

        self._table_schema.ensure(self._conn)
        column_names = [column.name for column in self._table_schema.columns]
        placeholders = ", ".join(["?"] * len(column_names))
        insert_sql = (
            f"INSERT INTO {self._table_schema.name} "
            f"({', '.join(column_names)}) VALUES ({placeholders})"
        )
        parameters = [[row.get(name) for name in column_names] for row in normalized_rows]
        if parameters:
            self._conn.executemany(insert_sql, parameters)

    def _normalize_row(
        self, row: Mapping[str, object] | StubProviderRow
    ) -> Mapping[str, object]:
        if isinstance(row, StubProviderRow):
            return row.as_mapping()
        return dict(row)

    def _validate_rows(
        self, rows: Iterable[Mapping[str, object]]
    ) -> Iterable[Mapping[str, object]]:
        required_columns = {
            column.name
            for column in self._table_schema.columns
            if "NOT NULL" in {constraint.upper() for constraint in column.constraints}
        }
        valid_columns = {column.name for column in self._table_schema.columns}
        for index, row in enumerate(rows):
            missing_required = [
                column
                for column in required_columns
                if row.get(column) is None
            ]
            unexpected = sorted(set(row.keys()) - valid_columns)
            if missing_required or unexpected:
                error_payload: dict[str, object] = {"index": index}
                if missing_required:
                    error_payload["missing_fields"] = sorted(missing_required)
                if unexpected:
                    error_payload["unexpected_fields"] = unexpected
                yield error_payload


__all__ = ["VPrismStubProvider", "StubProviderRow"]
