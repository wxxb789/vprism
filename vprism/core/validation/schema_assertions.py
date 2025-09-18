"""DuckDB schema validation helpers for PRD-0 baseline datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

try:  # pragma: no cover - duckdb optional for type checking environments.
    from duckdb import DuckDBPyConnection
except Exception:  # pragma: no cover
    DuckDBPyConnection = "DuckDBPyConnection"  # type: ignore[misc,assignment]

from vprism.core.data.schema import ColumnDef, TableSchema, baseline_tables
from vprism.core.exceptions.base import DataValidationError


@dataclass(frozen=True)
class _ObservedColumn:
    """Represents DuckDB column metadata from PRAGMA table_info."""

    name: str
    data_type: str
    not_null: bool


def _fetch_table_info(conn: DuckDBPyConnection, table_name: str) -> dict[str, _ObservedColumn]:
    """Return DuckDB column metadata keyed by column name."""

    pragma_sql = f"PRAGMA table_info('{table_name}')"
    rows = conn.execute(pragma_sql).fetchall()
    columns: dict[str, _ObservedColumn] = {}
    for row in rows:
        # DuckDB PRAGMA table_info rows: (cid, name, type, notnull, dflt_value, pk)
        _, name, data_type, notnull, _, _ = row
        columns[name] = _ObservedColumn(name=name, data_type=str(data_type).upper(), not_null=bool(notnull))
    return columns


def _constraint_flags(column: ColumnDef) -> Mapping[str, bool]:
    """Return constraint flags derived from a :class:`ColumnDef`."""

    constraints = {constraint.upper() for constraint in column.constraints}
    return {"not_null": "NOT NULL" in constraints}


def _normalize_type(data_type: str) -> str:
    """Normalize DuckDB type strings for comparison."""

    return data_type.strip().upper()


def assert_table_matches_schema(conn: DuckDBPyConnection, expected: TableSchema) -> None:
    """Assert that a DuckDB table matches the provided :class:`TableSchema`.

    Args:
        conn: Active DuckDB connection to inspect.
        expected: TableSchema describing the desired structure.

    Raises:
        DataValidationError: Raised when the table is missing, lacks required columns,
            or column types/constraints differ from the expected definition.
    """

    observed_columns = _fetch_table_info(conn, expected.name)
    if not observed_columns:
        raise DataValidationError(
            message=f"DuckDB table '{expected.name}' does not exist.",
            validation_errors={"table_missing": True},
            details={"table": expected.name},
        )

    missing_columns: list[str] = []
    type_mismatches: dict[str, dict[str, str]] = {}
    constraint_mismatches: dict[str, dict[str, bool]] = {}

    for column in expected.columns:
        observed = observed_columns.get(column.name)
        if observed is None:
            missing_columns.append(column.name)
            continue

        expected_type = _normalize_type(column.data_type)
        actual_type = _normalize_type(observed.data_type)
        if expected_type != actual_type:
            type_mismatches[column.name] = {
                "expected": expected_type,
                "actual": actual_type,
            }

        expected_constraints = _constraint_flags(column)
        actual_constraints = {"not_null": observed.not_null}
        if expected_constraints != actual_constraints:
            constraint_mismatches[column.name] = {
                "expected_not_null": expected_constraints["not_null"],
                "actual_not_null": actual_constraints["not_null"],
            }

    if missing_columns or type_mismatches or constraint_mismatches:
        raise DataValidationError(
            message=f"DuckDB table '{expected.name}' does not match expected schema.",
            validation_errors={
                "missing_columns": missing_columns,
                "type_mismatches": type_mismatches,
                "constraint_mismatches": constraint_mismatches,
            },
            details={"table": expected.name},
        )


def assert_tables_match_schemas(conn: DuckDBPyConnection, schemas: Iterable[TableSchema]) -> None:
    """Assert that multiple DuckDB tables match their expected schemas."""

    for schema in schemas:
        assert_table_matches_schema(conn, schema)


def assert_baseline_tables(conn: DuckDBPyConnection) -> None:
    """Assert that all PRD-0 baseline tables exist with the expected schemas."""

    assert_tables_match_schemas(conn, baseline_tables())


__all__ = [
    "assert_table_matches_schema",
    "assert_tables_match_schemas",
    "assert_baseline_tables",
]
