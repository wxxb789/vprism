"""DuckDB缓存实现."""

import asyncio
import json
import time
from typing import Any, Optional
import duckdb

from .base import CacheStrategy


class SimpleDuckDBCache(CacheStrategy):
    """基于DuckDB的持久化缓存."""
    
    def __init__(self, db_path: str = ":memory:"):
        """初始化DuckDB缓存."""
        self.db_path = db_path
        self._conn = None
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
    
    async def get(self, key: str) -> Optional[Any]:
        """从缓存获取数据."""
        try:
            result = self._conn.execute(
                "SELECT value FROM cache WHERE key = ? AND expiry > ?",
                [key, time.time()]
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
            
            self._conn.execute("""
                INSERT OR REPLACE INTO cache (key, value, expiry)
                VALUES (?, ?, ?)
            """, [key, value_json, expiry])
        except Exception:
            pass
    
    async def delete(self, key: str) -> bool:
        """删除缓存数据."""
        try:
            result = self._conn.execute(
                "DELETE FROM cache WHERE key = ?",
                [key]
            )
            return result.rowcount > 0
        except Exception:
            return False
    
    async def clear(self) -> None:
        """清空缓存."""
        try:
            self._conn.execute("DELETE FROM cache")
        except Exception:
            pass
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """获取剩余TTL."""
        try:
            result = self._conn.execute(
                "SELECT expiry FROM cache WHERE key = ? AND expiry > ?",
                [key, time.time()]
            ).fetchone()
            
            if result:
                remaining = result[0] - time.time()
                return max(0, int(remaining))
            return None
        except Exception:
            return None
    
    async def cleanup_expired(self) -> int:
        """清理过期数据."""
        """清理过期缓存项."""
        try:
            result = self._conn.execute(
                "DELETE FROM cache WHERE expiry <= ?",
                [time.time()]
            )
            return result.rowcount
        except Exception:
            return 0
    
    def close(self) -> None:
        """关闭数据库连接."""
        if self._conn:
            self._conn.close()
    
    def __del__(self):
        """析构函数，确保连接关闭."""
        self.close()