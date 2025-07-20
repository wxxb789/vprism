"""
Tests for the dual API design.

This module tests both the simple API (vprism.get()) and the builder API
(vprism.query().build()) to ensure they work correctly and share the same
underlying implementation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

import vprism
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


class TestDualAPI:
    """Test suite for dual API design."""

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

    def test_simple_api_imports(self):
        """Test that simple API functions are properly imported."""
        # Test that functions exist
        assert hasattr(vprism, 'get')
        assert hasattr(vprism, 'aget')
        assert callable(vprism.get)
        assert callable(vprism.aget)

    def test_builder_api_imports(self):
        """Test that builder API components are properly imported."""
        # Test that builder components exist
        assert hasattr(vprism, 'query')
        assert hasattr(vprism, 'execute')
        assert hasattr(vprism, 'execute_sync')
        assert hasattr(vprism, 'QueryBuilder')
        
        # Test that they are callable/instantiable
        assert callable(vprism.query)
        assert callable(vprism.execute)
        assert callable(vprism.execute_sync)

    def test_query_builder_creation(self):
        """Test creating QueryBuilder through vprism.query()."""
        builder = vprism.query()
        assert isinstance(builder, vprism.QueryBuilder)

    def test_query_builder_fluent_interface(self):
        """Test fluent interface of QueryBuilder."""
        query = (vprism.query()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001"])
            .timeframe(TimeFrame.DAY_1)
            .build())

        assert isinstance(query, DataQuery)
        assert query.asset == AssetType.STOCK
        assert query.market == MarketType.CN
        assert query.symbols == ["000001"]
        assert query.timeframe == TimeFrame.DAY_1

    @patch('vprism.VPrismClient')
    def test_simple_api_sync(self, mock_client_class, sample_response):
        """Test simple synchronous API."""
        mock_client = Mock()
        mock_client.get_sync.return_value = sample_response
        mock_client_class.return_value = mock_client

        result = vprism.get(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"]
        )

        assert result == sample_response
        mock_client.get_sync.assert_called_once_with(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"]
        )

    @pytest.mark.asyncio
    @patch('vprism.VPrismClient')
    async def test_simple_api_async(self, mock_client_class, sample_response):
        """Test simple asynchronous API."""
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=sample_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await vprism.aget(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"]
        )

        assert result == sample_response
        mock_client.get.assert_called_once_with(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"]
        )

    @pytest.mark.asyncio
    @patch('vprism.VPrismClient')
    async def test_builder_api_async(self, mock_client_class, sample_response):
        """Test builder API with async execution."""
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=sample_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        query = (vprism.query()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001"])
            .build())

        result = await vprism.execute(query)

        assert result == sample_response
        mock_client.get.assert_called_once()

    @patch('vprism.VPrismClient')
    def test_builder_api_sync(self, mock_client_class, sample_response):
        """Test builder API with sync execution."""
        mock_client = Mock()
        mock_client.get_sync.return_value = sample_response
        mock_client_class.return_value = mock_client

        query = (vprism.query()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001"])
            .build())

        result = vprism.execute_sync(query)

        assert result == sample_response
        mock_client.get_sync.assert_called_once()

    @pytest.mark.asyncio
    @patch('vprism.VPrismClient')
    async def test_api_equivalence(self, mock_client_class, sample_response):
        """Test that both APIs produce equivalent results."""
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=sample_response)
        mock_client.get_sync = Mock(return_value=sample_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Simple API
        simple_result = await vprism.aget(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
        )

        # Builder API
        query = (vprism.query()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001"])
            .timeframe(TimeFrame.DAY_1)
            .build())
        builder_result = await vprism.execute(query)

        # Results should be the same
        assert simple_result == builder_result

    def test_complex_builder_query(self):
        """Test complex query construction with builder API."""
        query = (vprism.query()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001", "000002"])
            .timeframe(TimeFrame.DAY_1)
            .date_range("2024-01-01", "2024-12-31")
            .provider("tushare")
            .limit(100)
            .filter("adj", "qfq")
            .build())

        assert query.asset == AssetType.STOCK
        assert query.market == MarketType.CN
        assert query.symbols == ["000001", "000002"]
        assert query.timeframe == TimeFrame.DAY_1
        assert query.start == datetime(2024, 1, 1)
        assert query.end == datetime(2024, 12, 31)
        assert query.provider == "tushare"
        assert query.limit == 100
        assert query.filters == {"adj": "qfq"}

    @pytest.mark.asyncio
    @patch('vprism.VPrismClient')
    async def test_date_handling_in_execute(self, mock_client_class, sample_response):
        """Test that execute properly handles datetime objects."""
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=sample_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        start_dt = datetime(2024, 1, 1)
        end_dt = datetime(2024, 12, 31)

        query = (vprism.query()
            .asset(AssetType.STOCK)
            .start(start_dt)
            .end(end_dt)
            .build())

        await vprism.execute(query)

        # Verify that datetime objects were converted to ISO strings
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs['start'] == "2024-01-01T00:00:00"
        assert call_kwargs['end'] == "2024-12-31T00:00:00"

    @pytest.mark.asyncio
    @patch('vprism.VPrismClient')
    async def test_none_date_handling(self, mock_client_class, sample_response):
        """Test that None dates are handled properly."""
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=sample_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        query = (vprism.query()
            .asset(AssetType.STOCK)
            .build())

        await vprism.execute(query)

        # Verify that None dates are passed as None
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs['start'] is None
        assert call_kwargs['end'] is None

    def test_builder_reusability(self):
        """Test that builders can be reused and modified."""
        base_builder = (vprism.query()
            .asset(AssetType.STOCK)
            .market(MarketType.CN))

        # Create different queries from the same base
        query1 = base_builder.copy().symbols(["000001"]).build()
        query2 = base_builder.copy().symbols(["000002"]).timeframe(TimeFrame.HOUR_1).build()

        assert query1.symbols == ["000001"]
        assert query1.timeframe is None

        assert query2.symbols == ["000002"]
        assert query2.timeframe == TimeFrame.HOUR_1

        # Both should have the same base properties
        assert query1.asset == query2.asset == AssetType.STOCK
        assert query1.market == query2.market == MarketType.CN

    def test_api_style_documentation_examples(self):
        """Test examples that would appear in documentation."""
        # Simple API examples
        assert callable(vprism.get)
        assert callable(vprism.aget)

        # Builder API examples
        builder = vprism.query()
        assert builder is not None

        # Complex builder example
        query = (vprism.query()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001"])
            .timeframe(TimeFrame.DAY_1)
            .date_range("2024-01-01", "2024-12-31")
            .provider("tushare")
            .limit(100)
            .build())

        assert isinstance(query, DataQuery)

    def test_all_exports_available(self):
        """Test that all expected exports are available."""
        expected_exports = [
            'Asset', 'AssetType', 'DataPoint', 'DataQuery', 'DataResponse',
            'MarketType', 'TimeFrame', 'VPrismClient', 'VPrismException',
            'QueryBuilder', 'get', 'aget', 'query', 'execute', 'execute_sync'
        ]

        for export in expected_exports:
            assert hasattr(vprism, export), f"Missing export: {export}"

    def test_backward_compatibility(self):
        """Test that existing simple API usage still works."""
        # These should not raise import errors
        from vprism import get, aget, AssetType, MarketType

        # Basic usage should work
        assert AssetType.STOCK == "stock"
        assert MarketType.CN == "cn"
        assert callable(get)
        assert callable(aget)