"""数据存储仓储模式实现."""

from vprism.core.data.repositories.base import Repository
from vprism.core.data.repositories.cache import CacheRepository
from vprism.core.data.repositories.data import DataRepository
from vprism.core.data.repositories.provider import ProviderRepository
from vprism.core.data.repositories.query import QueryRepository

__all__ = [
    "Repository",
    "DataRepository",
    "ProviderRepository",
    "CacheRepository",
    "QueryRepository",
]
