"""Core data service — unified access layer over router, cache, and storage."""

import asyncio
from datetime import date, datetime, timedelta
from typing import Any, cast

from loguru import logger

from vprism.core.data.cache.multilevel import MultiLevelCache
from vprism.core.data.providers.registry import ProviderRegistry
from vprism.core.data.repositories.data import DataRepository
from vprism.core.data.routing import DataRouter
from vprism.core.data.storage.database import DatabaseManager
from vprism.core.models.base import DataPoint
from vprism.core.models.market import AssetType, MarketType, TimeFrame
from vprism.core.models.query import DataQuery
from vprism.core.models.response import DataResponse, ProviderInfo, ResponseMetadata
from vprism.core.monitoring import PerformanceLogger

# Shared period-to-timedelta mapping (used by get_historical and QueryBuilder)
PERIOD_MAPPING: dict[str, timedelta] = {
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
    "1m": timedelta(days=30),
    "3m": timedelta(days=90),
    "1y": timedelta(days=365),
    "max": timedelta(days=3650),
}


def _to_date(value: str | date | datetime | None, default: date | None = None) -> date:
    """Coerce various date representations to a date object."""
    if value is None:
        return default or datetime.now().date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    return value


class DataService:
    """Core data service providing a unified data access interface."""

    def __init__(
        self,
        router: DataRouter | None = None,
        cache: MultiLevelCache | None = None,
        repository: DataRepository | None = None,
    ):
        self.router = router or DataRouter(ProviderRegistry())
        self.cache = cache or MultiLevelCache()
        self.repository = repository or DataRepository(DatabaseManager())

    # ------------------------------------------------------------------ #
    # Simple API
    # ------------------------------------------------------------------ #

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
        """Primary entry point for fetching data.

        Examples:
            >>> response = await service.get("000001", start="2024-01-01")
            >>> response = await service.get(["AAPL", "GOOGL"], market=MarketType.US)
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        end_date = _to_date(end)
        start_date = _to_date(start, default=end_date - timedelta(days=30))

        query = DataQuery(
            asset=asset_type,
            market=market,
            symbols=symbols,
            raw_symbols=symbols,
            timeframe=timeframe,
            start=datetime.combine(start_date, datetime.min.time()),
            end=datetime.combine(end_date, datetime.max.time()),
        )
        return await self.query_data(query)

    def query(self) -> "QueryBuilder":
        """Fluent API: create a query builder.

        Examples:
            >>> response = await service.query() \\
            ...     .symbols(["000001"]).start("2024-01-01").get()
        """
        return QueryBuilder(self)

    # ------------------------------------------------------------------ #
    # Core query logic
    # ------------------------------------------------------------------ #

    @PerformanceLogger("query_data")
    async def query_data(self, query: DataQuery) -> DataResponse:
        """Execute a data query with cache → provider → storage fallback."""
        # 1. Cache check
        cached_data = await self.cache.get_data(query)
        if cached_data is not None:
            data_points = [DataPoint(**item) if isinstance(item, dict) else item for item in cached_data]
            logger.info("Cache hit", extra={"symbols": query.symbols, "records": len(data_points)})
            return DataResponse(
                data=data_points,
                metadata=ResponseMetadata(total_records=len(data_points), query_time_ms=0.0, data_source="cache", cache_hit=True),
                source=ProviderInfo(name="cache", endpoint="cache"),
                cached=True,
            )

        # 2. Provider fetch
        try:
            provider = await self.router.route_query(query)
            response: DataResponse = await provider.get_data(query)

            if response.data:
                await self.cache.set_data(query, response.data)
                if response.source:
                    records = [self.repository.from_data_point(dp, response.source.name) for dp in response.data]
                    await self.repository.save_batch(records)

            source_name = response.source.name if response.source else "unknown"
            logger.info("Provider fetch OK", extra={"symbols": query.symbols, "records": len(response.data), "source": source_name})
            return response

        except Exception as provider_err:
            logger.warning("Provider failed, trying storage fallback", extra={"error": str(provider_err)})
            fallback = await self._fallback_from_storage(query)
            if fallback is not None:
                return fallback
            raise

    # ------------------------------------------------------------------ #
    # Convenience methods
    # ------------------------------------------------------------------ #

    @PerformanceLogger("get_latest")
    async def get_latest(
        self,
        symbols: list[str],
        market: MarketType = MarketType.CN,
        asset_type: AssetType = AssetType.STOCK,
    ) -> DataResponse:
        """Fetch the latest data (past 1 day)."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=1)
        query = DataQuery(
            asset=asset_type,
            market=market,
            symbols=symbols,
            timeframe=TimeFrame.DAY_1,
            start=datetime.combine(start_date, datetime.min.time()),
            end=datetime.combine(end_date, datetime.max.time()),
            start_date=start_date,
            end_date=end_date,
        )
        return cast("DataResponse", await self.query_data(query))

    @PerformanceLogger("get_historical")
    async def get_historical(
        self,
        symbols: list[str],
        period: str,
        market: MarketType = MarketType.CN,
        asset_type: AssetType = AssetType.STOCK,
        timeframe: TimeFrame = TimeFrame.DAY_1,
    ) -> DataResponse:
        """Fetch historical data for a named period (e.g. '1m', '3m', '1y')."""
        end_date = datetime.now().date()
        start_date = end_date - PERIOD_MAPPING.get(period, timedelta(days=30))
        query = DataQuery(
            asset=asset_type,
            market=market,
            symbols=symbols,
            timeframe=timeframe,
            start=datetime.combine(start_date, datetime.min.time()),
            end=datetime.combine(end_date, datetime.max.time()),
            start_date=start_date,
            end_date=end_date,
        )
        return cast("DataResponse", await self.query_data(query))

    @PerformanceLogger("batch_query")
    async def batch_query(self, queries: list[DataQuery]) -> dict[str, DataResponse | BaseException]:
        """Execute multiple queries concurrently."""
        tasks = [self.query_data(q) for q in queries]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

        results: dict[str, DataResponse | BaseException] = {}
        for i, (query, result) in enumerate(zip(queries, results_raw, strict=False)):
            key = f"query_{i}"
            if isinstance(result, BaseException):
                logger.error("Batch query failed", extra={"query_id": key, "symbols": query.symbols, "error": str(result)})
                results[key] = DataResponse(
                    data=[],
                    metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="error", cache_hit=False),
                    source=ProviderInfo(name="error", endpoint="error"),
                    cached=False,
                )
            else:
                results[key] = result
        return results

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _fallback_from_storage(self, query: DataQuery) -> DataResponse | None:
        """Try to serve query from stored data. Returns None if unavailable."""
        try:
            stored = await self.repository.find_by_query(query)
            if not stored:
                return None
            points = [r.to_data_point() if hasattr(r, "to_data_point") else r for r in stored if hasattr(r, "to_data_point") or isinstance(r, DataPoint)]
            logger.info("Served from storage fallback", extra={"records": len(points)})
            return DataResponse(
                data=points,
                metadata=ResponseMetadata(total_records=len(points), query_time_ms=0.0, data_source="repository", cache_hit=False),
                source=ProviderInfo(name="repository"),
                cached=False,
            )
        except Exception as e:
            logger.error("Storage fallback failed", extra={"error": str(e)})
            return None

    def _generate_cache_key(self, query: DataQuery) -> str:
        """Generate a deterministic cache key for a query."""
        symbols_str = ",".join(sorted(query.symbols)) if query.symbols else ""
        start_str = query.start.isoformat() if query.start else "None"
        end_str = query.end.isoformat() if query.end else "None"
        market_val = query.market.value if query.market else "none"
        timeframe_val = query.timeframe.value if query.timeframe else "none"
        return f"{query.asset.value}:{market_val}:{symbols_str}:{timeframe_val}:{start_str}:{end_str}"

    async def health_check(self) -> dict[str, Any]:
        """Return component health status."""
        router_health_raw = await self.router.health_check() if hasattr(self.router, "health_check") else {}
        router_health: dict[str, Any] = router_health_raw if isinstance(router_health_raw, dict) else {}
        cache_health_raw: Any = await self.cache.health_check() if hasattr(self.cache, "health_check") else {}
        cache_health: dict[str, Any] = cache_health_raw if isinstance(cache_health_raw, dict) else {}
        repo_health_raw: Any = self.repository.health_check() if hasattr(self.repository, "health_check") else False
        return {"router": router_health, "cache": cache_health, "repository": bool(repo_health_raw)}

    async def close(self) -> None:
        """Shut down service and release resources."""
        logger.info("Closing DataService")
        if hasattr(self.router, "close"):
            await self.router.close()
        if hasattr(self.cache, "close"):
            await self.cache.close()
        if hasattr(self.repository, "close"):
            await self.repository.close()


# ------------------------------------------------------------------ #
# QueryBuilder (fluent API)
# ------------------------------------------------------------------ #


class QueryBuilder:
    """Fluent query builder for DataService."""

    def __init__(self, service: DataService):
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
        self.query.asset = AssetType(asset_type) if isinstance(asset_type, str) else asset_type
        return self

    def market(self, market: str | MarketType) -> "QueryBuilder":
        self.query.market = MarketType(market) if isinstance(market, str) else market
        return self

    def symbols(self, symbols: str | list[str]) -> "QueryBuilder":
        if isinstance(symbols, str):
            symbols = [symbols]
        self.query.raw_symbols = symbols
        self.query.symbols = symbols
        if not self.query.market:
            self.query.market = MarketType.CN
        return self

    def start(self, start_date: str | date) -> "QueryBuilder":
        self.query.start_date = datetime.strptime(start_date, "%Y-%m-%d").date() if isinstance(start_date, str) else start_date
        return self

    def end(self, end_date: str | date) -> "QueryBuilder":
        self.query.end_date = datetime.strptime(end_date, "%Y-%m-%d").date() if isinstance(end_date, str) else end_date
        return self

    def timeframe(self, timeframe: str | TimeFrame) -> "QueryBuilder":
        self.query.timeframe = TimeFrame(timeframe) if isinstance(timeframe, str) else timeframe
        return self

    def period(self, period: str) -> "QueryBuilder":
        end_date = datetime.now().date()
        start_date = end_date - PERIOD_MAPPING.get(period, timedelta(days=30))
        self.query.start_date = start_date
        self.query.end_date = end_date
        self.query.start = datetime.combine(start_date, datetime.min.time())
        self.query.end = datetime.combine(end_date, datetime.max.time())
        return self

    async def get(self) -> DataResponse:
        """Execute the built query."""
        return cast("DataResponse", await self.service.query_data(self.query))
