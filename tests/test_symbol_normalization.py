from __future__ import annotations

import pytest

from vprism.core.models.market import MarketType
from vprism.core.services.symbol_normalization import SymbolNormalizer, get_symbol_normalizer


@pytest.mark.asyncio
async def test_cn_six_digit_kept():
    normalizer = SymbolNormalizer()
    result = await normalizer.normalize(["000001"], market=MarketType.CN)
    assert result[0].c_symbol == "000001"
    assert result[0].rule == "cn_six_digit"
    assert result[0].unresolved is False


@pytest.mark.asyncio
async def test_us_symbol_upper():
    normalizer = SymbolNormalizer()
    result = await normalizer.normalize(["aapl"], market=MarketType.US)
    assert result[0].c_symbol == "AAPL"
    assert result[0].rule == "us_symbol"


@pytest.mark.asyncio
async def test_unresolved_fallback():
    normalizer = SymbolNormalizer()
    result = await normalizer.normalize(["??X"], market=MarketType.CN)
    assert result[0].unresolved is True
    assert result[0].rule == "fallback"


@pytest.mark.asyncio
async def test_cached_singleton():
    a = get_symbol_normalizer()
    b = get_symbol_normalizer()
    assert a is b
