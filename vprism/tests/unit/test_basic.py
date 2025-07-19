"""Basic tests to verify TDD environment setup."""

import pytest


def test_tdd_environment_setup():
    """Test that TDD environment is properly configured."""
    assert True


@pytest.mark.asyncio
async def test_async_support():
    """Test async support in pytest."""
    await asyncio.sleep(0.001)
    assert True


import asyncio


def test_sample_data(sample_stock_symbols):
    """Test sample data fixture."""
    assert isinstance(sample_stock_symbols, list)
    assert len(sample_stock_symbols) == 5
    assert "000001" in sample_stock_symbols


def test_market_data(sample_market_data):
    """Test market data fixture."""
    assert sample_market_data["market"] == "cn"
    assert sample_market_data["asset_type"] == "stock"