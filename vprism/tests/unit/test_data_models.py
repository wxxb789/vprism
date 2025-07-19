"""Tests for core data models."""

import pytest
from datetime import datetime
from decimal import Decimal
from pydantic import ValidationError

from vprism.models.data import (
    Asset,
    DataPoint,
    DataQuery,
    DataResponse,
    ResponseMetadata,
    ProviderInfo,
)
from vprism.models.enums import AssetType, DataQuality, MarketType, TimeFrame


class TestAsset:
    """Test Asset data model."""

    def test_asset_creation(self):
        """Test basic asset creation."""
        asset = Asset(
            symbol="000001",
            name="平安银行",
            asset_type=AssetType.STOCK,
            market=MarketType.CN,
            currency="CNY",
            exchange="SZSE",
            sector="Financial Services",
            industry="Banks",
        )
        
        assert asset.symbol == "000001"
        assert asset.name == "平安银行"
        assert asset.asset_type == AssetType.STOCK
        assert asset.market == MarketType.CN
        assert asset.currency == "CNY"
        assert asset.exchange == "SZSE"

    def test_asset_validation(self):
        """Test asset validation."""
        # Test missing required fields
        with pytest.raises(ValidationError):
            Asset(
                symbol="000001",
                # Missing name
                asset_type=AssetType.STOCK,
                market=MarketType.CN,
                currency="CNY",
            )

    def test_asset_optional_fields(self):
        """Test optional fields in asset."""
        asset = Asset(
            symbol="000001",
            name="平安银行",
            asset_type=AssetType.STOCK,
            market=MarketType.CN,
            currency="CNY",
        )
        
        assert asset.exchange is None
        assert asset.sector is None
        assert asset.industry is None
        assert asset.metadata == {}


class TestDataPoint:
    """Test DataPoint model."""

    def test_data_point_creation(self):
        """Test basic data point creation."""
        now = datetime.now()
        point = DataPoint(
            symbol="000001",
            timestamp=now,
            open=Decimal("10.50"),
            high=Decimal("11.00"),
            low=Decimal("10.00"),
            close=Decimal("10.75"),
            volume=Decimal("1000000"),
            amount=Decimal("10750000"),
        )
        
        assert point.symbol == "000001"
        assert point.timestamp == now
        assert point.open == Decimal("10.50")
        assert point.close == Decimal("10.75")

    def test_data_point_optional_fields(self):
        """Test optional fields in data point."""
        now = datetime.now()
        point = DataPoint(
            symbol="000001",
            timestamp=now,
            close=Decimal("10.75"),
        )
        
        assert point.open is None
        assert point.high is None
        assert point.low is None
        assert point.volume is None
        assert point.amount is None
        assert point.extra_fields == {}


class TestDataQuery:
    """Test DataQuery model."""

    def test_data_query_creation(self):
        """Test basic data query creation."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        
        query = DataQuery(
            asset_type=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001", "600519"],
            timeframe=TimeFrame.DAY_1,
            start=start,
            end=end,
            provider="tushare",
        )
        
        assert query.asset_type == AssetType.STOCK
        assert query.market == MarketType.CN
        assert query.symbols == ["000001", "600519"]
        assert query.timeframe == TimeFrame.DAY_1
        assert query.start == start
        assert query.end == end
        assert query.provider == "tushare"

    def test_data_query_optional_fields(self):
        """Test optional fields in data query."""
        query = DataQuery(
            asset_type=AssetType.STOCK,
            symbols=["000001"],
        )
        
        assert query.market is None
        assert query.timeframe is None
        assert query.start is None
        assert query.end is None
        assert query.provider is None

    def test_data_query_validation(self):
        """Test data query validation."""
        # Valid query
        query = DataQuery(
            asset_type=AssetType.STOCK,
            symbols=["000001"],
        )
        assert query is not None

        # Empty symbols should be allowed for market data
        query = DataQuery(
            asset_type=AssetType.STOCK,
            symbols=[],
        )
        assert query.symbols == []


class TestResponseMetadata:
    """Test ResponseMetadata model."""

    def test_response_metadata_creation(self):
        """Test response metadata creation."""
        now = datetime.now()
        metadata = ResponseMetadata(
            total_records=100,
            page=1,
            per_page=100,
            total_pages=1,
            has_next=False,
            has_prev=False,
            quality=DataQuality.HIGH,
            processed_at=now,
        )
        
        assert metadata.total_records == 100
        assert metadata.page == 1
        assert metadata.per_page == 100
        assert metadata.quality == DataQuality.HIGH
        assert metadata.processed_at == now


class TestProviderInfo:
    """Test ProviderInfo model."""

    def test_provider_info_creation(self):
        """Test provider info creation."""
        info = ProviderInfo(
            name="tushare",
            display_name="Tushare",
            endpoint="https://api.tushare.pro",
            version="1.0",
            description="Tushare financial data provider",
        )
        
        assert info.name == "tushare"
        assert info.display_name == "Tushare"
        assert info.endpoint == "https://api.tushare.pro"
        assert info.version == "1.0"


class TestDataResponse:
    """Test DataResponse model."""

    def test_data_response_creation(self):
        """Test data response creation."""
        now = datetime.now()
        point = DataPoint(
            symbol="000001",
            timestamp=now,
            close=Decimal("10.75"),
        )
        
        metadata = ResponseMetadata(
            total_records=1,
            page=1,
            per_page=100,
            quality=DataQuality.HIGH,
            processed_at=now,
        )
        
        provider = ProviderInfo(
            name="tushare",
            display_name="Tushare",
        )
        
        response = DataResponse(
            data=[point],
            metadata=metadata,
            provider=provider,
            cached=False,
            timestamp=now,
        )
        
        assert len(response.data) == 1
        assert response.data[0].symbol == "000001"
        assert response.metadata.total_records == 1
        assert response.provider.name == "tushare"
        assert response.cached is False
        assert response.timestamp == now

    def test_data_response_empty_data(self):
        """Test data response with empty data."""
        now = datetime.now()
        
        response = DataResponse(
            data=[],
            metadata=ResponseMetadata(
                total_records=0,
                page=1,
                per_page=100,
                quality=DataQuality.HIGH,
                processed_at=now,
            ),
            provider=ProviderInfo(name="test", display_name="Test Provider"),
            cached=False,
            timestamp=now,
        )
        
        assert len(response.data) == 0
        assert response.metadata.total_records == 0