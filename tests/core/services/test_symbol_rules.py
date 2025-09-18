from __future__ import annotations

import pytest

from vprism.core.exceptions.base import UnresolvedSymbolError
from vprism.core.models.market import AssetType, MarketType
from vprism.core.services.symbols import SymbolService


@pytest.mark.parametrize(
    "raw_symbol, asset_type, expected",
    [
        ("600000.SS", AssetType.STOCK, "CN:STOCK:SH600000"),
        ("sz000002", AssetType.STOCK, "CN:STOCK:SZ000002"),
        ("000001", AssetType.STOCK, "CN:STOCK:000001"),
        ("159915.SZ", AssetType.FUND, "CN:FUND:SZ159915"),
        ("of110022", AssetType.FUND, "CN:FUND:OF110022"),
        ("110022", AssetType.FUND, "CN:FUND:110022"),
        ("000300.SH", AssetType.INDEX, "CN:INDEX:SH000300"),
        ("sz399001", AssetType.INDEX, "CN:INDEX:SZ399001"),
    ],
)
def test_default_rules_cover_cn_assets(
    raw_symbol: str, asset_type: AssetType, expected: str
) -> None:
    service = SymbolService()

    result = service.normalize(raw_symbol, MarketType.CN, asset_type)

    assert result.canonical == expected


def test_default_rules_support_generic_uppercase() -> None:
    service = SymbolService()

    result = service.normalize("aapl", MarketType.US, AssetType.STOCK)

    assert result.canonical == "US:STOCK:AAPL"


def test_default_rules_raise_for_unknown_pattern() -> None:
    service = SymbolService()

    with pytest.raises(UnresolvedSymbolError):
        service.normalize("??symbol??", MarketType.CN, AssetType.STOCK)
