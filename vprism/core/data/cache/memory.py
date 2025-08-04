"""线程安全的内存缓存实现."""

import time
from collections import OrderedDict
from threading import Lock
from typing import Any

from .base import CacheStrategy


class ThreadSafeInMemoryCache(CacheStrategy):
    """线程安全的LRU内存缓存."""

    def __init__(self, max_size: int = 1000):
        """初始化内存缓存."""
        self.max_size = max_size
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = Lock()

    async def get(self, key: str) -> Any | None:
        """从缓存获取数据."""
        with self._lock:
            if key not in self._cache:
                return None

            value, expiry = self._cache[key]

            # 检查是否过期
            if time.time() > expiry:
                del self._cache[key]
                return None

            # 移动到末尾（LRU）
            self._cache.move_to_end(key)
            return value

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """设置缓存数据."""
        expiry = time.time() + ttl

        with self._lock:
            # 如果键已存在，先删除旧值
            if key in self._cache:
                del self._cache[key]

            # 如果缓存已满，删除最旧的条目
            while len(self._cache) >= self.max_size and self._cache:
                self._cache.popitem(last=False)

            # 添加新条目
            self._cache[key] = (value, expiry)
            self._cache.move_to_end(key)

    async def delete(self, key: str) -> bool:
        """删除缓存数据."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """清空缓存."""
        with self._lock:
            self._cache.clear()

    async def get_ttl(self, key: str) -> int | None:
        """获取剩余TTL."""
        with self._lock:
            if key not in self._cache:
                return None

            _, expiry = self._cache[key]
            remaining = expiry - time.time()

            if remaining <= 0:
                del self._cache[key]
                return None

            return int(remaining)

    def __len__(self) -> int:
        """获取缓存大小."""
        with self._lock:
            return len(self._cache)

    def size(self) -> int:
        """获取当前缓存大小."""
        return len(self)
