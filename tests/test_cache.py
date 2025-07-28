"""测试多层缓存架构的实现."""

import asyncio

import pytest

from core.data.cache import (
    CacheKey,
    MultiLevelCache,
    SimpleDuckDBCache,
    ThreadSafeInMemoryCache,
)
from core.models import AssetType, DataQuery, MarketType, TimeFrame


class TestCacheKey:
    """测试缓存键生成."""

    def test_generate_key_basic(self):
        """测试基本缓存键生成."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
        )

        cache_key = CacheKey(query)

        assert len(cache_key.key) == 16  # SHA256前16位
        assert cache_key.ttl == 3600  # 日线数据1小时缓存

    def test_generate_key_different_queries(self):
        """测试不同查询产生不同键."""
        query1 = DataQuery(asset=AssetType.STOCK, symbols=["000001"])
        query2 = DataQuery(asset=AssetType.STOCK, symbols=["000002"])

        key1 = CacheKey(query1).key
        key2 = CacheKey(query2).key

        assert key1 != key2

    def test_generate_key_same_queries(self):
        """测试相同查询产生相同键."""
        query1 = DataQuery(asset=AssetType.STOCK, symbols=["000001"])
        query2 = DataQuery(asset=AssetType.STOCK, symbols=["000001"])

        key1 = CacheKey(query1).key
        key2 = CacheKey(query2).key

        assert key1 == key2

    def test_calculate_ttl(self):
        """测试TTL计算."""
        test_cases = [
            (TimeFrame.TICK, 5),
            (TimeFrame.MINUTE_1, 60),
            (TimeFrame.DAY_1, 3600),
            (TimeFrame.WEEK_1, 86400),
            (TimeFrame.DAY_1, 3600),  # 使用有效值代替None
        ]

        for timeframe, expected_ttl in test_cases:
            query = DataQuery(
                asset=AssetType.STOCK, symbols=["000001"], timeframe=timeframe
            )
            cache_key = CacheKey(query)
            assert cache_key.ttl == expected_ttl


class TestThreadSafeInMemoryCache:
    """测试线程安全内存缓存."""

    @pytest.fixture
    def cache(self):
        """创建缓存实例."""
        return ThreadSafeInMemoryCache(max_size=100)

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """测试基本的set和get操作."""
        await cache.set("key1", "value1", ttl=60)
        result = await cache.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, cache):
        """测试获取不存在的键."""
        result = await cache.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_expiry(self, cache):
        """测试过期机制."""
        # 设置短TTL
        await cache.set("key1", "value1", ttl=0.1)

        # 立即获取应该成功
        result = await cache.get("key1")
        assert result == "value1"

        # 等待过期
        await asyncio.sleep(0.2)

        # 过期后应该返回None
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self, cache):
        """测试LRU驱逐机制."""
        # 填满缓存
        for i in range(100):
            await cache.set(f"key{i}", f"value{i}", ttl=3600)

        # 访问第一个键使其成为最近使用
        await cache.get("key0")

        # 添加新键触发驱逐
        await cache.set("key100", "value100", ttl=3600)

        # key0应该还在（最近使用过）
        assert await cache.get("key0") == "value0"

        # key1应该被驱逐
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_concurrent_access(self, cache):
        """测试并发访问."""

        async def worker(worker_id):
            for i in range(10):
                key = f"worker{worker_id}_key{i}"
                value = f"worker{worker_id}_value{i}"
                await cache.set(key, value, ttl=60)
                result = await cache.get(key)
                assert result == value

        # 启动多个并发任务
        tasks = [worker(i) for i in range(5)]
        await asyncio.gather(*tasks)

    @pytest.mark.asyncio
    async def test_update_existing_key(self, cache):
        """测试更新已存在的键."""
        await cache.set("key1", "value1", ttl=60)
        await cache.set("key1", "value2", ttl=60)

        result = await cache.get("key1")
        assert result == "value2"


class TestSimpleDuckDBCache:
    """测试DuckDB缓存."""

    @pytest.fixture
    def cache(self, tmp_path):
        """创建DuckDB缓存实例."""
        db_path = tmp_path / "test_cache.duckdb"
        return SimpleDuckDBCache(str(db_path))

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """测试基本的set和get操作."""
        test_data = {"price": 100.0, "volume": 1000}

        await cache.set("key1", test_data, ttl=3600)
        result = await cache.get("key1")

        assert result == test_data

    @pytest.mark.asyncio
    async def test_persistence(self, cache):
        """测试数据持久化."""
        test_data = {"persistent": "data"}

        # 设置数据
        await cache.set("persistent_key", test_data, ttl=3600)

        # 创建新的缓存实例（应该能读取到之前的数据）
        new_cache = SimpleDuckDBCache(cache.db_path)
        result = await new_cache.get("persistent_key")

        assert result == test_data

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache):
        """测试清理过期数据."""
        # 设置过期数据
        await cache.set("expired_key", "expired_value", ttl=0.1)

        # 等待过期
        await asyncio.sleep(0.2)

        # 应该获取不到过期数据
        result = await cache.get("expired_key")
        assert result is None


class TestMultiLevelCache:
    """测试多级缓存."""

    @pytest.fixture
    def cache(self):
        """创建多级缓存实例."""
        return MultiLevelCache()

    @pytest.mark.asyncio
    async def test_l1_cache_hit(self, cache):
        """测试L1缓存命中."""
        query = DataQuery(asset=AssetType.STOCK, symbols=["TEST"])
        test_data = {"data": "test"}

        # 先设置数据
        cache_key = CacheKey(query)
        await cache.l1_cache.set(cache_key.key, test_data, ttl=60)

        # 从多级缓存获取
        result = await cache.get_data(query)

        assert result == test_data

    @pytest.mark.asyncio
    async def test_l2_cache_fallback(self, cache):
        """测试L2缓存回退."""
        query = DataQuery(asset=AssetType.STOCK, symbols=["TEST"])
        test_data = {"data": "test"}

        # 设置数据到L2缓存
        cache_key = CacheKey(query)
        await cache.l2_cache.set(cache_key.key, test_data, ttl=60)

        # 从多级缓存获取（应该回退到L2）
        result = await cache.get_data(query)

        assert result == test_data

    @pytest.mark.asyncio
    async def test_set_data(self, cache):
        """测试设置数据到多级缓存."""
        query = DataQuery(asset=AssetType.STOCK, symbols=["TEST"])
        test_data = {"data": "test"}

        await cache.set_data(query, test_data)

        # 验证数据被设置到两个缓存层
        cache_key = CacheKey(query)

        l1_result = await cache.l1_cache.get(cache_key.key)
        l2_result = await cache.l2_cache.get(cache_key.key)

        assert l1_result == test_data
        assert l2_result == test_data

    @pytest.mark.asyncio
    async def test_different_ttl_levels(self, cache):
        """测试不同缓存层的TTL设置."""
        query = DataQuery(asset=AssetType.STOCK, symbols=["TEST"])
        test_data = {"data": "test"}

        await cache.set_data(query, test_data)

        cache_key = CacheKey(query)

        # L1应该有较短TTL
        l1_ttl = await cache.l1_cache.get_ttl(cache_key.key)
        l2_ttl = await cache.l2_cache.get_ttl(cache_key.key)

        assert l1_ttl is not None
        assert l2_ttl is not None
        assert l2_ttl > l1_ttl

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache):
        """测试缓存未命中."""
        query = DataQuery(asset=AssetType.STOCK, symbols=["NONEXISTENT"])

        result = await cache.get_data(query)

        assert result is None

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self, cache):
        """测试并发缓存操作."""

        async def worker(worker_id):
            for i in range(5):
                query = DataQuery(
                    asset=AssetType.STOCK, symbols=[f"worker{worker_id}_stock{i}"]
                )
                test_data = {"worker": worker_id, "index": i}

                # 设置数据
                await cache.set_data(query, test_data)

                # 获取数据
                result = await cache.get_data(query)
                assert result == test_data

        # 启动多个并发任务
        tasks = [worker(i) for i in range(3)]
        await asyncio.gather(*tasks)
