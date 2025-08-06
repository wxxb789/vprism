"""核心数据服务，整合路由器、缓存和提供商的完整数据访问层."""

import asyncio
from datetime import date, datetime, timedelta
from typing import Any, cast

from loguru import logger

from vprism.core.data.cache.multilevel import MultiLevelCache
from vprism.core.data.providers.registry import ProviderRegistry
from vprism.core.data.repositories.data import DataRepository
from vprism.core.data.storage.database import DatabaseManager
from vprism.core.models.base import DataPoint
from vprism.core.models.market import AssetType, MarketType, TimeFrame
from vprism.core.models.query import DataQuery
from vprism.core.models.response import DataResponse, ProviderInfo, ResponseMetadata
from vprism.core.monitoring import PerformanceLogger, bind
from vprism.core.services.data_router import DataRouter


class DataService:
    """核心数据服务，提供统一的数据访问接口."""

    def __init__(
        self,
        router: DataRouter | None = None,
        cache: MultiLevelCache | None = None,
        repository: DataRepository | None = None,
    ):
        """初始化数据服务.

        Args:
            router: 数据路由器实例
            cache: 多层缓存实例
            repository: 数据存储仓库实例
        """
        self.router = router or DataRouter(ProviderRegistry())
        self.cache = cache or MultiLevelCache()
        self.repository = repository or DataRepository(DatabaseManager())

        logger.info(
            "DataService initialized",
            extra={
                "component": "DataService",
                "action": "initialization",
                "router_type": type(router).__name__ if router else "default",
                "cache_type": type(cache).__name__ if cache else "default",
                "repository_type": type(repository).__name__ if repository else "default",
            },
        )

    @PerformanceLogger("data_service_get")
    async def get(
        self,
        symbols: str | list[str],
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
        market: MarketType = MarketType.CN,
        asset_type: AssetType = AssetType.STOCK,
        timeframe: TimeFrame = TimeFrame.DAY_1,
    ) -> DataResponse:
        """简单API：获取数据的主要入口点.

        Args:
            symbols: 股票代码或代码列表
            start: 开始日期
            end: 结束日期
            market: 市场类型
            asset_type: 资产类型
            timeframe: 时间框架

        Returns:
            DataResponse: 包含数据点的响应对象

        Examples:
            >>> service = DataService()
            >>> response = await service.get("000001", start="2024-01-01")
            >>> response = await service.get(["AAPL", "GOOGL"], market=MarketType.US)
        """
        # 标准化输入
        if isinstance(symbols, str):
            symbols = [symbols]

        # 标准化日期格式
        if isinstance(end, str):
            end_date = datetime.strptime(end, "%Y-%m-%d").date()
        elif isinstance(end, datetime):
            end_date = end.date()
        elif end is None:
            end_date = datetime.now().date()
        else:
            end_date = end

        if isinstance(start, str):
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
        elif isinstance(start, datetime):
            start_date = start.date()
        elif start is None:
            start_date = end_date - timedelta(days=30)
        else:
            start_date = start

        # 创建查询对象
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        query = DataQuery(
            asset=asset_type,
            market=market,
            symbols=symbols,
            timeframe=timeframe,
            start=start_dt,
            end=end_dt,
        )

        return cast("DataResponse", await self.query_data(query))

    def query(self) -> "QueryBuilder":
        """链式API：创建查询构建器.

        Returns:
            QueryBuilder: 查询构建器实例

        Examples:
            >>> service = DataService()
            >>> response = await service.query() \
            ...     .asset("stock") \
            ...     .market("cn") \
            ...     .symbols(["000001", "000002"]) \
            ...     .start("2024-01-01") \
            ...     .end("2024-01-31") \
            ...     .get()
        """
        return QueryBuilder(self)

    @PerformanceLogger("query_data")
    async def query_data(self, query: DataQuery) -> DataResponse:
        """使用查询对象获取数据.

        Args:
            query: 数据查询对象

        Returns:
            DataResponse: 包含数据点的响应对象
        """
        logger = bind(
            request_id=str(id(query)),
            component="DataService",
            action="query_data",
            symbols=query.symbols,
            market=query.market.value if query.market else None,
            asset_type=query.asset.value,
            timeframe=query.timeframe.value if query.timeframe else None,
        )

        try:
            logger.info("Starting data query")

            # 检查缓存
            cache_key = self._generate_cache_key(query)
            logger.debug("Checking cache", extra={"cache_key": cache_key})

            cached_data = await self.cache.get_data(query)

            if cached_data is not None:
                logger.info(
                    "Cache hit",
                    extra={"cache_key": cache_key, "cached_records": len(cached_data)},
                )
                # Ensure cached data is converted to DataPoint instances
                data_points = []
                for item in cached_data:
                    if isinstance(item, dict):
                        data_points.append(DataPoint(**item))
                    else:
                        data_points.append(item)
                return DataResponse(
                    data=data_points,
                    metadata=ResponseMetadata(
                        total_records=len(data_points),
                        query_time_ms=0.0,
                        data_source="cache",
                        cache_hit=True,
                    ),
                    source=ProviderInfo(name="cache", endpoint="cache"),
                    cached=True,
                )

            logger.info("Cache miss, querying from provider")

            try:
                # 从路由器获取数据
                provider = await self.router.route_query(query)
                response = await provider.get_data(query)

                # 缓存结果
                if response.data:
                    await self.cache.set_data(query, response.data)
                    logger.info(
                        "Data cached",
                        extra={
                            "cache_key": cache_key,
                            "cached_records": len(response.data),
                        },
                    )

                    # 存储到数据库
                    if response.source:
                        data_records = [self.repository.from_data_point(dp, response.source.name) for dp in response.data]
                        await self.repository.save_batch(data_records)
                        logger.info(
                            "Data stored to repository",
                            extra={"stored_records": len(response.data)},
                        )

                logger.info(
                    "Query completed successfully",
                    extra={
                        "retrieved_records": len(response.data),
                        "data_source": response.source.name if response.source else "unknown",
                    },
                )
                return response
            except Exception as router_error:
                logger.error(
                    "Router failed, attempting database fallback",
                    extra={
                        "error_type": type(router_error).__name__,
                        "error_message": str(router_error),
                    },
                )

                # 尝试从数据库获取历史数据
                stored_records = await self.repository.find_by_query(query)
                if stored_records:
                    logger.info(
                        "Retrieved fallback data from storage",
                        extra={"stored_records": len(stored_records)},
                    )
                    data_points = [record.to_data_point() for record in stored_records]
                    return DataResponse(
                        data=data_points,
                        metadata=ResponseMetadata(
                            total_records=len(data_points),
                            query_time_ms=0.0,
                            data_source="repository",
                            cache_hit=False,
                        ),
                        source=ProviderInfo(name="repository"),
                        cached=False,
                    )

                # 如果数据库也没有数据，重新抛出异常
                raise router_error

        except Exception as e:
            logger.error(
                "Query failed",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
            )

            # 尝试从数据库获取历史数据
            try:
                stored_records = await self.repository.find_by_query(query)
                if stored_records:
                    logger.info(
                        "Retrieved fallback data from storage",
                        extra={"stored_records": len(stored_records)},
                    )

                    # 处理不同类型的返回数据
                    data_points = []
                    for record in stored_records:
                        if hasattr(record, "to_data_point"):
                            # 数据库记录对象
                            data_points.append(record.to_data_point())
                        else:
                            # 已经是DataPoint对象
                            data_points.append(record)

                    return DataResponse(
                        data=data_points,
                        metadata=ResponseMetadata(
                            total_records=len(data_points),
                            query_time_ms=0.0,
                            data_source="repository",
                            cache_hit=False,
                        ),
                        source=ProviderInfo(name="repository"),
                        cached=False,
                    )
            except Exception as storage_error:
                logger.error(
                    "Failed to retrieve fallback data",
                    extra={
                        "error_type": type(storage_error).__name__,
                        "error_message": str(storage_error),
                    },
                )

            raise

    @PerformanceLogger("get_latest")
    async def get_latest(
        self,
        symbols: list[str],
        market: MarketType = MarketType.CN,
        asset_type: AssetType = AssetType.STOCK,
    ) -> DataResponse:
        """获取最新数据.

        Args:
            symbols: 股票代码列表
            market: 市场类型
            asset_type: 资产类型

        Returns:
            DataResponse: 包含最新数据的响应对象
        """
        logger = bind(
            component="DataService",
            action="get_latest",
            symbols=symbols,
            market=market.value,
            asset_type=asset_type.value,
        )
        logger.info("Fetching latest data")

        # 获取过去1天的数据
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=1)

        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        query = DataQuery(
            asset=asset_type,
            market=market,
            symbols=symbols,
            timeframe=TimeFrame.DAY_1,
            start=start_dt,
            end=end_dt,
            start_date=start_date,
            end_date=end_date,
        )

        response = await self.query_data(query)
        logger.info("Latest data retrieved", extra={"records_count": len(response.data)})
        return cast("DataResponse", response)

    @PerformanceLogger("get_historical")
    async def get_historical(
        self,
        symbols: list[str],
        period: str,
        market: MarketType = MarketType.CN,
        asset_type: AssetType = AssetType.STOCK,
        timeframe: TimeFrame = TimeFrame.DAY_1,
    ) -> DataResponse:
        """获取历史数据.

        Args:
            symbols: 股票代码列表
            period: 时间周期（"1d", "1w", "1m", "3m", "1y", "max"）
            market: 市场类型
            asset_type: 资产类型
            timeframe: 时间框架

        Returns:
            DataResponse: 包含历史数据的响应对象
        """
        logger = bind(
            component="DataService",
            action="get_historical",
            symbols=symbols,
            period=period,
            market=market.value,
            asset_type=asset_type.value,
            timeframe=timeframe.value,
        )
        logger.info("Fetching historical data")

        end_date = datetime.now().date()

        period_mapping = {
            "1d": timedelta(days=1),
            "1w": timedelta(weeks=1),
            "1m": timedelta(days=30),
            "3m": timedelta(days=90),
            "1y": timedelta(days=365),
            "max": timedelta(days=3650),  # 10 years
        }

        start_date = end_date - period_mapping.get(period, timedelta(days=30))

        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        query = DataQuery(
            asset=asset_type,
            market=market,
            symbols=symbols,
            timeframe=timeframe,
            start=start_dt,
            end=end_dt,
            start_date=start_date,
            end_date=end_date,
        )

        response = await self.query_data(query)
        logger.info(
            "Historical data retrieved",
            extra={
                "records_count": len(response.data),
                "period": period,
                "date_range": f"{start_date} to {end_date}",
            },
        )
        return cast("DataResponse", response)

    @PerformanceLogger("batch_query")
    async def batch_query(self, queries: list[DataQuery]) -> dict[str, DataResponse | BaseException]:
        """批量查询多个数据请求.

        Args:
            queries: 查询对象列表

        Returns:
            Dict[str, DataResponse]: 查询ID到响应的映射
        """
        logger = bind(component="DataService", action="batch_query", query_count=len(queries))
        logger.info("Starting batch query processing")

        # 并发执行所有查询
        tasks = [self.query_data(query) for query in queries]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # 构建响应映射
        results: dict[str, DataResponse | BaseException] = {}
        success_count = 0
        failure_count = 0
        for i, (query, response) in enumerate(zip(queries, responses, strict=False)):
            query_id = f"query_{i}"
            if isinstance(response, BaseException):
                logger.error(
                    "Query failed",
                    extra={
                        "query_id": query_id,
                        "symbols": query.symbols,
                        "error_type": type(response).__name__,
                        "error_message": str(response),
                    },
                )
                # 为失败的查询创建错误响应
                error_response = DataResponse(
                    data=[],
                    metadata=ResponseMetadata(
                        total_records=0,
                        query_time_ms=0.0,
                        data_source="error",
                        cache_hit=False,
                    ),
                    source=ProviderInfo(name="error", endpoint="error"),
                    cached=False,
                )
                results[query_id] = error_response
                failure_count += 1
            elif isinstance(response, DataResponse):
                logger.info(
                    "Query completed successfully",
                    extra={
                        "query_id": query_id,
                        "symbols": query.symbols,
                        "records_count": len(response.data),
                    },
                )
                results[query_id] = response
                success_count += 1

        logger.info(
            "Batch query completed",
            extra={
                "total_queries": len(queries),
                "successful_queries": success_count,
                "failed_queries": failure_count,
            },
        )
        return results

    def _generate_cache_key(self, query: DataQuery) -> str:
        """生成查询的缓存键.

        Args:
            query: 数据查询对象

        Returns:
            str: 缓存键
        """
        symbols_str = ",".join(sorted(query.symbols)) if query.symbols else ""
        start_str = query.start.isoformat() if query.start else "None"
        end_str = query.end.isoformat() if query.end else "None"
        market_val = query.market.value if query.market else "none"
        timeframe_val = query.timeframe.value if query.timeframe else "none"
        return f"{query.asset.value}:{market_val}:{symbols_str}:{timeframe_val}:{start_str}:{end_str}"

    async def health_check(self) -> dict[str, Any]:
        """健康检查.

        Returns:
            Dict[str, Any]: 各组件健康状态
        """
        health = {
            "router": await self.router.health_check(),
            "cache": await self.cache.health_check(),
            "repository": await self.repository.health_check(),
        }
        return health

    async def close(self) -> None:
        """关闭服务并清理资源."""
        logger.info("Closing DataService")

        if hasattr(self.router, "close"):
            await self.router.close()

        if hasattr(self.cache, "close"):
            await self.cache.close()

        if hasattr(self.repository, "close"):
            await self.repository.close()


class QueryBuilder:
    """链式查询构建器，支持流畅的API调用."""

    def __init__(self, service: DataService):
        """初始化查询构建器.

        Args:
            service: 数据服务实例
        """
        self.service = service
        self.query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=[],
            timeframe=TimeFrame.DAY_1,
            start_date=datetime.now().date() - timedelta(days=30),
            end_date=datetime.now().date(),
        )

    def asset(self, asset_type: str | AssetType) -> "QueryBuilder":
        """设置资产类型.

        Args:
            asset_type: 资产类型

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        if isinstance(asset_type, str):
            asset_type = AssetType(asset_type)
        self.query.asset = asset_type
        return self

    def market(self, market: str | MarketType) -> "QueryBuilder":
        """设置市场类型.

        Args:
            market: 市场类型

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        if isinstance(market, str):
            market = MarketType(market)
        self.query.market = market
        return self

    def symbols(self, symbols: str | list[str]) -> "QueryBuilder":
        """设置股票代码.

        Args:
            symbols: 股票代码或代码列表

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        self.query.symbols = symbols
        return self

    def start(self, start_date: str | date) -> "QueryBuilder":
        """设置开始日期.

        Args:
            start_date: 开始日期

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        self.query.start_date = start_date
        return self

    def end(self, end_date: str | date) -> "QueryBuilder":
        """设置结束日期.

        Args:
            end_date: 结束日期

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        self.query.end_date = end_date
        return self

    def timeframe(self, timeframe: str | TimeFrame) -> "QueryBuilder":
        """设置时间框架.

        Args:
            timeframe: 时间框架

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        if isinstance(timeframe, str):
            timeframe = TimeFrame(timeframe)
        self.query.timeframe = timeframe
        return self

    async def get(self) -> DataResponse:
        """执行查询并获取数据.

        Returns:
            DataResponse: 包含数据点的响应对象
        """
        return cast("DataResponse", await self.service.query_data(self.query))

    def period(self, period: str) -> "QueryBuilder":
        """设置查询周期.

        Args:
            period: 时间周期（"1d", "1w", "1m", "3m", "1y", "max"）

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        period_mapping = {
            "1d": timedelta(days=1),
            "1w": timedelta(weeks=1),
            "1m": timedelta(days=30),
            "3m": timedelta(days=90),
            "1y": timedelta(days=365),
            "max": timedelta(days=3650),  # 10 years
        }

        end_date = datetime.now().date()
        start_date = end_date - period_mapping.get(period, timedelta(days=30))

        # Set both date fields for backward compatibility
        self.query.start_date = start_date
        self.query.end_date = end_date
        self.query.start = datetime.combine(start_date, datetime.min.time())
        self.query.end = datetime.combine(end_date, datetime.max.time())
        return self
