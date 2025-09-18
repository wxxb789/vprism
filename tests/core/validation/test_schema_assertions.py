"""Tests for DuckDB schema assertion helpers."""

from __future__ import annotations

import duckdb
import pytest

from vprism.core.data.schema import (
    NORMALIZATION_BASE_TABLE,
    RAW_BASE_TABLE,
    ensure_baseline_tables,
)
from vprism.core.exceptions.base import DataValidationError
from vprism.core.validation.schema_assertions import (
    assert_baseline_tables,
    assert_table_matches_schema,
)


@pytest.fixture()
def duckdb_conn() -> duckdb.DuckDBPyConnection:
    """Provide an in-memory DuckDB connection for tests."""

    connection = duckdb.connect(database=":memory:")
    try:
        yield connection
    finally:
        connection.close()


def test_assert_table_matches_schema_success(duckdb_conn: duckdb.DuckDBPyConnection) -> None:
    """The helper passes when table definitions match exactly."""

    ensure_baseline_tables(duckdb_conn)

    # Should not raise for either baseline table.
    assert_table_matches_schema(duckdb_conn, RAW_BASE_TABLE)
    assert_table_matches_schema(duckdb_conn, NORMALIZATION_BASE_TABLE)


def test_assert_table_matches_schema_missing_column(duckdb_conn: duckdb.DuckDBPyConnection) -> None:
    """Missing required columns trigger validation errors."""

    duckdb_conn.execute(
        """
        CREATE TABLE raw_schema (
            supplier_symbol VARCHAR NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            provider VARCHAR
        )
        """
    )

    with pytest.raises(DataValidationError) as exc_info:
        assert_table_matches_schema(duckdb_conn, RAW_BASE_TABLE)

    errors = exc_info.value.validation_errors
    assert "volume" in errors["missing_columns"]


def test_assert_table_matches_schema_type_mismatch(duckdb_conn: duckdb.DuckDBPyConnection) -> None:
    """Type mismatches are surfaced with detailed diagnostics."""

    duckdb_conn.execute(
        """
        CREATE TABLE raw_schema (
            supplier_symbol VARCHAR NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            open VARCHAR,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            provider VARCHAR
        )
        """
    )

    with pytest.raises(DataValidationError) as exc_info:
        assert_table_matches_schema(duckdb_conn, RAW_BASE_TABLE)

    type_mismatches = exc_info.value.validation_errors["type_mismatches"]
    mismatch = type_mismatches["open"]
    assert mismatch["expected"] == "DOUBLE"
    assert mismatch["actual"] == "VARCHAR"


def test_assert_table_matches_schema_not_null_mismatch(duckdb_conn: duckdb.DuckDBPyConnection) -> None:
    """Missing NOT NULL constraints are reported."""

    duckdb_conn.execute(
        """
        CREATE TABLE raw_schema (
            supplier_symbol VARCHAR,
            timestamp TIMESTAMP,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            provider VARCHAR
        )
        """
    )

    with pytest.raises(DataValidationError) as exc_info:
        assert_table_matches_schema(duckdb_conn, RAW_BASE_TABLE)

    constraint_mismatches = exc_info.value.validation_errors["constraint_mismatches"]
    assert constraint_mismatches["supplier_symbol"]["expected_not_null"] is True
    assert constraint_mismatches["supplier_symbol"]["actual_not_null"] is False
    assert constraint_mismatches["timestamp"]["expected_not_null"] is True


def test_assert_baseline_tables_success(duckdb_conn: duckdb.DuckDBPyConnection) -> None:
    """Aggregate assertion validates all baseline schemas."""

    ensure_baseline_tables(duckdb_conn)

    assert_baseline_tables(duckdb_conn)
