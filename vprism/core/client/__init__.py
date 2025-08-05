"""Client module - main client interface."""

from vprism.core.client.builder import QueryBuilder
from vprism.core.client.client import VPrismClient

__all__ = [
    "VPrismClient",
    "QueryBuilder",
]
