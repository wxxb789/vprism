"""测试数据仓储模式"""

import asyncio
from datetime import date, datetime
from decimal import Decimal

import pytest

from core.data.storage.factory import RepositoryFactory
from core.data.storage.repository import (
    AssetInfo,
    DataQualityMetrics,
    DuckDBRepository,
    OHLCVData,
    RealTimeQuote,
)
from core.models import MarketType


class TestDuckDBRepository:
    """测试DuckDB仓储实现"""

    @pytest.fixture
    def repository(self):
        """创建测试仓储实例"""
        return RepositoryFactory.create_test_repository()

    @pytest.mark.asyncio
    async def test_save_and_get_asset_info(self, repository):
        """测试资产信息保存和获取"""
        asset = AssetInfo(
            symbol="000001",
            market="cn",
            name="平安银行",
            asset_type="stock",
            currency="CNY",
            exchange="SZSE",
            sector="金融",
            industry="银行业",
            provider="tushare",
        )

        # 保存资产信息
        result = await repository.save_asset_info(asset)
        assert result is True

        # 获取资产信息
        retrieved = await repository.get_asset_info("000001", "cn")
        assert retrieved is not None
        assert retrieved.symbol == "000001"
        assert retrieved.name == "平安银行"
        assert retrieved.sector == "金融"

    @pytest.mark.asyncio
    async def test_save_and_get_ohlcv_data(self, repository):
        """测试OHLCV数据保存和获取"""
        ohlcv_data = [
            OHLCVData(
                symbol="000001",
                market="cn",
                timestamp=datetime(2024, 1, 1),
                open_price=Decimal("10.50"),
                high_price=Decimal("10.80"),
                low_price=Decimal("10.30"),
                close_price=Decimal("10.60"),
                volume=Decimal("1000000"),
                provider="tushare",
            ),
            OHLCVData(
                symbol="000001",
                market="cn",
                timestamp=datetime(2024, 1, 2),
                open_price=Decimal("10.60"),
                high_price=Decimal("10.90"),
                low_price=Decimal("10.40"),
                close_price=Decimal("10.75"),
                volume=Decimal("1200000"),
                provider="tushare",
            ),
        ]

        # 保存数据
        result = await repository.save_ohlcv_data(ohlcv_data)
        assert result is True

        # 获取数据
        retrieved = await repository.get_ohlcv_data("000001", "cn", date(2024, 1, 1), date(2024, 1, 2))
        assert len(retrieved) == 2
        assert retrieved[0].close_price == Decimal("10.60")
        assert retrieved[1].close_price == Decimal("10.75")

    @pytest.mark.asyncio
    async def test_save_and_get_real_time_quote(self, repository):
        """测试实时报价保存和获取"""
        quote = RealTimeQuote(
            symbol="000001",
            market="cn",
            price=Decimal("10.55"),
            change_amount=Decimal("0.05"),
            change_percent=Decimal("0.47"),
            volume=Decimal("500000"),
            timestamp=datetime.now(),
            provider="tushare",
        )

        # 保存报价
        result = await repository.save_real_time_quote(quote)
        assert result is True

        # 获取报价
        retrieved = await repository.get_real_time_quote("000001", "cn")
        assert retrieved is not None
        assert retrieved.price == Decimal("10.55")
        assert retrieved.change_amount == Decimal("0.05")

    @pytest.mark.asyncio
    async def test_save_and_get_data_quality_metrics(self, repository):
        """测试数据质量指标保存和获取"""
        metrics = DataQualityMetrics(
            symbol="000001",
            market="cn",
            date_range_start=date(2024, 1, 1),
            date_range_end=date(2024, 1, 31),
            completeness_score=98.5,
            accuracy_score=99.2,
            consistency_score=97.8,
            total_records=22,
            missing_records=0,
            anomaly_count=1,
            provider="tushare",
            checked_at=datetime.now(),
        )

        # 保存指标
        result = await repository.save_data_quality_metrics(metrics)
        assert result is True

        # 获取指标
        retrieved = await repository.get_data_quality_metrics("000001", "cn", date(2024, 1, 1), date(2024, 1, 31))
        assert retrieved is not None
        assert retrieved.completeness_score == 98.5
        assert retrieved.accuracy_score == 99.2

    @pytest.mark.asyncio
    async def test_get_symbols_by_market(self, repository):
        """测试按市场获取股票代码"""
        assets = [
            AssetInfo(
                symbol="000001",
                market="cn",
                name="平安银行",
                asset_type="stock",
                currency="CNY",
                exchange="SZSE",
                provider="tushare",
            ),
            AssetInfo(
                symbol="AAPL",
                market="us",
                name="Apple",
                asset_type="stock",
                currency="USD",
                exchange="NASDAQ",
                provider="yahoo",
            ),
            AssetInfo(
                symbol="600000",
                market="cn",
                name="浦发银行",
                asset_type="stock",
                currency="CNY",
                exchange="SSE",
                provider="tushare",
            ),
        ]

        for asset in assets:
            await repository.save_asset_info(asset)

        # 获取中国市场股票
        cn_symbols = await repository.get_symbols_by_market(MarketType.CN)
        assert "000001" in cn_symbols
        assert "600000" in cn_symbols
        assert "AAPL" not in cn_symbols

        # 获取美国市场股票
        us_symbols = await repository.get_symbols_by_market(MarketType.US)
        assert "AAPL" in us_symbols
        assert "000001" not in us_symbols

    @pytest.mark.asyncio
    async def test_get_latest_price(self, repository):
        """测试获取最新价格"""
        # 先保存OHLCV数据
        ohlcv_data = [
            OHLCVData(
                symbol="000001",
                market="cn",
                timestamp=datetime(2024, 1, 1),
                open_price=Decimal("10.50"),
                high_price=Decimal("10.80"),
                low_price=Decimal("10.30"),
                close_price=Decimal("10.60"),
                volume=Decimal("1000000"),
                provider="tushare",
            )
        ]
        await repository.save_ohlcv_data(ohlcv_data)

        # 获取最新价格
        latest_price = await repository.get_latest_price("000001", "cn")
        assert latest_price == Decimal("10.60")

    @pytest.mark.asyncio
    async def test_get_nonexistent_data(self, repository):
        """测试获取不存在的数据"""
        # 获取不存在的资产信息
        asset = await repository.get_asset_info("NONEXISTENT", "cn")
        assert asset is None

        # 获取不存在的OHLCV数据
        ohlcv = await repository.get_ohlcv_data("NONEXISTENT", "cn", date(2024, 1, 1), date(2024, 1, 1))
        assert len(ohlcv) == 0

        # 获取不存在的实时报价
        quote = await repository.get_real_time_quote("NONEXISTENT", "cn")
        assert quote is None

    @pytest.mark.asyncio
    async def test_update_existing_asset(self, repository):
        """测试更新已存在的资产信息"""
        # 首先创建资产
        asset = AssetInfo(
            symbol="000001",
            market="cn",
            name="平安银行",
            asset_type="stock",
            currency="CNY",
            exchange="SZSE",
            provider="tushare",
        )
        await repository.save_asset_info(asset)

        # 更新资产信息
        updated_asset = AssetInfo(
            symbol="000001",
            market="cn",
            name="平安银行股份有限公司",
            asset_type="stock",
            currency="CNY",
            exchange="SZSE",
            sector="金融业",
            provider="tushare",
        )
        await repository.save_asset_info(updated_asset)

        # 验证更新
        retrieved = await repository.get_asset_info("000001", "cn")
        assert retrieved.name == "平安银行股份有限公司"
        assert retrieved.sector == "金融业"


class TestRepositoryFactory:
    """测试仓储工厂"""

    def test_create_repository(self):
        """测试创建仓储实例"""
        # 测试内存数据库
        repo = RepositoryFactory.create_repository(use_memory=True)
        assert isinstance(repo, DuckDBRepository)
        repo.close()

        # 测试文件数据库
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = os.path.join(tmp_dir, "test.duckdb")
            repo = RepositoryFactory.create_repository(db_path=tmp_path)
            assert isinstance(repo, DuckDBRepository)
            repo.close()

    def test_singleton_pattern(self):
        """测试单例模式"""
        repo1 = RepositoryFactory.get_default_repository()
        repo2 = RepositoryFactory.get_default_repository()

        assert repo1 is repo2

        # 清理
        RepositoryFactory.reset_instance()

    def test_create_test_repository(self):
        """测试创建测试仓储"""
        repo = RepositoryFactory.create_test_repository()
        assert isinstance(repo, DuckDBRepository)
        repo.close()


class TestConcurrentOperations:
    """测试并发操作"""

    @pytest.fixture
    def repository(self):
        return RepositoryFactory.create_test_repository()

    @pytest.mark.asyncio
    async def test_concurrent_save_operations(self, repository):
        """测试并发保存操作"""

        async def save_worker(worker_id):
            asset = AssetInfo(
                symbol=f"TEST{worker_id}",
                market="cn",
                name=f"测试股票{worker_id}",
                asset_type="stock",
                currency="CNY",
                exchange="SZSE",
                provider="tushare",
            )
            return await repository.save_asset_info(asset)

        # 并发保存多个资产
        tasks = [save_worker(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert all(results)

        # 验证所有资产都已保存
        for i in range(10):
            asset = await repository.get_asset_info(f"TEST{i}", "cn")
            assert asset is not None
            assert asset.name == f"测试股票{i}"
