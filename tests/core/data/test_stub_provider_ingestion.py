from __future__ import annotations

from datetime import datetime

import duckdb
import pytest

from vprism.core.data import schema
from vprism.core.data.providers.stub_provider import StubProviderRow, VPrismStubProvider
from vprism.core.exceptions.base import DataValidationError


def test_stub_provider_inserts_valid_rows() -> None:
    conn = duckdb.connect(database=":memory:")
    schema.ensure_baseline_tables(conn)
    provider = VPrismStubProvider(conn)

    rows = [
        StubProviderRow(
            supplier_symbol="000001.SZ",
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
            open=10.0,
            high=10.5,
            low=9.8,
            close=10.2,
            volume=1000.0,
            provider="stub",
        )
    ]

    provider.ingest_rows(rows)

    stored_rows = conn.execute(
        "SELECT supplier_symbol, close, volume FROM raw_schema"
    ).fetchall()

    assert stored_rows == [("000001.SZ", 10.2, 1000.0)]


def test_stub_provider_rejects_missing_required_fields() -> None:
    conn = duckdb.connect(database=":memory:")
    schema.ensure_baseline_tables(conn)
    provider = VPrismStubProvider(conn)

    with pytest.raises(DataValidationError) as exc_info:
        provider.ingest_rows(
            [
                {
                    "supplier_symbol": "000001.SZ",
                    "open": 10.0,
                }
            ]
        )

    assert exc_info.value.validation_errors == {
        "rows": [
            {
                "index": 0,
                "missing_fields": ["timestamp"],
            }
        ]
    }
    assert conn.execute("SELECT COUNT(*) FROM raw_schema").fetchone()[0] == 0
