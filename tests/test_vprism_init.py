"""
Tests for vprism package initialization and convenience functions.

This module tests the main package interface and convenience functions
to ensure they work correctly and provide the expected API.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import vprism
from vprism.core.models import AssetType, DataResponse, MarketType, ResponseMetadata, ProviderInfo, DataQuery


class TestVPrismPackage:
    """Test vprism package initialization and exports."""

    def test_package_exports(self):
        """Test that all expected symbols are exported."""
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
            assert hasattr(vprism, export), f"Missing export: {export}"

    def test_version_attribute(self):
        """Test that version is defined."""
        assert hasattr(vprism, "__version__")
        assert isinstance(vprism.__version__, str)
        assert vprism.__version__ == "0.1.0"

    @patch('vprism.VPrismClient')
    def test_get_convenience_function(self, mock_client_class):
        """Test the synchronous get convenience function."""
        # Mock the client and its get_sync method
        mock_client = MagicMock()
        mock_response = DataResponse(
            data=[],
            metadata=ResponseMetadata(execution_time_ms=100, record_count=0),
            source=ProviderInfo(name="test"),
            query=DataQuery(asset=AssetType.STOCK)
        )
        mock_client.get_sync.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Call the convenience function
        result = vprism.get(asset="stock", market="cn", symbols=["000001"])
        
        # Verify the client was created and called correctly
        mock_client_class.assert_called_once()
        mock_client.get_sync.assert_called_once_with(
            asset="stock", market="cn", symbols=["000001"]
        )
        assert result == mock_response

    @pytest.mark.asyncio
    @patch('vprism.VPrismClient')
    async def test_aget_convenience_function(self, mock_client_class):
        """Test the asynchronous aget convenience function."""
        # Mock the client and its get method
        mock_client = AsyncMock()
        mock_response = DataResponse(
            data=[],
            metadata=ResponseMetadata(execution_time_ms=100, record_count=0),
            source=ProviderInfo(name="test"),
            query=DataQuery(asset=AssetType.STOCK)
        )
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client
        
        # Call the convenience function
        result = await vprism.aget(asset="stock", market="cn", symbols=["000001"])
        
        # Verify the client was created and used as async context manager
        mock_client_class.assert_called_once()
        mock_client.__aenter__.assert_called_once()
        mock_client.get.assert_called_once_with(
            asset="stock", market="cn", symbols=["000001"]
        )
        mock_client.__aexit__.assert_called_once()
        assert result == mock_response

    def test_package_docstring(self):
        """Test that package has proper docstring."""
        assert vprism.__doc__ is not None
        assert "vprism" in vprism.__doc__
        assert "Financial Data Infrastructure" in vprism.__doc__