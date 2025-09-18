"""Data validation module."""

from vprism.core.validation.consistency import ConsistencyReport, DataConsistencyValidator
from vprism.core.validation.quality import DataQualityScorer, DataQualityValidator
from vprism.core.validation.schema_assertions import (
    assert_baseline_tables,
    assert_table_matches_schema,
    assert_tables_match_schemas,
)

__all__ = [
    "DataQualityValidator",
    "DataQualityScorer",
    "ConsistencyReport",
    "DataConsistencyValidator",
    "assert_table_matches_schema",
    "assert_tables_match_schemas",
    "assert_baseline_tables",
]
