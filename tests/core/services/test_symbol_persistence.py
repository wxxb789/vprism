from __future__ import annotations

from datetime import datetime

import pytest

from vprism.core.data.storage.duckdb_factory import VPrismDuckDBFactory
from vprism.core.models.market import AssetType, MarketType
from vprism.core.services.symbols import SymbolService


def _fetch_symbol_map_rows(conn) -> list[tuple]:
    return conn.execute(
        """
        SELECT c_symbol, raw_symbol, market, asset_type, provider_hint, rule_id, created_at
        FROM symbol_map
        ORDER BY raw_symbol
        """
    ).fetchall()


@pytest.fixture()
def duckdb_conn():
    factory = VPrismDuckDBFactory()
    with factory.connection() as conn:
        yield conn


def test_persistence_inserts_row_on_first_normalization(duckdb_conn) -> None:
    service = SymbolService(persistence_conn=duckdb_conn)

    result = service.normalize("600000.SS", MarketType.CN, AssetType.STOCK, provider_hint="yfinance")

    rows = _fetch_symbol_map_rows(duckdb_conn)
    assert len(rows) == 1
    (c_symbol, raw_symbol, market, asset_type, provider_hint, rule_id, created_at) = rows[0]
    assert c_symbol == result.canonical
    assert raw_symbol == "600000.SS"
    assert market == MarketType.CN.value
    assert asset_type == AssetType.STOCK.value
    assert provider_hint == "yfinance"
    assert rule_id == result.rule_id
    assert isinstance(created_at, datetime)


def test_persistence_skips_duplicates_with_insert_or_ignore(duckdb_conn) -> None:
    primary_service = SymbolService(persistence_conn=duckdb_conn)
    primary_service.normalize("600000.SS", MarketType.CN, AssetType.STOCK, provider_hint="yfinance")

    secondary_service = SymbolService(persistence_conn=duckdb_conn)
    secondary_service.normalize("600000.SS", MarketType.CN, AssetType.STOCK, provider_hint="akshare")

    rows = _fetch_symbol_map_rows(duckdb_conn)
    assert len(rows) == 1
    (_, _, _, _, provider_hint, _, _) = rows[0]
    assert provider_hint == "yfinance"


def test_persistence_allows_null_provider_hint(duckdb_conn) -> None:
    service = SymbolService(persistence_conn=duckdb_conn)

    service.normalize("000001.SZ", MarketType.CN, AssetType.STOCK)

    rows = _fetch_symbol_map_rows(duckdb_conn)
    assert len(rows) == 1
    (_, raw_symbol, _, _, provider_hint, _, _) = rows[0]
    assert raw_symbol == "000001.SZ"
    assert provider_hint is None
