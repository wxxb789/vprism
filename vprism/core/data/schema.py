"""Core schema definitions for baseline OHLCV datasets."""

from __future__ import annotations

from collections.abc import Iterable, Sequence  # noqa: TC003
from dataclasses import dataclass

try:  # pragma: no cover - duckdb is optional at import time for type checking.
    from duckdb import DuckDBPyConnection
except Exception:  # pragma: no cover
    DuckDBPyConnection = "DuckDBPyConnection"  # type: ignore[misc,assignment]


@dataclass(frozen=True)
class ColumnDef:
    """Represents a DuckDB table column definition."""

    name: str
    data_type: str
    constraints: Sequence[str] = ()

    def render(self) -> str:
        parts = [self.name, self.data_type, *self.constraints]
        return " ".join(parts)


@dataclass(frozen=True)
class TableSchema:
    """Utility wrapper describing a DuckDB table schema."""

    name: str
    columns: Sequence[ColumnDef]
    primary_key: Sequence[str] = ()

    def create_ddl(self) -> str:
        column_defs: list[str] = [column.render() for column in self.columns]
        if self.primary_key:
            pk_cols = ", ".join(self.primary_key)
            column_defs.append(f"PRIMARY KEY ({pk_cols})")
        columns_sql = ",\n                ".join(column_defs)
        return f"""
            CREATE TABLE IF NOT EXISTS {self.name} (
                {columns_sql}
            )
            """.strip()

    def ensure(self, conn: DuckDBPyConnection) -> None:
        """Create the table on the provided connection if it does not exist."""

        conn.execute(self.create_ddl())


RAW_BASE_TABLE = TableSchema(
    name="raw_schema",
    columns=(
        ColumnDef("supplier_symbol", "VARCHAR", ("NOT NULL",)),
        ColumnDef("timestamp", "TIMESTAMP", ("NOT NULL",)),
        ColumnDef("open", "DOUBLE"),
        ColumnDef("high", "DOUBLE"),
        ColumnDef("low", "DOUBLE"),
        ColumnDef("close", "DOUBLE"),
        ColumnDef("volume", "DOUBLE"),
        ColumnDef("provider", "VARCHAR"),
    ),
)

NORMALIZATION_BASE_TABLE = TableSchema(
    name="normalization_schema",
    columns=(
        ColumnDef("supplier_symbol", "VARCHAR", ("NOT NULL",)),
        ColumnDef("timestamp", "TIMESTAMP", ("NOT NULL",)),
        ColumnDef("open", "DOUBLE"),
        ColumnDef("high", "DOUBLE"),
        ColumnDef("low", "DOUBLE"),
        ColumnDef("close", "DOUBLE"),
        ColumnDef("volume", "DOUBLE"),
        ColumnDef("provider", "VARCHAR"),
        ColumnDef("market", "VARCHAR"),
        ColumnDef("tz_offset", "INTEGER"),
        ColumnDef("currency", "VARCHAR"),
        ColumnDef("c_symbol", "VARCHAR"),
    ),
)

SYMBOL_MAP_TABLE = TableSchema(
    name="symbol_map",
    columns=(
        ColumnDef("c_symbol", "VARCHAR", ("NOT NULL",)),
        ColumnDef("raw_symbol", "VARCHAR", ("NOT NULL",)),
        ColumnDef("market", "VARCHAR", ("NOT NULL",)),
        ColumnDef("asset_type", "VARCHAR", ("NOT NULL",)),
        ColumnDef("provider_hint", "VARCHAR"),
        ColumnDef("rule_id", "VARCHAR", ("NOT NULL",)),
        ColumnDef("created_at", "TIMESTAMP", ("NOT NULL",)),
    ),
    primary_key=("c_symbol", "raw_symbol"),
)

RAW_OHLCV_TABLE = TableSchema(
    name="raw_ohlcv",
    columns=(
        ColumnDef("supplier_symbol", "VARCHAR", ("NOT NULL",)),
        ColumnDef("market", "VARCHAR", ("NOT NULL",)),
        ColumnDef("ts", "TIMESTAMP", ("NOT NULL",)),
        ColumnDef("open", "DOUBLE"),
        ColumnDef("high", "DOUBLE"),
        ColumnDef("low", "DOUBLE"),
        ColumnDef("close", "DOUBLE"),
        ColumnDef("volume", "DOUBLE"),
        ColumnDef("provider", "VARCHAR", ("NOT NULL",)),
        ColumnDef("batch_id", "VARCHAR", ("NOT NULL",)),
        ColumnDef("ingest_time", "TIMESTAMP", ("NOT NULL",)),
    ),
    primary_key=("supplier_symbol", "market", "ts", "batch_id"),
)


CORPORATE_ACTIONS_TABLE = TableSchema(
    name="corporate_actions",
    columns=(
        ColumnDef("market", "VARCHAR", ("NOT NULL",)),
        ColumnDef("supplier_symbol", "VARCHAR", ("NOT NULL",)),
        ColumnDef("event_type", "VARCHAR", ("NOT NULL",)),
        ColumnDef("effective_date", "DATE", ("NOT NULL",)),
        ColumnDef("dividend_cash", "DOUBLE"),
        ColumnDef("split_ratio", "DOUBLE"),
        ColumnDef("raw_payload", "JSON"),
        ColumnDef("source", "VARCHAR"),
        ColumnDef("batch_id", "VARCHAR", ("NOT NULL",)),
        ColumnDef("ingest_time", "TIMESTAMP", ("NOT NULL",)),
    ),
    primary_key=("market", "supplier_symbol", "event_type", "effective_date", "batch_id"),
)


ADJUSTMENTS_TABLE = TableSchema(
    name="adjustments",
    columns=(
        ColumnDef("market", "VARCHAR", ("NOT NULL",)),
        ColumnDef("supplier_symbol", "VARCHAR", ("NOT NULL",)),
        ColumnDef("date", "DATE", ("NOT NULL",)),
        ColumnDef("adj_factor_qfq", "DOUBLE", ("NOT NULL",)),
        ColumnDef("adj_factor_hfq", "DOUBLE", ("NOT NULL",)),
        ColumnDef("version", "VARCHAR", ("NOT NULL",)),
        ColumnDef("build_time", "TIMESTAMP", ("NOT NULL",)),
        ColumnDef("source_events_hash", "VARCHAR", ("NOT NULL",)),
    ),
    primary_key=("market", "supplier_symbol", "date", "version"),
)


def baseline_tables() -> Sequence[TableSchema]:
    """Return the schemas that compose the PRD-0 baseline."""

    return (RAW_BASE_TABLE, NORMALIZATION_BASE_TABLE)


def ensure_baseline_tables(conn: DuckDBPyConnection) -> None:
    """Create all baseline tables on the provided DuckDB connection."""

    for table in baseline_tables():
        table.ensure(conn)


def create_baseline_ddl() -> Iterable[str]:
    """Yield CREATE TABLE statements for the baseline schemas."""

    for table in baseline_tables():
        yield table.create_ddl()


def corporate_action_tables() -> Sequence[TableSchema]:
    """Return the schemas used for corporate action storage and factors."""

    return (CORPORATE_ACTIONS_TABLE, ADJUSTMENTS_TABLE)


def ensure_corporate_action_tables(conn: DuckDBPyConnection) -> None:
    """Create corporate action-related tables on the provided connection."""

    for table in corporate_action_tables():
        table.ensure(conn)


def create_corporate_action_ddl() -> Iterable[str]:
    """Yield CREATE TABLE statements for corporate action storage."""

    for table in corporate_action_tables():
        yield table.create_ddl()
