"""
vprism - Modern Financial Data Infrastructure Platform

A next-generation financial data platform that provides unified, composable APIs
for accessing financial data from multiple sources with modern Python architecture.
"""

from typing import Any

from vprism.core.client import VPrismClient
from vprism.core.exceptions import VPrismException
from vprism.core.models import (
    Asset,
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    MarketType,
    TimeFrame,
)
from vprism.core.query_builder import QueryBuilder

__version__ = "0.1.0"
__all__ = [
    "Asset",
    "AssetType",
    "DataPoint",
    "DataQuery",
    "DataResponse",
    "MarketType",
    "TimeFrame",
    "VPrismClient",
    "VPrismException",
    "QueryBuilder",
    "get",
    "aget",
    "query",
    "execute",
    "execute_sync",
]


# Convenience function for quick access
def get(**kwargs: Any) -> DataResponse:
    """
    Convenience function for synchronous data access.

    Args:
        **kwargs: Query parameters (asset, market, symbols, etc.)

    Returns:
        DataResponse: The requested financial data

    Example:
        >>> data = vprism.get(asset="stock", market="cn", symbols=["000001"])
    """
    client = VPrismClient()
    return client.get_sync(**kwargs)


async def aget(**kwargs: Any) -> DataResponse:
    """
    Convenience function for asynchronous data access.

    Args:
        **kwargs: Query parameters (asset, market, symbols, etc.)

    Returns:
        DataResponse: The requested financial data

    Example:
        >>> data = await vprism.aget(asset="stock", market="cn", symbols=["000001"])
    """
    async with VPrismClient() as client:
        return await client.get(**kwargs)


def query() -> QueryBuilder:
    """
    Create a new QueryBuilder for fluent query construction.

    Returns:
        QueryBuilder: New query builder instance

    Example:
        >>> query = (vprism.query()
        ...     .asset(AssetType.STOCK)
        ...     .market(MarketType.CN)
        ...     .symbols(["000001"])
        ...     .timeframe(TimeFrame.DAY_1)
        ...     .date_range("2024-01-01", "2024-12-31")
        ...     .build())
        >>> data = await execute(query)
    """
    return QueryBuilder()


async def execute(query: DataQuery) -> DataResponse:
    """
    Execute a DataQuery object asynchronously.

    Args:
        query: DataQuery object to execute

    Returns:
        DataResponse: The requested financial data

    Example:
        >>> query = vprism.query().asset(AssetType.STOCK).build()
        >>> data = await vprism.execute(query)
    """
    async with VPrismClient() as client:
        return await client.get(
            asset=query.asset,
            market=query.market,
            symbols=query.symbols,
            provider=query.provider,
            timeframe=query.timeframe,
            start=query.start.isoformat() if query.start else None,
            end=query.end.isoformat() if query.end else None,
            limit=query.limit,
            **query.filters,
        )


def execute_sync(query: DataQuery) -> DataResponse:
    """
    Execute a DataQuery object synchronously.

    Args:
        query: DataQuery object to execute

    Returns:
        DataResponse: The requested financial data

    Example:
        >>> query = vprism.query().asset(AssetType.STOCK).build()
        >>> data = vprism.execute_sync(query)
    """
    client = VPrismClient()
    return client.get_sync(
        asset=query.asset,
        market=query.market,
        symbols=query.symbols,
        provider=query.provider,
        timeframe=query.timeframe,
        start=query.start.isoformat() if query.start else None,
        end=query.end.isoformat() if query.end else None,
        limit=query.limit,
        **query.filters,
    )
