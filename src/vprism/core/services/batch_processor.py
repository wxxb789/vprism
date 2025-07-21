"""批量数据处理管道实现."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vprism.core.models import (
    DataQuery,
    DataResponse,
    AssetType,
    ProviderInfo,
    ResponseMetadata,
)
from vprism.core.services.data_router import DataRouter
from vprism.core.services.data_service import DataService
from vprism.infrastructure.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


@dataclass
class BatchRequest:
    """批量请求数据结构."""

    queries: list[DataQuery]
    concurrent_limit: int = 10
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0

    def __post_init__(self):
        """初始化后验证."""
        if self.concurrent_limit <= 0:
            self.concurrent_limit = 10
        if self.timeout <= 0:
            self.timeout = 30
        if self.retry_count < 0:
            self.retry_count = 0


@dataclass
class BatchResult:
    """批量处理结果."""

    results: dict[str, DataResponse]
    success_count: int
    failure_count: int
    total_time_seconds: float
    errors: dict[str, str]
    processed_queries: list[str]


class BatchProcessor:
    """批量数据处理管道."""

    def __init__(
        self,
        data_service: DataService,
        router: DataRouter | None = None,
        registry: ProviderRegistry | None = None,
    ):
        """初始化批量处理器.

        Args:
            data_service: 数据服务实例
            router: 数据路由器实例
            registry: 提供商注册表实例
        """
        self.data_service = data_service
        self.router = router
        self.registry = registry

    async def process_batch(self, batch_request: BatchRequest) -> BatchResult:
        """处理批量数据请求.

        Args:
            batch_request: 批量请求配置

        Returns:
            BatchResult: 批量处理结果

        Examples:
            >>> processor = BatchProcessor(data_service)
            >>> queries = [DataQuery(...), DataQuery(...)]
            >>> request = BatchRequest(queries=queries)
            >>> result = await processor.process_batch(request)
        """
        start_time = datetime.now()

        logger.info(
            f"Starting batch processing with {len(batch_request.queries)} queries"
        )

        # 按提供商分组查询
        provider_groups = self._group_queries_by_provider(batch_request.queries)

        # 并发处理每个提供商的查询
        tasks = []
        for provider_name, queries in provider_groups.items():
            task = self._process_provider_group(provider_name, queries, batch_request)
            tasks.append(task)

        # 执行所有任务
        group_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 合并结果
        final_results = {}
        errors = {}
        success_count = 0
        failure_count = 0

        for i, (provider_name, queries) in enumerate(provider_groups.items()):
            result = group_results[i]
            if isinstance(result, Exception):
                # 处理异常
                for j, query in enumerate(queries):
                    query_id = f"{provider_name}_{j}"
                    errors[query_id] = str(result)
                    final_results[query_id] = DataResponse(
                        data=[],
                        metadata={"error": str(result), "provider": provider_name},
                        source=ProviderInfo(name=provider_name, endpoint=provider_name),
                    )
                failure_count += len(queries)
            else:
                # 处理成功结果
                final_results.update(result)
                success_count += len(
                    [
                        r
                        for r in result.values()
                        if not getattr(r.metadata, "error", None)
                    ]
                )
                failure_count += len(
                    [r for r in result.values() if getattr(r.metadata, "error", None)]
                )

        total_time = (datetime.now() - start_time).total_seconds()

        result = BatchResult(
            results=final_results,
            success_count=success_count,
            failure_count=failure_count,
            total_time_seconds=total_time,
            errors=errors,
            processed_queries=list(final_results.keys()),
        )

        logger.info(
            f"Batch processing completed: {success_count} successful, "
            f"{failure_count} failed in {total_time:.2f} seconds"
        )

        return result

    def _group_queries_by_provider(
        self, queries: list[DataQuery]
    ) -> dict[str, list[DataQuery]]:
        """按提供商分组查询.

        Args:
            queries: 查询列表

        Returns:
            Dict[str, List[DataQuery]]: 按提供商分组的查询
        """
        groups = {}

        for query in queries:
            # 找到能处理此查询的提供商
            capable_providers = self._find_capable_providers(query)

            if not capable_providers:
                logger.warning(f"No capable provider found for query: {query}")
                continue

            # 选择最佳提供商（健康、高分、低延迟）
            best_provider = self._select_best_provider(capable_providers)

            if best_provider:
                provider_name = best_provider.name
                if provider_name not in groups:
                    groups[provider_name] = []
                groups[provider_name].append(query)

        return groups

    def _find_capable_providers(self, query: DataQuery) -> list[Any]:
        """找到能处理查询的提供商.

        Args:
            query: 数据查询

        Returns:
            List[Any]: 能处理查询的提供商列表
        """
        if not self.registry:
            return []

        return self.registry.find_capable_providers(query)

    def _select_best_provider(self, providers: list[Any]) -> Any | None:
        """选择最佳提供商.

        Args:
            providers: 提供商列表

        Returns:
            Optional[Any]: 最佳提供商或None
        """
        if not providers:
            return None

        # 简单的选择策略：选择健康的第一个提供商
        for provider in providers:
            if hasattr(self.registry, "is_healthy") and self.registry.is_healthy(
                provider.name
            ):
                return provider

        # 如果没有健康的，返回第一个
        return providers[0]

    async def _process_provider_group(
        self, provider_name: str, queries: list[DataQuery], batch_request: BatchRequest
    ) -> dict[str, DataResponse]:
        """处理单个提供商的查询组.

        Args:
            provider_name: 提供商名称
            queries: 查询列表
            batch_request: 批量请求配置

        Returns:
            Dict[str, DataResponse]: 查询结果
        """
        semaphore = asyncio.Semaphore(batch_request.concurrent_limit)

        async def process_single_query(
            query: DataQuery, index: int
        ) -> tuple[str, DataResponse]:
            """处理单个查询."""
            async with semaphore:
                query_id = f"{provider_name}_{index}"

                for attempt in range(batch_request.retry_count + 1):
                    try:
                        response = await asyncio.wait_for(
                            self.data_service.query_data(query),
                            timeout=batch_request.timeout,
                        )
                        return query_id, response

                    except TimeoutError:
                        if attempt == batch_request.retry_count:
                            error_msg = f"Query timeout after {batch_request.retry_count} retries"
                            logger.error(f"{query_id}: {error_msg}")
                            return query_id, DataResponse(
                                data=[],
                                metadata=ResponseMetadata(
                                    total_records=0,
                                    query_time_ms=0.0,
                                    data_source=provider_name,
                                ),
                                source=ProviderInfo(
                                    name=provider_name, endpoint=provider_name
                                ),
                            )
                        else:
                            await asyncio.sleep(
                                batch_request.retry_delay * (2**attempt)
                            )

                    except Exception as e:
                        if attempt == batch_request.retry_count:
                            logger.error(f"{query_id}: Query failed - {e}")
                            return query_id, DataResponse(
                                data=[],
                                metadata=ResponseMetadata(
                                    total_records=0,
                                    query_time_ms=0.0,
                                    data_source=provider_name,
                                ),
                                source=ProviderInfo(
                                    name=provider_name, endpoint=provider_name
                                ),
                            )
                        else:
                            await asyncio.sleep(
                                batch_request.retry_delay * (2**attempt)
                            )

        # 并发处理所有查询
        tasks = [process_single_query(query, i) for i, query in enumerate(queries)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        final_results = {}
        for result in results:
            if isinstance(result, Exception):
                # 处理异常
                logger.error(f"Unexpected error in batch processing: {result}")
            else:
                query_id, response = result
                final_results[query_id] = response

        return final_results

    async def process_optimized_batch(
        self,
        symbols: list[str],
        market: Any,
        timeframe: Any,
        start: datetime,
        end: datetime,
        concurrent_limit: int = 10,
    ) -> BatchResult:
        """处理优化后的批量请求.

        Args:
            symbols: 股票代码列表
            market: 市场类型
            timeframe: 时间框架
            start: 开始时间
            end: 结束时间
            concurrent_limit: 并发限制

        Returns:
            BatchResult: 批量处理结果
        """
        # 创建批量查询
        queries = [
            DataQuery(
                asset=AssetType.STOCK,
                symbols=[symbol],
                market=market,
                timeframe=timeframe,
                start=start,
                end=end,
            )
            for symbol in symbols
        ]

        batch_request = BatchRequest(queries=queries, concurrent_limit=concurrent_limit)

        return await self.process_batch(batch_request)

    async def get_market_data_batch(
        self,
        symbols: list[str],
        market: Any,
        period: str = "1m",
        concurrent_limit: int = 10,
    ) -> BatchResult:
        """获取市场数据的批量接口.

        Args:
            symbols: 股票代码列表
            market: 市场类型
            period: 时间周期
            concurrent_limit: 并发限制

        Returns:
            BatchResult: 批量处理结果
        """
        from datetime import timedelta

        end = datetime.now()
        period_mapping = {
            "1d": timedelta(days=1),
            "1w": timedelta(weeks=1),
            "1m": timedelta(days=30),
            "3m": timedelta(days=90),
            "1y": timedelta(days=365),
            "max": timedelta(days=3650),
        }

        start = end - period_mapping.get(period, timedelta(days=30))

        return await self.process_optimized_batch(
            symbols=symbols,
            market=market,
            timeframe="1d",
            start=start,
            end=end,
            concurrent_limit=concurrent_limit,
        )

    def get_performance_metrics(self, result: BatchResult) -> dict[str, Any]:
        """获取性能指标.

        Args:
            result: 批量处理结果

        Returns:
            Dict[str, Any]: 性能指标
        """
        total_queries = len(result.results)
        success_rate = result.success_count / total_queries if total_queries > 0 else 0

        return {
            "total_queries": total_queries,
            "success_count": result.success_count,
            "failure_count": result.failure_count,
            "success_rate": success_rate,
            "total_time_seconds": result.total_time_seconds,
            "queries_per_second": total_queries / result.total_time_seconds
            if result.total_time_seconds > 0
            else 0,
            "errors": result.errors,
        }
