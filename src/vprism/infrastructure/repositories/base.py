"""仓储模式基础接口."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """仓储模式基础接口."""

    @abstractmethod
    async def save(self, entity: T) -> str:
        """保存实体."""
        pass

    @abstractmethod
    async def find_by_id(self, entity_id: str) -> T | None:
        """根据ID查找实体."""
        pass

    @abstractmethod
    async def find_all(self, limit: int | None = None, offset: int = 0) -> list[T]:
        """查找所有实体."""
        pass

    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """删除实体."""
        pass

    @abstractmethod
    async def exists(self, entity_id: str) -> bool:
        """检查实体是否存在."""
        pass
