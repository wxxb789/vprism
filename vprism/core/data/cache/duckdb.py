"""DuckDB缓存实现."""

import contextlib
import json
import time
from typing import Any

import duckdb
from duckdb import DuckDBPyConnection

from vprism.core.data.cache.base import CacheStrategy


class SimpleDuckDBCache(CacheStrategy):
    """基于DuckDB的持久化缓存."""

    def __init__(self, db_path: str = ":memory:"):
        """初始化DuckDB缓存."""
        self.db_path = db_path
        self._conn: DuckDBPyConnection | None = None
        self._init_database()

    def _init_database(self) -> None:
        """初始化数据库表结构."""
        self._conn = duckdb.connect(self.db_path)

        # 创建缓存表
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key VARCHAR PRIMARY KEY,
                value JSON,
                expiry DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建索引
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_key ON cache(key)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_expiry ON cache(expiry)")

    async def get(self, key: str) -> Any | None:
        """从缓存获取数据."""
        try:
            if not self._conn:
                return None
            result = self._conn.execute(
                "SELECT value FROM cache WHERE key = ? AND expiry > ?",
                [key, time.time()],
            ).fetchone()

            if result:
                return json.loads(result[0])
            return None
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """设置缓存数据."""
        try:
            expiry = time.time() + ttl
            value_json = json.dumps(value, default=str)

            if not self._conn:
                return
            self._conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, value, expiry)
                VALUES (?, ?, ?)
            """,
                [key, value_json, expiry],
            )
        except Exception:
            pass

    async def delete(self, key: str) -> bool:
        """删除缓存数据."""
        try:
            if not self._conn:
                return False
            result = self._conn.execute("DELETE FROM cache WHERE key = ?", [key])
            return bool(result.rowcount)
        except Exception:
            return False

    async def clear(self) -> None:
        """清空缓存."""
        with contextlib.suppress(Exception):
            if self._conn:
                self._conn.execute("DELETE FROM cache")

    async def get_ttl(self, key: str) -> int | None:
        """获取剩余TTL."""
        try:
            if not self._conn:
                return None
            result = self._conn.execute(
                "SELECT expiry FROM cache WHERE key = ? AND expiry > ?",
                [key, time.time()],
            ).fetchone()

            if result:
                remaining = result[0] - time.time()
                return max(0, int(remaining))
            return None
        except Exception:
            return None

    async def cleanup_expired(self) -> int:
        """清理过期缓存项."""
        try:
            if not self._conn:
                return 0
            result = self._conn.execute("DELETE FROM cache WHERE expiry <= ?", [time.time()])
            return int(result.rowcount or 0)
        except Exception:
            return 0

    def is_connected(self) -> bool:
        """检查数据库连接是否处于活动状态."""
        return self._conn is not None

    def close(self) -> None:
        """关闭数据库连接."""
        if self._conn:
            self._conn.close()

    def __del__(self) -> None:
        """析构函数，确保连接关闭."""
        self.close()
