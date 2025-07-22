"""测试核心数据服务和双重API设计."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

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
from vprism.core.services import DataService, QueryBuilder
from vprism.core.services.data_router import DataRouter


class TestDataService:
    """测试数据服务."""

    @pytest.fixture
    def mock_router(self):
        """创建mock路由器."""

        registry = AsyncMock()
        router = AsyncMock(spec=DataRouter)
        return router

    @pytest.fixture
    def mock_cache(self):
        """创建mock缓存."""
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.health_check = AsyncMock(return_value=True)
        return cache

    @pytest.fixture
    def mock_repository(self):
        """创建mock仓库."""
        repo = AsyncMock()
        repo.save_data_points = AsyncMock()
        repo.get_data_points = AsyncMock(return_value=[])
        repo.health_check = AsyncMock(return_value=True)
        return repo

    @pytest.fixture
    def service(self, mock_router, mock_cache, mock_repository):
        """创建测试服务实例."""
        return DataService(
            router=mock_router,
            cache=mock_cache,
            repository=mock_repository,
        )

    @pytest.fixture
    def sample_data(self):
        """创建示例数据."""
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
    async def test_simple_api_get_single_symbol(
        self, service, mock_router, sample_data
    ):
        """测试简单API：获取单个股票数据."""
        mock_response = DataResponse(
            data=sample_data,
            metadata=ResponseMetadata(
                total_records=len(sample_data), query_time_ms=100.0, data_source="test"
            ),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_router.route_query.return_value = mock_response

        result = await service.get("000001", start="2024-01-01", end="2024-01-31")

        assert len(result.data) == 1
        assert result.data[0].symbol == "000001"
        mock_router.route_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_simple_api_get_multiple_symbols(
        self, service, mock_router, sample_data
    ):
        """测试简单API：获取多个股票数据."""
        # 为每个符号创建数据
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
            metadata=ResponseMetadata(
                total_records=len(data), query_time_ms=100.0, data_source="test"
            ),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_router.route_query.return_value = mock_response

        result = await service.get(["000001", "000002"], start="2024-01-01")

        assert len(result.data) == 2
        symbols = [dp.symbol for dp in result.data]
        assert "000001" in symbols
        assert "000002" in symbols

    @pytest.mark.asyncio
    async def test_simple_api_with_default_dates(self, service, mock_router):
        """测试简单API：使用默认日期."""
        mock_router.route_query.return_value = DataResponse(
            data=[],
            metadata=ResponseMetadata(
                total_records=0, query_time_ms=0.0, data_source="test"
            ),
            source=ProviderInfo(name="test", endpoint="test"),
        )

        await service.get("000001")

        # 验证查询参数
        call_args = mock_router.route_query.call_args[0][0]
        assert call_args.symbols == ["000001"]
        assert call_args.market == MarketType.CN
        assert call_args.asset == AssetType.STOCK
        assert call_args.timeframe == TimeFrame.DAY_1
        assert call_args.end.date() == datetime.now().date()
        assert call_args.start.date() == datetime.now().date() - timedelta(days=30)

    @pytest.mark.asyncio
    async def test_simple_api_different_markets(self, service, mock_router):
        """测试简单API：不同市场."""
        mock_router.route_query.return_value = DataResponse(
            data=[],
            metadata=ResponseMetadata(
                total_records=0, query_time_ms=0.0, data_source="test"
            ),
            source=ProviderInfo(name="test", endpoint="test"),
        )

        await service.get("AAPL", market=MarketType.US)

        call_args = mock_router.route_query.call_args[0][0]
        assert call_args.market == MarketType.US
        assert call_args.symbols == ["AAPL"]

    @pytest.mark.asyncio
    async def test_chain_api_basic_usage(self, service):
        """测试链式API：基本使用."""
        builder = service.query()
        assert isinstance(builder, QueryBuilder)

    @pytest.mark.asyncio
    async def test_chain_api_fluent_interface(self, service, mock_router, sample_data):
        """测试链式API：流畅接口."""
        mock_response = DataResponse(
            data=sample_data,
            metadata=ResponseMetadata(
                total_records=len(sample_data), query_time_ms=100.0, data_source="test"
            ),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        mock_router.route_query.return_value = mock_response

        result = await (
            service.query()
            .asset("stock")
            .market("cn")
            .symbols(["000001"])
            .start("2024-01-01")
            .end("2024-01-31")
            .get()
        )

        assert len(result.data) == 1
        assert result.data[0].symbol == "000001"

    @pytest.mark.asyncio
    async def test_chain_api_with_period(self, service, mock_router):
        """测试链式API：使用周期参数."""
        mock_router.route_query.return_value = DataResponse(
            data=[],
            metadata=ResponseMetadata(
                total_records=0, query_time_ms=0.0, data_source="test"
            ),
            source=ProviderInfo(name="test", endpoint="test"),
        )

        await service.query().symbols(["000001"]).period("1m").get()

        call_args = mock_router.route_query.call_args[0][0]
        assert call_args.symbols == ["000001"]
        assert (call_args.end - call_args.start).days >= 29

    @pytest.mark.asyncio
    async def test_cache_hit(self, service, mock_cache, sample_data):
        """测试缓存命中."""
        mock_cache.get.return_value = sample_data

        result = await service.get("000001", start="2024-01-01")

        assert result.cached is True
        assert len(result.data) == 1
        mock_cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_miss_and_store(
        self, service, mock_cache, mock_repository, sample_data
    ):
        """测试缓存未命中并存储."""
        mock_router = AsyncMock()
        mock_router.route_query.return_value = DataResponse(
            data=sample_data,
            metadata=ResponseMetadata(
                total_records=len(sample_data), query_time_ms=100.0, data_source="test"
            ),
            source=ProviderInfo(name="test", endpoint="test"),
        )
        service.router = mock_router

        result = await service.get("000001", start="2024-01-01")

        assert result.cached is False
        mock_cache.set.assert_called_once()
        mock_repository.save_data_points.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_fallback_on_error(
        self, service, mock_router, mock_repository, sample_data
    ):
        """测试数据库回退机制."""
        # 路由器失败
        mock_router.route_query.side_effect = Exception("Router error")
        # 数据库有数据
        mock_repository.get_data_points.return_value = sample_data

        result = await service.get("000001", start="2024-01-01")

        assert len(result.data) == 1
        assert result.metadata["source"] == "repository"

    @pytest.mark.asyncio
    async def test_get_latest_data(self, service, mock_router):
        """测试获取最新数据."""
        mock_router.route_query.return_value = DataResponse(
            data=[],
            metadata=ResponseMetadata(
                total_records=0, query_time_ms=0.0, data_source="test"
            ),
            source=ProviderInfo(name="test", endpoint="test"),
        )

        await service.get_latest(["000001", "000002"])

        call_args = mock_router.route_query.call_args[0][0]
        assert call_args.symbols == ["000001", "000002"]
        assert call_args.end == datetime.now().date()
        assert call_args.start == datetime.now().date() - timedelta(days=1)

    @pytest.mark.asyncio
    async def test_get_historical_data(self, service, mock_router):
        """测试获取历史数据."""
        mock_router.route_query.return_value = DataResponse(
            data=[],
            metadata=ResponseMetadata(
                total_records=0, query_time_ms=0.0, data_source="test"
            ),
            source=ProviderInfo(name="test", endpoint="test"),
        )

        await service.get_historical(["000001"], "3m")

        call_args = mock_router.route_query.call_args[0][0]
        assert call_args.symbols == ["000001"]
        assert (call_args.end - call_args.start).days >= 89

    @pytest.mark.asyncio
    async def test_batch_query(self, service, mock_router, sample_data):
        """测试批量查询."""
        mock_router.route_query.return_value = DataResponse(
            data=sample_data,
            metadata=ResponseMetadata(
                total_records=len(sample_data), query_time_ms=100.0, data_source="test"
            ),
            source=ProviderInfo(name="test", endpoint="test"),
        )

        queries = [
            DataQuery(symbols=["000001"], market=MarketType.CN),
            DataQuery(symbols=["AAPL"], market=MarketType.US),
        ]

        results = await service.batch_query(queries)

        assert len(results) == 2
        assert "query_0" in results
        assert "query_1" in results
        assert len(results["query_0"].data) == 1

    @pytest.mark.asyncio
    async def test_batch_query_with_errors(self, service, mock_router):
        """测试批量查询处理错误."""
        # 第一个查询成功，第二个失败
        mock_router.route_query.side_effect = [
            DataResponse(data=[]),
            Exception("Query failed"),
        ]

        queries = [
            DataQuery(symbols=["000001"], market=MarketType.CN),
            DataQuery(symbols=["AAPL"], market=MarketType.US),
        ]

        results = await service.batch_query(queries)

        assert len(results) == 2
        assert len(results["query_0"].data) == 0
        assert "error" in results["query_1"].metadata

    @pytest.mark.asyncio
    async def test_health_check(self, service, mock_cache, mock_repository):
        """测试健康检查."""
        mock_router = AsyncMock()
        mock_router.health_check.return_value = True
        service.router = mock_router

        health = await service.health_check()

        assert health["router"] is True
        assert health["cache"] is True
        assert health["repository"] is True

    @pytest.mark.asyncio
    async def test_close_service(self, service):
        """测试关闭服务."""
        # 确保关闭方法可以正常调用
        await service.close()
        # 不应该抛出异常


class TestQueryBuilder:
    """测试查询构建器."""

    def test_create_query_builder(self):
        """测试创建查询构建器."""
        builder = QueryBuilder()
        assert builder.query.symbols == []
        assert builder.query.market == MarketType.CN

    def test_asset_setting(self):
        """测试设置资产类型."""
        builder = QueryBuilder()
        result = builder.asset("stock")
        assert result is builder  # 链式调用
        assert builder.query.asset == AssetType.STOCK

    def test_asset_setting_enum(self):
        """测试设置资产类型（枚举）."""
        builder = QueryBuilder()
        builder.asset(AssetType.INDEX)
        assert builder.query.asset == AssetType.INDEX

    def test_market_setting(self):
        """测试设置市场类型."""
        builder = QueryBuilder()
        builder.market("us")
        assert builder.query.market == MarketType.US

    def test_symbols_setting(self):
        """测试设置股票代码."""
        builder = QueryBuilder()
        builder.symbols("000001")
        assert builder.query.symbols == ["000001"]

    def test_symbols_setting_list(self):
        """测试设置股票代码列表."""
        builder = QueryBuilder()
        builder.symbols(["000001", "000002"])
        assert builder.query.symbols == ["000001", "000002"]

    def test_start_date_setting(self):
        """测试设置开始日期."""
        builder = QueryBuilder()
        builder.start("2024-01-01")
        assert builder.query.start == date(2024, 1, 1)

    def test_end_date_setting(self):
        """测试设置结束日期."""
        builder = QueryBuilder()
        builder.end("2024-01-31")
        assert builder.query.end == date(2024, 1, 31)

    def test_timeframe_setting(self):
        """测试设置时间框架."""
        builder = QueryBuilder()
        builder.timeframe("1h")
        assert builder.query.timeframe == TimeFrame.HOUR_1

    def test_period_setting(self):
        """测试设置周期."""
        builder = QueryBuilder()
        builder.period("1m")

        assert (builder.query.end - builder.query.start).days >= 29

    def test_build_query(self):
        """测试构建查询."""
        builder = QueryBuilder()
        query = (
            builder.asset("stock")
            .market("cn")
            .symbols(["000001"])
            .start("2024-01-01")
            .end("2024-01-31")
            .build()
        )

        assert query.asset == AssetType.STOCK
        assert query.market == MarketType.CN
        assert query.symbols == ["000001"]
        assert query.start == date(2024, 1, 1)
        assert query.end == date(2024, 1, 31)

    def test_string_representation(self):
        """测试字符串表示."""
        builder = QueryBuilder()
        builder.symbols(["000001"])

        repr_str = repr(builder)
        assert "QueryBuilder" in repr_str
        assert "000001" in repr_str


class TestDataServiceIntegration:
    """数据服务集成测试."""

    def test_simple_api_usage_patterns(self):
        """测试简单API使用模式."""
        # 测试各种参数组合
        from vprism.infrastructure.providers.registry import ProviderRegistry
        registry = ProviderRegistry()
        router = DataRouter(registry)
        service = DataService(router=router)

        # 应该能够创建查询而不抛出异常
        assert service is not None

    def test_chain_api_usage_patterns(self):
        """测试链式API使用模式."""
        from vprism.infrastructure.providers.registry import ProviderRegistry
        registry = ProviderRegistry()
        router = DataRouter(registry)
        service = DataService(router=router)

        # 应该能够创建查询构建器而不抛出异常
        builder = service.query()
        assert isinstance(builder, QueryBuilder)

    def test_query_builder_independence(self):
        """测试查询构建器独立性."""
        from vprism.infrastructure.providers.registry import ProviderRegistry
        registry = ProviderRegistry()
        router = DataRouter(registry)
        service = DataService(router=router)

        builder1 = service.query().symbols(["000001"])
        builder2 = service.query().symbols(["000002"])

        assert builder1.query.symbols == ["000001"]
        assert builder2.query.symbols == ["000002"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
