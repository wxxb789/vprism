"""缓存策略和接口定义."""

from abc import ABC, abstractmethod
from typing import Any


class CacheStrategy(ABC):
    """缓存策略抽象基类."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """从缓存获取数据."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int) -> None:
        """设置缓存数据."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存数据."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """清空缓存."""
        pass

    @abstractmethod
    async def get_ttl(self, key: str) -> int | None:
        """获取剩余TTL."""
        pass
