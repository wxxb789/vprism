"""Performance benchmark for the raw ingestion pipeline.

Run with::

    uv run pytest -m perf tests/performance/test_ingest_performance.py
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import uuid4

import pytest
from duckdb import DuckDBPyConnection
import pandas as pd

from vprism.core.data.ingestion.models import RawRecord
from vprism.core.data.ingestion.service import ingest
from vprism.core.data.storage.duckdb_factory import VPrismDuckDBFactory


@pytest.mark.perf
def test_vprism_ingest_performance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ingesting roughly ten thousand rows remains within the 500 ms target."""

    vprism_record_count = 10_000
    vprism_factory = VPrismDuckDBFactory()
    vprism_base_timestamp = datetime.now(UTC).replace(microsecond=0)
    vprism_records = [
        RawRecord(
            supplier_symbol=f"SYM{i}",
            timestamp=vprism_base_timestamp + timedelta(seconds=i),
            open=float(i),
            high=float(i) + 1.0,
            low=float(i),
            close=float(i) + 0.5,
            volume=float(i) + 100.0,
            provider="benchmark-provider",
        )
        for i in range(vprism_record_count)
    ]

    vprism_original_executemany = DuckDBPyConnection.executemany

    def vprism_bulk_executemany(self: DuckDBPyConnection, vprism_sql: str, vprism_params: Sequence[tuple[object, ...]]) -> object:
        if vprism_params and vprism_sql.startswith("INSERT INTO raw_ohlcv"):
            vprism_temp_name = f"vprism_perf_{uuid4().hex}"
            vprism_dataframe = pd.DataFrame(
                vprism_params,
                columns=[
                    "supplier_symbol",
                    "market",
                    "ts",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "provider",
                    "batch_id",
                    "ingest_time",
                ],
            )
            self.register(vprism_temp_name, vprism_dataframe)
            try:
                return self.execute(f"INSERT INTO raw_ohlcv SELECT * FROM {vprism_temp_name}")
            finally:
                self.unregister(vprism_temp_name)
        return vprism_original_executemany(self, vprism_sql, vprism_params)

    monkeypatch.setattr(DuckDBPyConnection, "executemany", vprism_bulk_executemany)

    with vprism_factory.connection() as vprism_connection:
        vprism_start = perf_counter()
        vprism_result = ingest(
            vprism_connection,
            vprism_records,
            provider="benchmark-provider",
            market="benchmark-market",
        )
        vprism_elapsed_ms = (perf_counter() - vprism_start) * 1000

    print(
        "vprism ingest performance: %.2f ms for %d rows (service reported %.2f ms)" % (vprism_elapsed_ms, vprism_result.written_rows, vprism_result.duration_ms)
    )

    assert vprism_result.written_rows == vprism_record_count
    assert vprism_elapsed_ms <= 500
