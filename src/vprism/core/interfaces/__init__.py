"""核心接口定义"""

from .providers import DataProvider, ProviderCapability
from .repositories import DataRepository, CacheRepository

__all__ = ["DataProvider", "ProviderCapability", "DataRepository", "CacheRepository"]