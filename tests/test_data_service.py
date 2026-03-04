"""Test core data service and dual API design."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from vprism.core.data.routing import DataRouter
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
from vprism.core.services.data import DataService


class TestDataService:
    """Test data service."""

    @pytest.fixture
    def mock_router(self):
        """Create mock router."""
        router = AsyncMock(spec=DataRouter)
        return router

    @pytest.fixture
    def mock_cache(self):
        """Create mock cache."""
        cache = AsyncMock()
        cache.get_data = AsyncMock(return_value=None)
        cache.set_data = AsyncMock()
        cache.health_check = AsyncMock(return_value=True)
        return cache

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        repo = AsyncMock()
        repo.save_batch = AsyncMock()
        repo.find_by_query = AsyncMock(return_value=[])
        repo.health_check = AsyncMock(return_value=True)
        return repo

    @pytest.fixture
    def service(self, mock_router, mock_cache, mock_repository):
        """Create test service instance."""
        return DataService(
            router=mock_router,
            cache=mock_cache,
            repository=mock_repository,
        )

    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        return [
            DataPoint(
                symbol="000001",
                market=MarketType.CN,
                timestamp=datetime.now(),
                open_price=Decimal("10.0"),
                high_price=Decimal("11.0"),
                low_price=Decimal("9.0"),
                close_price=Decimal("10.5"),
                volume=Decimal("1000000"),
                provider="test",
            )
        ]

    @pytest.mark.asyncio
    async def test_simple_api_get_single_symbol(self, service, mock_router, sample_data):
        """Test simple API: get single stock data."""
        mock_response = DataResponse(
            data=sample_data,
            metadata=ResponseMetadata(total_records=len(sample_data), query_time_ms=100.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = mock_response
        mock_router.route_query.return_value = mock_provider

        result = await service.get("000001", start="2024-01-01", end="2024-01-31")

        assert len(result.data) == 1
        assert result.data[0].symbol == "000001"
        mock_router.route_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_simple_api_get_multiple_symbols(self, service, mock_router, sample_data):
        """Test simple API: get multiple stock data."""
        data = [
            DataPoint(
                symbol="000001",
                market=MarketType.CN,
                timestamp=datetime.now(),
                open_price=Decimal("10.0"),
                high_price=Decimal("11.0"),
                low_price=Decimal("9.0"),
                close_price=Decimal("10.5"),
                volume=Decimal("1000000"),
                provider="test",
            ),
            DataPoint(
                symbol="000002",
                market=MarketType.CN,
                timestamp=datetime.now(),
                open_price=Decimal("20.0"),
                high_price=Decimal("21.0"),
                low_price=Decimal("19.0"),
                close_price=Decimal("20.5"),
                volume=Decimal("2000000"),
                provider="test",
            ),
        ]
        mock_response = DataResponse(
            data=data,
            metadata=ResponseMetadata(total_records=len(data), query_time_ms=100.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = mock_response
        mock_router.route_query.return_value = mock_provider

        result = await service.get(["000001", "000002"], start="2024-01-01")

        assert len(result.data) == 2
        symbols = [dp.symbol for dp in result.data]
        assert "000001" in symbols
        assert "000002" in symbols

    @pytest.mark.asyncio
    async def test_simple_api_with_default_dates(self, service, mock_router):
        """Test simple API: default dates."""
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = DataResponse(
            data=[],
            metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_router.route_query.return_value = mock_provider

        await service.get("000001")

        call_args = mock_router.route_query.call_args[0][0]
        assert call_args.symbols == ["000001"]
        assert call_args.market == MarketType.CN
        assert call_args.asset == AssetType.STOCK
        assert call_args.timeframe == TimeFrame.DAY_1
        assert call_args.end.date() == datetime.now().date()
        assert call_args.start.date() == datetime.now().date() - timedelta(days=30)

    @pytest.mark.asyncio
    async def test_simple_api_different_markets(self, service, mock_router):
        """Test simple API: different markets."""
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = DataResponse(
            data=[],
            metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_router.route_query.return_value = mock_provider

        await service.get("AAPL", market=MarketType.US)

        call_args = mock_router.route_query.call_args[0][0]
        assert call_args.market == MarketType.US
        assert call_args.symbols == ["AAPL"]

    def test_chain_api_basic_usage(self, service):
        """Test chain API: basic usage."""
        builder = service.query()
        assert "QueryBuilder" in str(type(builder))

    @pytest.mark.asyncio
    async def test_chain_api_fluent_interface(self, service, mock_router, sample_data):
        """Test chain API: fluent interface."""
        mock_response = DataResponse(
            data=sample_data,
            metadata=ResponseMetadata(total_records=len(sample_data), query_time_ms=100.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = mock_response
        mock_router.route_query.return_value = mock_provider

        result = await service.query().asset("stock").market("cn").symbols(["000001"]).start("2024-01-01").end("2024-01-31").get()

        assert len(result.data) == 1
        assert result.data[0].symbol == "000001"

    @pytest.mark.asyncio
    async def test_chain_api_with_period(self, service, mock_router):
        """Test chain API: period parameter."""
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = DataResponse(
            data=[],
            metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_router.route_query.return_value = mock_provider

        await service.query().symbols(["000001"]).period("1m").get()

        call_args = mock_router.route_query.call_args[0][0]
        assert call_args.symbols == ["000001"]
        assert (call_args.end - call_args.start).days >= 29

    @pytest.mark.asyncio
    async def test_cache_hit(self, service, mock_cache, sample_data):
        """Test cache hit."""
        mock_cache.get_data.return_value = sample_data

        result = await service.get("000001", start="2024-01-01")

        assert result.cached is True
        assert len(result.data) == 1
        mock_cache.get_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_miss_and_store(self, service, mock_cache, mock_repository, sample_data):
        """Test cache miss and store."""
        mock_router = AsyncMock()
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = DataResponse(
            data=sample_data,
            metadata=ResponseMetadata(total_records=len(sample_data), query_time_ms=100.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_router.route_query.return_value = mock_provider
        service.router = mock_router

        result = await service.get("000001", start="2024-01-01")

        assert result.cached is False
        mock_cache.set_data.assert_called_once()
        mock_repository.save_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_fallback_on_error(self, service, mock_router, mock_repository, sample_data):
        """Test database fallback on error."""
        mock_router.route_query.side_effect = Exception("Router error")
        mock_repository.find_by_query.return_value = sample_data

        result = await service.get("000001", start="2024-01-01")

        assert len(result.data) == 1
        assert result.metadata.data_source == "repository"

    @pytest.mark.asyncio
    async def test_get_latest_data(self, service, mock_router):
        """Test getting latest data."""
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = DataResponse(
            data=[],
            metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_router.route_query.return_value = mock_provider

        await service.get_latest(["000001", "000002"])

        call_args = mock_router.route_query.call_args[0][0]
        assert call_args.symbols == ["000001", "000002"]
        assert call_args.end_date == datetime.now().date()
        assert call_args.start_date == datetime.now().date() - timedelta(days=1)

    @pytest.mark.asyncio
    async def test_get_historical_data(self, service, mock_router):
        """Test getting historical data."""
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = DataResponse(
            data=[],
            metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_router.route_query.return_value = mock_provider

        await service.get_historical(["000001"], "3m")

        call_args = mock_router.route_query.call_args[0][0]
        assert call_args.symbols == ["000001"]
        assert (call_args.end - call_args.start).days >= 89

    @pytest.mark.asyncio
    async def test_batch_query(self, service, mock_router, sample_data):
        """Test batch query."""
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = DataResponse(
            data=sample_data,
            metadata=ResponseMetadata(total_records=len(sample_data), query_time_ms=100.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_router.route_query.return_value = mock_provider

        queries = [
            DataQuery(symbols=["000001"], market=MarketType.CN, asset=AssetType.STOCK),
            DataQuery(symbols=["AAPL"], market=MarketType.US, asset=AssetType.STOCK),
        ]

        results = await service.batch_query(queries)

        assert len(results) == 2
        assert "query_0" in results
        assert "query_1" in results
        assert len(results["query_0"].data) == 1

    @pytest.mark.asyncio
    async def test_batch_query_with_errors(self, service, mock_router):
        """Test batch query error handling."""
        mock_router.route_query.side_effect = [
            DataResponse(
                data=[],
                metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="test_provider"),
                source=ProviderInfo(name="test_provider", endpoint="test"),
            ),
            Exception("Query failed"),
        ]

        queries = [
            DataQuery(symbols=["000001"], market=MarketType.CN, asset=AssetType.STOCK),
            DataQuery(symbols=["AAPL"], market=MarketType.US, asset=AssetType.STOCK),
        ]

        results = await service.batch_query(queries)

        assert len(results) == 2
        assert len(results["query_0"].data) == 0
        assert results["query_1"].source.name == "error"

    @pytest.mark.asyncio
    async def test_health_check(self, service, mock_cache, mock_repository):
        """Test health check."""
        mock_router = AsyncMock()
        mock_router.health_check.return_value = True
        service.router = mock_router

        health = await service.health_check()

        assert health["router"] is True or isinstance(health["router"], dict)
        assert health["cache"] is True or isinstance(health["cache"], dict)
        assert health["repository"] is True


class TestQueryBuilder:
    """Test query builder."""

    @pytest.fixture
    def service(self):
        """Create test service instance."""
        router = AsyncMock()
        cache = AsyncMock()
        repository = AsyncMock()

        return DataService(router=router, cache=cache, repository=repository)

    @pytest.mark.parametrize(
        "method,arg,attr,expected",
        [
            ("asset", "stock", "asset", AssetType.STOCK),
            ("asset", AssetType.INDEX, "asset", AssetType.INDEX),
            ("market", "us", "market", MarketType.US),
            ("symbols", "000001", "symbols", ["000001"]),
            ("symbols", ["000001", "000002"], "symbols", ["000001", "000002"]),
            ("start", "2024-01-01", "start_date", date(2024, 1, 1)),
            ("end", "2024-01-31", "end_date", date(2024, 1, 31)),
            ("timeframe", "1h", "timeframe", TimeFrame.HOUR_1),
        ],
        ids=["asset_str", "asset_enum", "market", "symbols_str", "symbols_list", "start_date", "end_date", "timeframe"],
    )
    def test_query_builder_setter(self, service, method, arg, attr, expected):
        """Test query builder setters return self and store value correctly."""
        builder = service.query()
        result = getattr(builder, method)(arg)
        assert result is builder  # fluent interface
        assert getattr(builder.query, attr) == expected

    def test_period_setting(self, service):
        """Test period setting with date arithmetic."""
        builder = service.query()
        builder.period("1m")

        assert (builder.query.end_date - builder.query.start_date).days >= 29
