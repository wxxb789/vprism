"""
Tests for the unified data service implementation.

This module tests the DataService class which integrates routing, caching,
and provider management to provide intelligent data retrieval.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from vprism.core.cache import MultiLevelCache
from vprism.core.data_router import DataRouter
from vprism.core.data_service import DataService
from vprism.core.exceptions import (
    DataValidationException,
    NoAvailableProviderException,
    VPrismException,
)
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
from vprism.core.provider_abstraction import (
    EnhancedDataProvider,
    EnhancedProviderRegistry,
)


class TestDataService:
    """Test suite for DataService class."""

    @pytest.fixture
    def mock_cache(self):
        """Mock cache for testing."""
        cache = Mock(spec=MultiLevelCache)
        cache.get_data = AsyncMock(return_value=None)
        cache.set_data = AsyncMock()
        return cache

    @pytest.fixture
    def mock_router(self):
        """Mock router for testing."""
        router = Mock(spec=DataRouter)
        router.execute_query = AsyncMock()
        return router

    @pytest.fixture
    def mock_provider_registry(self):
        """Mock provider registry for testing."""
        registry = Mock(spec=EnhancedProviderRegistry)
        return registry

    @pytest.fixture
    def data_service(self, mock_cache, mock_router, mock_provider_registry):
        """DataService instance for testing."""
        return DataService(
            cache=mock_cache,
            router=mock_router,
            provider_registry=mock_provider_registry,
        )

    @pytest.fixture
    def sample_query(self):
        """Sample data query for testing."""
        return DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
        )

    @pytest.fixture
    def sample_data_point(self):
        """Sample data point for testing."""
        return DataPoint(
            symbol="000001",
            timestamp=datetime.now(timezone.utc),
            open=Decimal("10.00"),
            high=Decimal("10.50"),
            low=Decimal("9.50"),
            close=Decimal("10.25"),
            volume=Decimal("1000000"),
        )

    @pytest.fixture
    def sample_response(self, sample_query, sample_data_point):
        """Sample data response for testing."""
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
    async def test_get_data_cache_hit(
        self, data_service, mock_cache, sample_query, sample_response
    ):
        """Test successful data retrieval from cache."""
        # Arrange
        mock_cache.get_data.return_value = sample_response

        # Act
        result = await data_service.get_data(sample_query)

        # Assert
        assert result.data == sample_response.data
        assert result.source == sample_response.source
        assert result.metadata.cache_hit is True
        mock_cache.get_data.assert_called_once_with(sample_query)
        # Router should not be called for cache hits
        data_service.router.execute_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_data_cache_miss_provider_success(
        self, data_service, mock_cache, mock_router, sample_query, sample_response
    ):
        """Test successful data retrieval from provider after cache miss."""
        # Arrange
        mock_cache.get_data.return_value = None  # Cache miss
        mock_router.execute_query.return_value = sample_response

        # Act
        result = await data_service.get_data(sample_query)

        # Assert
        assert result.data == sample_response.data
        assert result.source == sample_response.source
        assert result.metadata.cache_hit is False
        mock_cache.get_data.assert_called_once_with(sample_query)
        mock_router.execute_query.assert_called_once_with(sample_query)
        # Cache should be called with the enhanced response
        assert mock_cache.set_data.call_count == 1

    @pytest.mark.asyncio
    async def test_get_data_provider_failure(
        self, data_service, mock_cache, mock_router, sample_query
    ):
        """Test handling of provider failure."""
        # Arrange
        mock_cache.get_data.return_value = None  # Cache miss
        mock_router.execute_query.side_effect = NoAvailableProviderException(
            "No providers available"
        )

        # Act & Assert
        with pytest.raises(NoAvailableProviderException):
            await data_service.get_data(sample_query)

        mock_cache.get_data.assert_called_once_with(sample_query)
        mock_router.execute_query.assert_called_once_with(sample_query)
        # Cache should not be updated on failure
        mock_cache.set_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_data_with_validation(
        self, data_service, mock_cache, mock_router, sample_query, sample_response
    ):
        """Test data validation during retrieval."""
        # Arrange
        mock_cache.get_data.return_value = None
        mock_router.execute_query.return_value = sample_response

        # Act
        result = await data_service.get_data(sample_query)

        # Assert
        assert result.data == sample_response.data
        assert result.source == sample_response.source
        # Verify data quality score is set
        assert result.metadata.data_quality_score is not None
        assert 0.0 <= result.metadata.data_quality_score <= 1.0

    @pytest.mark.asyncio
    async def test_get_data_invalid_query(self, data_service):
        """Test handling of invalid query."""
        # Since Pydantic validates at creation time, we need to test
        # the validation that happens in DataService._validate_query
        # Create a valid query first, then modify it to be invalid
        valid_query = DataQuery(asset=AssetType.STOCK)
        
        # Manually set invalid symbols to bypass Pydantic validation
        valid_query.symbols = []

        # Act & Assert
        with pytest.raises(DataValidationException):
            await data_service.get_data(valid_query)

    @pytest.mark.asyncio
    async def test_get_data_execution_timing(
        self, data_service, mock_cache, mock_router, sample_query, sample_response
    ):
        """Test that execution timing is properly recorded."""
        # Arrange
        mock_cache.get_data.return_value = None
        mock_router.execute_query.return_value = sample_response

        # Add delay to router execution
        async def delayed_execute(query):
            await asyncio.sleep(0.1)  # 100ms delay
            return sample_response

        mock_router.execute_query.side_effect = delayed_execute

        # Act
        start_time = time.time()
        result = await data_service.get_data(sample_query)
        end_time = time.time()

        # Assert
        execution_time = (end_time - start_time) * 1000  # Convert to ms
        assert result.metadata.execution_time_ms >= 100  # At least 100ms
        assert result.metadata.execution_time_ms <= execution_time + 50  # Some tolerance

    @pytest.mark.asyncio
    async def test_get_data_response_metadata_generation(
        self, data_service, mock_cache, mock_router, sample_query, sample_response
    ):
        """Test that response metadata is properly generated."""
        # Arrange
        mock_cache.get_data.return_value = None
        mock_router.execute_query.return_value = sample_response

        # Act
        result = await data_service.get_data(sample_query)

        # Assert
        metadata = result.metadata
        assert metadata.record_count == len(result.data)
        assert metadata.cache_hit is False
        assert metadata.query_time is not None
        assert metadata.execution_time_ms > 0
        assert metadata.data_quality_score is not None

    @pytest.mark.asyncio
    async def test_get_data_concurrent_requests(
        self, data_service, mock_cache, mock_router, sample_query, sample_response
    ):
        """Test handling of concurrent requests for same data."""
        # Arrange
        mock_cache.get_data.return_value = None
        mock_router.execute_query.return_value = sample_response

        # Act - Make multiple concurrent requests
        tasks = [data_service.get_data(sample_query) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # Assert
        assert len(results) == 5
        for result in results:
            assert result.data == sample_response.data
            assert result.source == sample_response.source

        # Cache should be called for each request
        assert mock_cache.get_data.call_count == 5
        # Router might be called multiple times due to concurrency
        assert mock_router.execute_query.call_count >= 1

    @pytest.mark.asyncio
    async def test_validate_query_valid(self, data_service, sample_query):
        """Test validation of valid query."""
        # Act & Assert - Should not raise exception
        await data_service._validate_query(sample_query)

    @pytest.mark.asyncio
    async def test_validate_query_empty_symbols(self, data_service):
        """Test validation of query with empty symbols list."""
        # Arrange - Create valid query then modify to bypass Pydantic validation
        query = DataQuery(asset=AssetType.STOCK)
        query.symbols = []  # Set empty list directly

        # Act & Assert
        with pytest.raises(DataValidationException) as exc_info:
            await data_service._validate_query(query)

        assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_query_future_dates(self, data_service):
        """Test validation of query with future dates."""
        # Arrange - Create valid query then modify to bypass Pydantic validation
        query = DataQuery(asset=AssetType.STOCK)
        future_date = datetime.now(timezone.utc).replace(year=2030)
        query.start = future_date  # Set future date directly

        # Act & Assert
        with pytest.raises(DataValidationException) as exc_info:
            await data_service._validate_query(query)

        assert "future" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_calculate_data_quality_score_perfect_data(
        self, data_service, sample_data_point
    ):
        """Test data quality calculation for perfect data."""
        # Arrange
        data_points = [sample_data_point]

        # Act
        score = await data_service._calculate_data_quality_score(data_points)

        # Assert
        assert score == 1.0  # Perfect score for complete data

    @pytest.mark.asyncio
    async def test_calculate_data_quality_score_missing_fields(
        self, data_service, sample_data_point
    ):
        """Test data quality calculation for data with missing fields."""
        # Arrange
        incomplete_point = DataPoint(
            symbol="000001",
            timestamp=datetime.now(timezone.utc),
            close=Decimal("10.25"),
            # Missing open, high, low, volume
        )
        data_points = [incomplete_point]

        # Act
        score = await data_service._calculate_data_quality_score(data_points)

        # Assert
        assert 0.0 < score < 1.0  # Reduced score for missing fields

    @pytest.mark.asyncio
    async def test_calculate_data_quality_score_empty_data(self, data_service):
        """Test data quality calculation for empty data."""
        # Arrange
        data_points = []

        # Act
        score = await data_service._calculate_data_quality_score(data_points)

        # Assert
        assert score == 0.0  # Zero score for no data

    @pytest.mark.asyncio
    async def test_enhance_response_metadata(
        self, data_service, sample_response, sample_query
    ):
        """Test response metadata enhancement."""
        # Arrange
        execution_time_ms = 150.0

        # Act
        enhanced_response = await data_service._enhance_response_metadata(
            sample_response, sample_query, execution_time_ms, cache_hit=False
        )

        # Assert
        metadata = enhanced_response.metadata
        assert metadata.execution_time_ms == execution_time_ms
        assert metadata.cache_hit is False
        assert metadata.record_count == len(enhanced_response.data)
        assert metadata.data_quality_score is not None

    @pytest.mark.asyncio
    async def test_get_data_pipeline_integration(
        self, data_service, mock_cache, mock_router, sample_query, sample_response
    ):
        """Test the complete data retrieval pipeline."""
        # Arrange
        mock_cache.get_data.return_value = None  # Cache miss
        mock_router.execute_query.return_value = sample_response

        # Act
        result = await data_service.get_data(sample_query)

        # Assert - Verify complete pipeline execution
        # 1. Cache check
        mock_cache.get_data.assert_called_once_with(sample_query)
        # 2. Query validation (implicit)
        # 3. Router execution
        mock_router.execute_query.assert_called_once_with(sample_query)
        # 4. Data quality validation (implicit)
        # 5. Response metadata enhancement (implicit)
        # 6. Cache storage
        mock_cache.set_data.assert_called_once_with(sample_query, result)

        # Verify final result
        assert result.data == sample_response.data
        assert result.metadata.cache_hit is False
        assert result.metadata.data_quality_score is not None

    @pytest.mark.asyncio
    async def test_error_handling_and_logging(
        self, data_service, mock_cache, mock_router, sample_query, caplog
    ):
        """Test error handling and logging."""
        # Arrange
        mock_cache.get_data.return_value = None
        mock_router.execute_query.side_effect = Exception("Provider error")

        # Act & Assert
        with pytest.raises(VPrismException):
            await data_service.get_data(sample_query)

        # Verify error was logged
        assert "error" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_data_service_initialization(self):
        """Test DataService initialization with different configurations."""
        # Test with minimal configuration
        service = DataService()
        assert service.cache is not None
        assert service.router is not None
        assert service.provider_registry is not None

        # Test with custom components
        custom_cache = Mock(spec=MultiLevelCache)
        custom_router = Mock(spec=DataRouter)
        custom_registry = Mock(spec=EnhancedProviderRegistry)

        service = DataService(
            cache=custom_cache,
            router=custom_router,
            provider_registry=custom_registry,
        )
        assert service.cache is custom_cache
        assert service.router is custom_router
        assert service.provider_registry is custom_registry

    @pytest.mark.asyncio
    async def test_performance_metrics_collection(
        self, data_service, mock_cache, mock_router, sample_query, sample_response
    ):
        """Test that performance metrics are properly collected."""
        # Arrange
        mock_cache.get_data.return_value = None
        mock_router.execute_query.return_value = sample_response

        # Act
        result = await data_service.get_data(sample_query)

        # Assert
        # Verify timing information is captured
        assert result.metadata.execution_time_ms > 0
        assert result.metadata.query_time is not None

        # Verify record count is accurate
        assert result.metadata.record_count == len(result.data)


class TestDataServiceIntegration:
    """Integration tests for DataService with real components."""

    @pytest.mark.asyncio
    async def test_integration_with_real_cache_and_router(self):
        """Test DataService with real cache and router components."""
        # This would be an integration test with real components
        # For now, we'll skip this as it requires more setup
        pytest.skip("Integration test - requires real components")

    @pytest.mark.asyncio
    async def test_end_to_end_data_flow(self):
        """Test complete end-to-end data flow."""
        # This would test the complete flow from query to response
        # with real providers, cache, and routing
        pytest.skip("End-to-end test - requires real providers")