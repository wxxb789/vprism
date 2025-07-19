"""Tests for vprism data models."""

import pytest
from decimal import Decimal
from datetime import datetime
from pydantic import ValidationError

from vprism.models.enums import AssetType, MarketType, TimeFrame


class TestEnums:
    """Test enumeration classes."""

    def test_asset_type_values(self):
        """Test AssetType enum values."""
        assert AssetType.STOCK == "stock"
        assert AssetType.BOND == "bond"
        assert AssetType.ETF == "etf"
        assert AssetType.CRYPTO == "crypto"

    def test_market_type_values(self):
        """Test MarketType enum values."""
        assert MarketType.CN == "cn"
        assert MarketType.US == "us"
        assert MarketType.HK == "hk"

    def test_timeframe_values(self):
        """Test TimeFrame enum values."""
        assert TimeFrame.TICK == "tick"
        assert TimeFrame.DAY_1 == "1d"
        assert TimeFrame.MINUTE_1 == "1m"

    def test_enum_iteration(self):
        """Test enum iteration."""
        assets = list(AssetType)
        assert len(assets) >= 8
        assert AssetType.STOCK in assets

    def test_enum_string_compatibility(self):
        """Test enum string compatibility."""
        assert AssetType.STOCK.value == "stock"
        assert AssetType.STOCK == "stock"