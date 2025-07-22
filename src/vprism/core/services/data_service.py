"""核心数据服务，整合路由器、缓存和提供商的完整数据访问层."""

import asyncio
from datetime import date, datetime, timedelta

from loguru import logger

from vprism.core.logging import PerformanceLogger, bind
from vprism.core.models import (
    AssetType,
    DataQuery,
    DataResponse,
    MarketType,
    ProviderInfo,
    ResponseMetadata,
    TimeFrame,
)
from vprism.core.services.data_router import DataRouter
from vprism.infrastructure.cache.multilevel import MultiLevelCache
from vprism.infrastructure.repositories.data import DataRepository


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
        self.router = router or DataRouter()
        self.cache = cache or MultiLevelCache()
        self.repository = repository or DataRepository()

        logger.info(
            "DataService initialized",
            extra={
                "component": "DataService",
                "action": "initialization",
                "router_type": type(router).__name__ if router else "default",
                "cache_type": type(cache).__name__ if cache else "default",
                "repository_type": type(repository).__name__
                if repository
                else "default",
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

        # 处理默认日期
        if end is None:
            end = datetime.now().date()
        if start is None:
            start = end - timedelta(days=30)

        # 标准化日期格式
        if isinstance(start, str):
            start = datetime.strptime(start, "%Y-%m-%d").date()
        if isinstance(end, str):
            end = datetime.strptime(end, "%Y-%m-%d").date()

        # 创建查询对象
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end, datetime.max.time())

        query = DataQuery(
            asset=asset_type,
            market=market,
            symbols=symbols,
            timeframe=timeframe,
            start=start_dt,
            end=end_dt,
        )

        return await self.query_data(query)

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
        try:
            logger = bind(
                request_id=str(id(query)),
                component="DataService",
                action="query_data",
                symbols=query.symbols,
                market=query.market.value,
                asset_type=query.asset.value,
                timeframe=query.timeframe.value,
            )

            logger.info("Starting data query")

            # 检查缓存
            cache_key = self._generate_cache_key(query)
            logger.debug("Checking cache", extra={"cache_key": cache_key})

            cached_data = await self.cache.get(cache_key)

            if cached_data is not None:
                logger.info(
                    "Cache hit",
                    extra={"cache_key": cache_key, "cached_records": len(cached_data)},
                )
                return DataResponse(
                    data=cached_data,
                    metadata=ResponseMetadata(
                        total_records=len(cached_data),
                        query_time_ms=0.0,
                        data_source="cache",
                        cache_hit=True,
                    ),
                    source=ProviderInfo(name="cache", endpoint="cache"),
                    cached=True,
                )

            logger.info("Cache miss, querying from provider")

            # 从路由器获取数据
            response = await self.router.route_query(query)

            # 缓存结果
            if response.data:
                await self.cache.set(cache_key, response.data)
                logger.info(
                    "Data cached",
                    extra={
                        "cache_key": cache_key,
                        "cached_records": len(response.data),
                    },
                )

                # 存储到数据库
                await self.repository.save_data_points(response.data)
                logger.info(
                    "Data stored to repository",
                    extra={"stored_records": len(response.data)},
                )

            logger.info(
                "Query completed successfully",
                extra={
                    "retrieved_records": len(response.data),
                    "data_source": response.source.name
                    if response.source
                    else "unknown",
                },
            )
            return response

        except Exception as e:
            logger.error(
                "Query failed",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
            )

            # 尝试从数据库获取历史数据
            try:
                stored_data = await self.repository.get_data_points(query)
                if stored_data:
                    logger.info(
                        "Retrieved fallback data from storage",
                        extra={"stored_records": len(stored_data)},
                    )
                    return DataResponse(
                        data=stored_data,
                        query=query,
                        cached=False,
                        metadata={"source": "repository"},
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

        query = DataQuery(
            asset=asset_type,
            market=market,
            symbols=symbols,
            timeframe=TimeFrame.DAY_1,
            start_date=start_date,
            end_date=end_date,
        )

        response = await self.query_data(query)
        logger.info(
            "Latest data retrieved", extra={"records_count": len(response.data)}
        )
        return response

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

        query = DataQuery(
            asset=asset_type,
            market=market,
            symbols=symbols,
            timeframe=timeframe,
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
        return response

    @PerformanceLogger("batch_query")
    async def batch_query(self, queries: list[DataQuery]) -> dict[str, DataResponse]:
        """批量查询多个数据请求.

        Args:
            queries: 查询对象列表

        Returns:
            Dict[str, DataResponse]: 查询ID到响应的映射
        """
        logger = bind(
            component="DataService", action="batch_query", query_count=len(queries)
        )
        logger.info("Starting batch query processing")

        # 并发执行所有查询
        tasks = [self.query_data(query) for query in queries]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # 构建响应映射
        results = {}
        success_count = 0
        failure_count = 0
        for i, (query, response) in enumerate(zip(queries, responses, strict=False)):
            query_id = f"query_{i}"
            if isinstance(response, Exception):
                logger.error(
                    "Query failed",
                    extra={
                        "query_id": query_id,
                        "symbols": query.symbols,
                        "error_type": type(response).__name__,
                        "error_message": str(response),
                    },
                )
                results[query_id] = DataResponse(
                    data=[],
                    query=query,
                    cached=False,
                    metadata={"error": str(response)},
                )
                failure_count += 1
            else:
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
        return (
            f"{query.asset.value}:{query.market.value}:"
            f"{symbols_str}:{query.timeframe.value}:"
            f"{start_str}:{end_str}"
        )

    async def health_check(self) -> dict[str, bool]:
        """健康检查.

        Returns:
            Dict[str, bool]: 各组件健康状态
        """
        health = {
            "router": await self.router.health_check(),
            "cache": await self.cache.health_check(),
            "repository": await self.repository.health_check(),
        }
        return health

    async def close(self):
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
        return await self.service.query_data(self.query)

    def __repr__(self) -> str:
        """字符串表示."""
        return f"QueryBuilder({self.query})"
