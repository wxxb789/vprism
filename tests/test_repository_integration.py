"""数据仓储集成测试"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from vprism.core.data.storage.factory import RepositoryFactory
from vprism.core.data.storage.repository import (
    AssetInfo,
    DataQualityMetrics,
    OHLCVData,
    RealTimeQuote,
)
from vprism.core.models import MarketType


class TestRepositoryIntegration:
    """数据仓储集成测试"""

    @pytest.fixture
    def repository(self):
        """创建测试仓储实例"""
        return RepositoryFactory.create_test_repository()

    @pytest.fixture
    def sample_assets(self):
        """创建测试资产数据"""
        return [
            AssetInfo(
                symbol="000001",
                market="cn",
                name="平安银行",
                asset_type="stock",
                currency="CNY",
                exchange="SZSE",
                sector="金融",
                industry="银行业",
                provider="tushare",
            ),
            AssetInfo(
                symbol="AAPL",
                market="us",
                name="Apple Inc.",
                asset_type="stock",
                currency="USD",
                exchange="NASDAQ",
                sector="科技",
                industry="消费电子",
                provider="yahoo",
            ),
            AssetInfo(
                symbol="600000",
                market="cn",
                name="浦发银行",
                asset_type="stock",
                currency="CNY",
                exchange="SSE",
                sector="金融",
                industry="银行业",
                provider="tushare",
            ),
        ]

    @pytest.fixture
    def sample_ohlcv_data(self):
        """创建测试OHLCV数据"""
        base_date = date(2024, 1, 1)
        data = []

        # 为000001创建日线数据
        for i in range(30):
            current_date = base_date + timedelta(days=i)
            base_price = Decimal("10.0") + Decimal(str(i * 0.1))
            data.append(
                OHLCVData(
                    symbol="000001",
                    market="cn",
                    timestamp=datetime.combine(current_date, datetime.min.time()),
                    open_price=base_price,
                    high_price=base_price + Decimal("0.5"),
                    low_price=base_price - Decimal("0.3"),
                    close_price=base_price + Decimal("0.1"),
                    volume=Decimal(str(1000000 + i * 100000)),
                    provider="tushare",
                )
            )

        # 为AAPL创建日线数据
        for i in range(30):
            current_date = base_date + timedelta(days=i)
            base_price = Decimal("150.0") + Decimal(str(i * 2))
            data.append(
                OHLCVData(
                    symbol="AAPL",
                    market="us",
                    timestamp=datetime.combine(current_date, datetime.min.time()),
                    open_price=base_price,
                    high_price=base_price + Decimal("2.5"),
                    low_price=base_price - Decimal("1.5"),
                    close_price=base_price + Decimal("1.0"),
                    volume=Decimal(str(50000000 + i * 1000000)),
                    provider="yahoo",
                )
            )

        return data

    @pytest.mark.asyncio
    async def test_full_data_workflow(self, repository, sample_assets, sample_ohlcv_data):
        """测试完整的数据工作流程"""
        # 1. 保存资产信息
        for asset in sample_assets:
            result = await repository.save_asset_info(asset)
            assert result is True

        # 2. 验证资产保存成功
        retrieved_000001 = await repository.get_asset_info("000001", "cn")
        assert retrieved_000001 is not None
        assert retrieved_000001.name == "平安银行"

        retrieved_aapl = await repository.get_asset_info("AAPL", "us")
        assert retrieved_aapl is not None
        assert retrieved_aapl.name == "Apple Inc."

        # 3. 保存OHLCV数据
        result = await repository.save_ohlcv_data(sample_ohlcv_data)
        assert result is True

        # 4. 验证OHLCV数据保存成功
        ohlcv_000001 = await repository.get_ohlcv_data("000001", "cn", date(2024, 1, 1), date(2024, 1, 30))
        assert len(ohlcv_000001) == 30

        ohlcv_aapl = await repository.get_ohlcv_data("AAPL", "us", date(2024, 1, 1), date(2024, 1, 30))
        assert len(ohlcv_aapl) == 30

        # 5. 验证数据完整性
        assert ohlcv_000001[0].symbol == "000001"
        assert ohlcv_000001[0].market == "cn"
        assert ohlcv_000001[0].close_price > ohlcv_000001[0].open_price

    @pytest.mark.asyncio
    async def test_data_quality_workflow(self, repository, sample_assets):
        """测试数据质量工作流程"""
        # 保存资产信息
        for asset in sample_assets:
            await repository.save_asset_info(asset)

        # 创建数据质量指标
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

        # 验证指标保存成功
        retrieved = await repository.get_data_quality_metrics("000001", "cn", date(2024, 1, 1), date(2024, 1, 31))
        assert retrieved is not None
        assert retrieved.completeness_score == 98.5
        assert retrieved.provider == "tushare"

    @pytest.mark.asyncio
    async def test_market_data_separation(self, repository):
        """测试市场数据分离"""
        # 创建不同市场的资产
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
        ]

        for asset in assets:
            await repository.save_asset_info(asset)

        # 验证市场分离
        cn_symbols = await repository.get_symbols_by_market(MarketType.CN)
        us_symbols = await repository.get_symbols_by_market(MarketType.US)

        assert "000001" in cn_symbols
        assert "AAPL" in us_symbols
        assert "AAPL" not in cn_symbols
        assert "000001" not in us_symbols

    @pytest.mark.asyncio
    async def test_real_time_quote_integration(self, repository, sample_assets):
        """测试实时报价集成"""
        # 保存资产信息
        for asset in sample_assets:
            await repository.save_asset_info(asset)

        # 创建实时报价
        quotes = [
            RealTimeQuote(
                symbol="000001",
                market="cn",
                price=Decimal("10.55"),
                change_amount=Decimal("0.05"),
                change_percent=Decimal("0.47"),
                volume=Decimal("500000"),
                timestamp=datetime.now(),
                provider="tushare",
            ),
            RealTimeQuote(
                symbol="AAPL",
                market="us",
                price=Decimal("150.25"),
                change_amount=Decimal("-1.75"),
                change_percent=Decimal("-1.15"),
                volume=Decimal("25000000"),
                timestamp=datetime.now(),
                provider="yahoo",
            ),
        ]

        # 保存报价
        for quote in quotes:
            result = await repository.save_real_time_quote(quote)
            assert result is True

        # 验证报价保存成功
        retrieved_000001 = await repository.get_real_time_quote("000001", "cn")
        assert retrieved_000001 is not None
        assert retrieved_000001.price == Decimal("10.55")

        retrieved_aapl = await repository.get_real_time_quote("AAPL", "us")
        assert retrieved_aapl is not None
        assert retrieved_aapl.price == Decimal("150.25")

        # 验证最新价格获取
        latest_000001 = await repository.get_latest_price("000001", "cn")
        assert latest_000001 == Decimal("10.55")

        latest_aapl = await repository.get_latest_price("AAPL", "us")
        assert latest_aapl == Decimal("150.25")

    @pytest.mark.asyncio
    async def test_data_consistency(self, repository):
        """测试数据一致性"""
        # 创建测试数据
        asset = AssetInfo(
            symbol="TEST001",
            market="cn",
            name="测试股票",
            asset_type="stock",
            currency="CNY",
            exchange="SZSE",
            provider="tushare",
        )

        ohlcv_data = [
            OHLCVData(
                symbol="TEST001",
                market="cn",
                timestamp=datetime.combine(date(2024, 1, i + 1), datetime.min.time()),
                open_price=Decimal(str(10.0 + i * 0.1)),
                high_price=Decimal(str(10.5 + i * 0.1)),
                low_price=Decimal(str(9.8 + i * 0.1)),
                close_price=Decimal(str(10.2 + i * 0.1)),
                volume=Decimal(str(1000000 + i * 100000)),
                provider="tushare",
            )
            for i in range(10)
        ]

        # 保存数据
        await repository.save_asset_info(asset)
        await repository.save_ohlcv_data(ohlcv_data)

        # 验证数据一致性
        retrieved_asset = await repository.get_asset_info("TEST001", "cn")
        assert retrieved_asset is not None

        retrieved_ohlcv = await repository.get_ohlcv_data("TEST001", "cn", date(2024, 1, 1), date(2024, 1, 10))
        assert len(retrieved_ohlcv) == 10

        # 验证数据匹配（使用近似比较来处理浮点精度问题）
        for i, ohlcv in enumerate(retrieved_ohlcv):
            assert ohlcv.symbol == "TEST001"
            assert ohlcv.market == "cn"
            expected_price = Decimal(str(10.2 + i * 0.1)).quantize(Decimal("0.01"))
            assert abs(ohlcv.close_price - expected_price) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_bulk_operations_performance(self, repository):
        """测试批量操作性能"""
        # 创建大量测试数据
        assets = [
            AssetInfo(
                symbol=f"TEST{i:04d}",
                market="cn",
                name=f"测试股票{i}",
                asset_type="stock",
                currency="CNY",
                exchange="SZSE",
                provider="tushare",
            )
            for i in range(100)
        ]

        ohlcv_data = []
        for asset in assets:
            for day in range(30):
                current_date = date(2024, 1, 1) + timedelta(days=day)
                ohlcv_data.append(
                    OHLCVData(
                        symbol=asset.symbol,
                        market="cn",
                        timestamp=datetime.combine(current_date, datetime.min.time()),
                        open_price=Decimal("10.0"),
                        high_price=Decimal("10.5"),
                        low_price=Decimal("9.5"),
                        close_price=Decimal("10.2"),
                        volume=Decimal("1000000"),
                        provider="tushare",
                    )
                )

        # 批量保存资产信息
        for asset in assets:
            result = await repository.save_asset_info(asset)
            assert result is True

        # 批量保存OHLCV数据
        result = await repository.save_ohlcv_data(ohlcv_data)
        assert result is True

        # 验证数据完整性
        symbols = await repository.get_symbols_by_market(MarketType.CN)
        assert len(symbols) == 100

        # 验证某个资产的数据
        sample_ohlcv = await repository.get_ohlcv_data("TEST0001", "cn", date(2024, 1, 1), date(2024, 1, 30))
        assert len(sample_ohlcv) == 30

    def teardown_method(self):
        """清理测试数据"""
        RepositoryFactory.reset_instance()
