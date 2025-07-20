"""
Integration tests for VPrismClient with DataService.

This module tests the integration between the client and data service,
ensuring that the client properly delegates to the data service and
handles date parsing, streaming, and error cases.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from vprism.core.client import VPrismClient
from vprism.core.exceptions import VPrismException
from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    MarketType,
    ProviderInfo,
    ResponseMetadata,
    TimeFrame,
)


class TestVPrismClientIntegration:
    """Test suite for VPrismClient integration with DataService."""

    @pytest.fixture
    def sample_data_point(self):
        """Sample data point for testing."""
        return DataPoint(
            symbol="000001",
            timestamp=datetime.now(),
            open=Decimal("10.00"),
            high=Decimal("10.50"),
            low=Decimal("9.50"),
            close=Decimal("10.25"),
            volume=Decimal("1000000"),
        )

    @pytest.fixture
    def sample_response(self, sample_data_point):
        """Sample data response for testing."""
        sample_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
        )
        return DataResponse(
            data=[sample_data_point],
            metadata=ResponseMetadata(
                execution_time_ms=100.0,
                record_count=1,
                cache_hit=False,
            ),
            source=ProviderInfo(name="test_provider"),
            query=sample_query,
        )

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization and cleanup."""
        client = VPrismClient()
        
        # Client should not be initialized yet
        assert not client._initialized
        assert client._data_service is None

        # Use async context manager
        async with client:
            assert client._initialized
            assert client._data_service is not None

    @pytest.mark.asyncio
    async def test_get_data_basic_query(self, sample_response):
        """Test basic data retrieval through client."""
        with patch('vprism.core.client.DataService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_data = AsyncMock(return_value=sample_response)
            mock_service_class.return_value = mock_service

            client = VPrismClient()
            
            # Test basic query
            result = await client.get(
                asset=AssetType.STOCK,
                market=MarketType.CN,
                symbols=["000001"],
            )

            assert result == sample_response
            mock_service.get_data.assert_called_once()
            
            # Verify query parameters
            call_args = mock_service.get_data.call_args[0][0]
            assert call_args.asset == AssetType.STOCK
            assert call_args.market == MarketType.CN
            assert call_args.symbols == ["000001"]

    @pytest.mark.asyncio
    async def test_get_data_with_date_parsing(self, sample_response):
        """Test data retrieval with date string parsing."""
        with patch('vprism.core.client.DataService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_data = AsyncMock(return_value=sample_response)
            mock_service_class.return_value = mock_service

            client = VPrismClient()
            
            # Test with date strings
            result = await client.get(
                asset=AssetType.STOCK,
                start="2024-01-01",
                end="2024-12-31",
            )

            assert result == sample_response
            
            # Verify date parsing
            call_args = mock_service.get_data.call_args[0][0]
            assert call_args.start == datetime(2024, 1, 1)
            assert call_args.end == datetime(2024, 12, 31)

    @pytest.mark.asyncio
    async def test_get_data_sync_wrapper(self, sample_response):
        """Test synchronous wrapper method behavior in async context."""
        client = VPrismClient()
        
        # In an async context (like pytest-asyncio), sync method should raise an error
        with pytest.raises(VPrismException) as exc_info:
            client.get_sync(
                asset=AssetType.STOCK,
                symbols=["000001"],
            )

        assert exc_info.value.error_code == "SYNC_IN_ASYNC_CONTEXT"

    def test_get_data_sync_wrapper_no_event_loop(self, sample_response):
        """Test synchronous wrapper method without event loop."""
        with patch('vprism.core.client.DataService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_data = AsyncMock(return_value=sample_response)
            mock_service_class.return_value = mock_service

            client = VPrismClient()
            
            # Test sync method (this will work outside of async context)
            result = client.get_sync(
                asset=AssetType.STOCK,
                symbols=["000001"],
            )

            assert result == sample_response
            mock_service.get_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_data_basic(self, sample_response):
        """Test basic streaming functionality."""
        with patch('vprism.core.client.DataService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_data = AsyncMock(return_value=sample_response)
            mock_service_class.return_value = mock_service

            client = VPrismClient()
            
            # Test streaming
            responses = []
            async for response in client.stream(
                asset=AssetType.STOCK,
                symbols=["000001"],
            ):
                responses.append(response)

            assert len(responses) == 1
            assert responses[0] == sample_response

    @pytest.mark.asyncio
    async def test_date_parsing_various_formats(self):
        """Test date parsing with various formats."""
        client = VPrismClient()
        
        # Test different date formats
        test_cases = [
            ("2024-01-01", datetime(2024, 1, 1)),
            ("2024-01-01T10:30:00", datetime(2024, 1, 1, 10, 30, 0)),
            ("2024-01-01T10:30:00Z", datetime(2024, 1, 1, 10, 30, 0)),
            ("2024-01-01 10:30:00", datetime(2024, 1, 1, 10, 30, 0)),
            ("2024/01/01", datetime(2024, 1, 1)),
            ("2024/01/01 10:30:00", datetime(2024, 1, 1, 10, 30, 0)),
        ]

        for date_str, expected_dt in test_cases:
            result = client._parse_date_string(date_str)
            assert result == expected_dt

    @pytest.mark.asyncio
    async def test_date_parsing_invalid_format(self):
        """Test date parsing with invalid format."""
        client = VPrismClient()
        
        with pytest.raises(VPrismException) as exc_info:
            client._parse_date_string("invalid-date")

        assert exc_info.value.error_code == "INVALID_DATE_FORMAT"

    @pytest.mark.asyncio
    async def test_date_parsing_empty_string(self):
        """Test date parsing with empty string."""
        client = VPrismClient()
        
        with pytest.raises(VPrismException) as exc_info:
            client._parse_date_string("")

        assert exc_info.value.error_code == "INVALID_DATE_FORMAT"

    @pytest.mark.asyncio
    async def test_client_configuration(self):
        """Test client configuration."""
        client = VPrismClient(config={"key1": "value1"})
        
        # Initial configuration
        assert client.config["key1"] == "value1"
        
        # Update configuration
        client.configure(key2="value2", key1="updated_value1")
        assert client.config["key1"] == "updated_value1"
        assert client.config["key2"] == "value2"
        
        # Configuration should reset initialization
        assert not client._initialized

    @pytest.mark.asyncio
    async def test_error_handling_data_service_failure(self):
        """Test error handling when data service fails."""
        with patch('vprism.core.client.DataService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_data = AsyncMock(
                side_effect=VPrismException("Service error", "SERVICE_ERROR")
            )
            mock_service_class.return_value = mock_service

            client = VPrismClient()
            
            with pytest.raises(VPrismException) as exc_info:
                await client.get(asset=AssetType.STOCK)

            assert exc_info.value.error_code == "SERVICE_ERROR"

    @pytest.mark.asyncio
    async def test_uninitialized_service_error(self):
        """Test error when service is not initialized."""
        client = VPrismClient()
        # Manually set service to None to simulate initialization failure
        client._data_service = None
        client._initialized = True  # But service is None
        
        with pytest.raises(VPrismException) as exc_info:
            await client.get(asset=AssetType.STOCK)

        assert exc_info.value.error_code == "INITIALIZATION_ERROR"

    @pytest.mark.asyncio
    async def test_client_with_all_parameters(self, sample_response):
        """Test client with all possible parameters."""
        with patch('vprism.core.client.DataService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_data = AsyncMock(return_value=sample_response)
            mock_service_class.return_value = mock_service

            client = VPrismClient()
            
            result = await client.get(
                asset=AssetType.STOCK,
                market=MarketType.CN,
                symbols=["000001", "000002"],
                provider="test_provider",
                timeframe=TimeFrame.DAY_1,
                start="2024-01-01",
                end="2024-12-31",
                limit=100,
                custom_param="custom_value",
            )

            assert result == sample_response
            
            # Verify all parameters were passed correctly
            call_args = mock_service.get_data.call_args[0][0]
            assert call_args.asset == AssetType.STOCK
            assert call_args.market == MarketType.CN
            assert call_args.symbols == ["000001", "000002"]
            assert call_args.provider == "test_provider"
            assert call_args.timeframe == TimeFrame.DAY_1
            assert call_args.start == datetime(2024, 1, 1)
            assert call_args.end == datetime(2024, 12, 31)
            assert call_args.limit == 100
            assert call_args.filters == {"custom_param": "custom_value"}

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, sample_response):
        """Test handling of concurrent requests."""
        with patch('vprism.core.client.DataService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_data = AsyncMock(return_value=sample_response)
            mock_service_class.return_value = mock_service

            client = VPrismClient()
            
            # Make multiple concurrent requests
            tasks = [
                client.get(asset=AssetType.STOCK, symbols=[f"00000{i}"])
                for i in range(5)
            ]
            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            for result in results:
                assert result == sample_response

            # Service should be called for each request
            assert mock_service.get_data.call_count == 5