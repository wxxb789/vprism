"""Data validation module."""

from vprism.core.validation.schema_assertions import (
    assert_baseline_tables,
    assert_table_matches_schema,
    assert_tables_match_schemas,
)

__all__ = [
    "assert_table_matches_schema",
    "assert_tables_match_schemas",
    "assert_baseline_tables",
]
