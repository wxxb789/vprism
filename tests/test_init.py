"""
Tests for main vprism module.

This module contains tests for the main module convenience functions
and public API exports.
"""

import pytest

import vprism
from vprism.core.exceptions import VPrismException
from vprism.core.models import AssetType


class TestVPrismModule:
    """Test main vprism module."""

    def test_version_available(self):
        """Test that version is available."""
        assert hasattr(vprism, "__version__")
        assert vprism.__version__ == "0.1.0"

    def test_all_exports_available(self):
        """Test that all expected exports are available."""
        expected_exports = [
            "Asset",
            "AssetType",
            "DataPoint",
            "DataQuery",
            "DataResponse",
            "MarketType",
            "TimeFrame",
            "VPrismClient",
            "VPrismException",
        ]

        for export in expected_exports:
            assert hasattr(vprism, export)
            assert export in vprism.__all__

    def test_convenience_get_function_exists(self):
        """Test that convenience get function exists."""
        assert hasattr(vprism, "get")
        assert callable(vprism.get)

    def test_convenience_aget_function_exists(self):
        """Test that convenience aget function exists."""
        assert hasattr(vprism, "aget")
        assert callable(vprism.aget)

    def test_convenience_get_function_not_implemented(self):
        """Test that convenience get function raises not implemented."""
        with pytest.raises(VPrismException) as exc_info:
            vprism.get(asset=AssetType.STOCK)

        assert exc_info.value.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_convenience_aget_function_not_implemented(self):
        """Test that convenience aget function raises not implemented."""
        with pytest.raises(VPrismException) as exc_info:
            await vprism.aget(asset=AssetType.STOCK)

        assert exc_info.value.error_code == "NOT_IMPLEMENTED"

    def test_imports_work_correctly(self):
        """Test that imports work correctly."""
        # Test that we can create instances of imported classes
        asset_type = vprism.AssetType.STOCK
        assert asset_type == "stock"

        # Test that we can create a client
        client = vprism.VPrismClient()
        assert client is not None

        # Test that we can create an exception
        exc = vprism.VPrismException("test", "TEST_ERROR")
        assert exc.message == "test"
        assert exc.error_code == "TEST_ERROR"
