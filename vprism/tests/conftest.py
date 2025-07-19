"""Pytest configuration and fixtures for vprism testing."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_setup() -> AsyncGenerator[None, None]:
    """Set up async test environment."""
    yield


@pytest.fixture
def sample_stock_symbols() -> list[str]:
    """Sample stock symbols for testing."""
    return ["000001", "600519", "000858", "601318", "000002"]


@pytest.fixture
def sample_market_data() -> dict[str, str]:
    """Sample market data configuration for testing."""
    return {
        "market": "cn",
        "asset_type": "stock",
        "timeframe": "1d",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    }