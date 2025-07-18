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
