"""测试批量数据处理管道."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from core.models.base import DataPoint
from core.models.market import AssetType, MarketType, TimeFrame
from core.models.query import DataQuery
from core.models.response import DataResponse, ProviderInfo, ResponseMetadata
from core.services.batch import BatchProcessor, BatchRequest, BatchResult


class TestBatchProcessor:
    """测试批量处理器."""

    @pytest.fixture
    def mock_data_service(self):
        """创建mock数据服务."""
        return AsyncMock()

    @pytest.fixture
    def mock_registry(self):
        """创建mock注册表."""
        registry = AsyncMock()
        # 设置同步方法返回实际值而不是协程
        registry.find_capable_providers = lambda query: []
        registry.is_healthy = lambda name: True
        return registry

    @pytest.fixture
    def processor(self, mock_data_service, mock_registry):
        """创建测试处理器实例."""
        return BatchProcessor(data_service=mock_data_service, registry=mock_registry)

    @pytest.fixture
    def sample_queries(self):
        """创建示例查询."""
        return [
            DataQuery(
                asset=AssetType.STOCK,
                symbols=["000001"],
                market=MarketType.CN,
                timeframe=TimeFrame.DAY_1,
                start=datetime.now() - timedelta(days=30),
                end=datetime.now(),
            ),
            DataQuery(
                asset=AssetType.STOCK,
                symbols=["AAPL"],
                market=MarketType.US,
                timeframe=TimeFrame.DAY_1,
                start=datetime.now() - timedelta(days=30),
                end=datetime.now(),
            ),
        ]

    @pytest.fixture
    def sample_data(self):
        """创建示例数据."""
        return [
            DataPoint(
                symbol="000001",
                timestamp=datetime.now(),
                open=Decimal("10.0"),
                high=Decimal("11.0"),
                low=Decimal("9.0"),
                close=Decimal("10.5"),
                volume=Decimal("1000000"),
            )
        ]

    @pytest.mark.asyncio
    async def test_process_batch_success(self, processor, mock_data_service, sample_queries, sample_data):
        """测试批量处理成功."""
        # 设置mock响应
        mock_response = DataResponse(
            data=sample_data,
            metadata=ResponseMetadata(total_records=len(sample_data), query_time_ms=100.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )

        mock_data_service.query_data.return_value = mock_response

        # 设置mock注册表
        mock_provider = AsyncMock()
        mock_provider.name = "test_provider"
        processor.registry.find_capable_providers = lambda query: [mock_provider]
        processor.registry.is_healthy = lambda name: True

        # 创建批量请求
        batch_request = BatchRequest(queries=sample_queries, concurrent_limit=2, timeout=10)

        result = await processor.process_batch(batch_request)

        assert isinstance(result, BatchResult)
        assert result.success_count == 2
        assert result.failure_count == 0
        assert len(result.results) == 2
        assert result.total_time_seconds > 0

    @pytest.mark.asyncio
    async def test_process_batch_with_failures(self, processor, mock_data_service, sample_queries):
        """测试批量处理包含失败."""
        # 设置mock响应：第一个成功，第二个失败
        mock_response = DataResponse(
            data=[],
            metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )

        # 设置mock响应：第一个成功，第二个失败
        def mock_query_data(query):
            if query.symbols == ["000001"]:
                return mock_response
            else:
                raise Exception("Query failed")

        mock_data_service.query_data.side_effect = mock_query_data

        # 设置mock注册表
        mock_provider = AsyncMock()
        mock_provider.name = "test_provider"
        processor.registry.find_capable_providers = lambda query: [mock_provider]
        processor.registry.is_healthy = lambda name: True

        batch_request = BatchRequest(queries=sample_queries)
        result = await processor.process_batch(batch_request)

        # 由于异常被捕获并转换为空响应，检查是否有结果
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_group_queries_by_provider(self, processor, sample_queries):
        """测试按提供商分组查询."""
        # 设置mock注册表
        mock_provider = AsyncMock()
        mock_provider.name = "test_provider"
        processor.registry.find_capable_providers = lambda query: [mock_provider]
        processor.registry.is_healthy = lambda name: True

        groups = processor._group_queries_by_provider(sample_queries)

        assert len(groups) > 0
        assert "test_provider" in groups

    @pytest.mark.asyncio
    async def test_select_best_provider(self, processor):
        """测试选择最佳提供商."""
        mock_provider1 = AsyncMock()
        mock_provider1.name = "provider1"
        mock_provider2 = AsyncMock()
        mock_provider2.name = "provider2"

        best = processor._select_best_provider([mock_provider1, mock_provider2])

        assert best is not None
        assert best.name in ["provider1", "provider2"]

    @pytest.mark.asyncio
    async def test_process_optimized_batch(self, processor, mock_data_service):
        """测试优化批量处理."""
        mock_response = DataResponse(
            data=[],
            metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )

        mock_data_service.query_data.return_value = mock_response

        # 设置mock注册表
        mock_provider = AsyncMock()
        mock_provider.name = "test_provider"
        processor.registry.find_capable_providers = lambda query: [mock_provider]
        processor.registry.is_healthy = lambda name: True

        result = await processor.process_optimized_batch(
            symbols=["000001", "000002"],
            market=MarketType.CN,
            timeframe=TimeFrame.DAY_1,
            start=datetime.now() - timedelta(days=30),
            end=datetime.now(),
            concurrent_limit=2,
        )

        assert isinstance(result, BatchResult)
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_get_market_data_batch(self, processor, mock_data_service):
        """测试获取市场数据批量接口."""
        mock_response = DataResponse(
            data=[],
            metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )

        mock_data_service.query_data.return_value = mock_response

        # 设置mock注册表
        mock_provider = AsyncMock()
        mock_provider.name = "test_provider"
        processor.registry.find_capable_providers = lambda query: [mock_provider]
        processor.registry.is_healthy = lambda name: True

        result = await processor.get_market_data_batch(
            symbols=["000001", "000002"],
            market=MarketType.CN,
            period="1m",
            concurrent_limit=2,
        )

        assert isinstance(result, BatchResult)
        assert len(result.results) == 2

    def test_get_performance_metrics(self, processor):
        """测试获取性能指标."""
        result = BatchResult(
            results={
                "q1": DataResponse(
                    data=[],
                    metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="test"),
                    source=ProviderInfo(name="test", endpoint="test"),
                )
            },
            success_count=1,
            failure_count=0,
            total_time_seconds=2.5,
            errors={},
            processed_queries=["q1"],
        )

        metrics = processor.get_performance_metrics(result)

        assert metrics["total_queries"] == 1
        assert metrics["success_count"] == 1
        assert metrics["failure_count"] == 0
        assert metrics["success_rate"] == 1.0
        assert metrics["total_time_seconds"] == 2.5
        assert metrics["queries_per_second"] == 0.4

    @pytest.mark.asyncio
    async def test_batch_request_validation(self):
        """测试批量请求验证."""
        # 测试默认值
        batch = BatchRequest(queries=[])
        assert batch.concurrent_limit == 10
        assert batch.timeout == 30
        assert batch.retry_count == 3

        # 测试边界值
        batch = BatchRequest(queries=[], concurrent_limit=0, timeout=-1, retry_count=-1)
        assert batch.concurrent_limit == 10
        assert batch.timeout == 30
        assert batch.retry_count == 0

    @pytest.mark.asyncio
    async def test_concurrent_processing_limits(self, processor, mock_data_service):
        """测试并发处理限制."""
        # 创建大量查询
        queries = [
            DataQuery(
                asset=AssetType.STOCK,
                symbols=[f"SYMBOL_{i}"],
                market=MarketType.CN,
                timeframe=TimeFrame.DAY_1,
                start=datetime.now() - timedelta(days=1),
                end=datetime.now(),
            )
            for i in range(20)
        ]

        mock_response = DataResponse(
            data=[],
            metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="test"),
            source=ProviderInfo(name="test", endpoint="test"),
        )

        mock_data_service.query_data.return_value = mock_response

        # 设置mock注册表
        mock_provider = AsyncMock()
        mock_provider.name = "test_provider"
        processor.registry.find_capable_providers = lambda query: [mock_provider]
        processor.registry.is_healthy = lambda name: True

        batch_request = BatchRequest(queries=queries, concurrent_limit=5)

        result = await processor.process_batch(batch_request)

        assert len(result.results) == 20
        assert result.total_time_seconds > 0


class TestBatchIntegration:
    """批量处理集成测试."""

    def test_batch_processor_creation(self):
        """测试批量处理器创建."""
        processor = BatchProcessor(data_service=None)
        assert processor is not None

    def test_batch_request_creation(self):
        """测试批量请求创建."""
        batch = BatchRequest(queries=[])
        assert batch.concurrent_limit == 10
        assert batch.timeout == 30
        assert batch.retry_count == 3

    def test_batch_result_creation(self):
        """测试批量结果创建."""
        result = BatchResult(
            results={},
            success_count=0,
            failure_count=0,
            total_time_seconds=0.0,
            errors={},
            processed_queries=[],
        )
        assert result.success_count == 0
        assert result.failure_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
