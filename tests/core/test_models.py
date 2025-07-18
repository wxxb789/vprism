"""
Tests for core domain models.

This module contains comprehensive tests for all core data models,
following TDD principles with 100% coverage target.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from vprism.core.models import (
    Asset,
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    MarketType,
    ProviderInfo,
    ResponseMetadata,
    TimeFrame,
)


class TestAssetType:
    """Test AssetType enumeration."""

    def test_asset_type_values(self):
        """Test that all expected asset types are available."""
        expected_types = {
            "stock",
            "bond",
            "etf",
            "fund",
            "futures",
            "options",
            "forex",
            "crypto",
            "index",
            "commodity",
            "warrant",
            "convertible",
            "repo",
            "money_market",
            "structured",
        }
        actual_types = {asset_type.value for asset_type in AssetType}
        assert actual_types == expected_types

    def test_asset_type_string_conversion(self):
        """Test asset type string conversion."""
        assert AssetType.STOCK.value == "stock"
        assert AssetType.STOCK == "stock"


class TestMarketType:
    """Test MarketType enumeration."""

    def test_market_type_values(self):
        """Test that all expected market types are available."""
        expected_markets = {
            "cn",
            "us",
            "hk",
            "eu",
            "jp",
            "kr",
            "sg",
            "au",
            "in",
            "global",
        }
        actual_markets = {market.value for market in MarketType}
        assert actual_markets == expected_markets

    def test_market_type_string_conversion(self):
        """Test market type string conversion."""
        assert MarketType.CN.value == "cn"
        assert MarketType.US == "us"


class TestTimeFrame:
    """Test TimeFrame enumeration."""

    def test_timeframe_values(self):
        """Test that all expected timeframes are available."""
        expected_timeframes = {
            "tick",
            "1s",
            "5s",
            "15s",
            "30s",
            "1m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "6h",
            "12h",
            "1d",
            "1w",
            "1M",
            "1Q",
            "1Y",
        }
        actual_timeframes = {tf.value for tf in TimeFrame}
        assert actual_timeframes == expected_timeframes


class TestDataPoint:
    """Test DataPoint model."""

    def test_valid_data_point_creation(self):
        """Test creating a valid data point."""
        timestamp = datetime.now() - timedelta(hours=1)
        data_point = DataPoint(
            symbol="AAPL",
            timestamp=timestamp,
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.00"),
            close=Decimal("151.00"),
            volume=Decimal("1000000"),
        )

        assert data_point.symbol == "AAPL"
        assert data_point.timestamp == timestamp
        assert data_point.open == Decimal("150.00")
        assert data_point.high == Decimal("152.00")
        assert data_point.low == Decimal("149.00")
        assert data_point.close == Decimal("151.00")
        assert data_point.volume == Decimal("1000000")
        assert data_point.extra_fields == {}

    def test_data_point_with_extra_fields(self):
        """Test data point with additional fields."""
        timestamp = datetime.now() - timedelta(hours=1)
        extra_fields = {"pe_ratio": 25.5, "market_cap": 2500000000}

        data_point = DataPoint(
            symbol="AAPL",
            timestamp=timestamp,
            close=Decimal("151.00"),
            extra_fields=extra_fields,
        )

        assert data_point.extra_fields == extra_fields

    def test_symbol_validation_and_normalization(self):
        """Test symbol validation and uppercase normalization."""
        timestamp = datetime.now() - timedelta(hours=1)

        # Test lowercase symbol gets uppercased
        data_point = DataPoint(
            symbol="aapl", timestamp=timestamp, close=Decimal("151.00")
        )
        assert data_point.symbol == "AAPL"

        # Test symbol with spaces gets trimmed and uppercased
        data_point = DataPoint(
            symbol="  aapl  ", timestamp=timestamp, close=Decimal("151.00")
        )
        assert data_point.symbol == "AAPL"

    def test_empty_symbol_validation(self):
        """Test that empty symbols are rejected."""
        timestamp = datetime.now() - timedelta(hours=1)

        with pytest.raises(ValidationError) as exc_info:
            DataPoint(symbol="", timestamp=timestamp, close=Decimal("151.00"))

        assert "Symbol cannot be empty" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            DataPoint(symbol="   ", timestamp=timestamp, close=Decimal("151.00"))

        assert "Symbol cannot be empty" in str(exc_info.value)

    def test_future_timestamp_validation(self):
        """Test that future timestamps are rejected."""
        future_timestamp = datetime.now() + timedelta(hours=1)

        with pytest.raises(ValidationError) as exc_info:
            DataPoint(
                symbol="AAPL", timestamp=future_timestamp, close=Decimal("151.00")
            )

        assert "Timestamp cannot be in the future" in str(exc_info.value)

    def test_json_serialization(self):
        """Test JSON serialization of data point."""
        timestamp = datetime.now() - timedelta(hours=1)
        data_point = DataPoint(
            symbol="AAPL",
            timestamp=timestamp,
            open=Decimal("150.00"),
            close=Decimal("151.00"),
            volume=Decimal("1000000"),
        )

        json_data = data_point.model_dump()

        # Decimals should be converted to strings
        assert isinstance(json_data["open"], Decimal)
        assert isinstance(json_data["close"], Decimal)
        assert isinstance(json_data["volume"], Decimal)

        # Test JSON encoding
        json_str = data_point.model_dump_json()
        assert '"open":"150.00"' in json_str
        assert '"close":"151.00"' in json_str


class TestAsset:
    """Test Asset model."""

    def test_valid_asset_creation(self):
        """Test creating a valid asset."""
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            asset_type=AssetType.STOCK,
            market=MarketType.US,
            currency="USD",
            exchange="NASDAQ",
            sector="Technology",
            industry="Consumer Electronics",
        )

        assert asset.symbol == "AAPL"
        assert asset.name == "Apple Inc."
        assert asset.asset_type == AssetType.STOCK
        assert asset.market == MarketType.US
        assert asset.currency == "USD"
        assert asset.exchange == "NASDAQ"
        assert asset.sector == "Technology"
        assert asset.industry == "Consumer Electronics"

    def test_symbol_normalization(self):
        """Test symbol normalization."""
        asset = Asset(
            symbol="  aapl  ",
            name="Apple Inc.",
            asset_type=AssetType.STOCK,
            market=MarketType.US,
            currency="USD",
        )

        assert asset.symbol == "AAPL"

    def test_currency_validation(self):
        """Test currency code validation."""
        # Valid 3-character currency
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            asset_type=AssetType.STOCK,
            market=MarketType.US,
            currency="usd",
        )
        assert asset.currency == "USD"

        # Invalid currency length
        with pytest.raises(ValidationError) as exc_info:
            Asset(
                symbol="AAPL",
                name="Apple Inc.",
                asset_type=AssetType.STOCK,
                market=MarketType.US,
                currency="US",
            )

        assert "Currency must be 3-character ISO 4217 code" in str(exc_info.value)

    def test_empty_symbol_validation(self):
        """Test empty symbol validation."""
        with pytest.raises(ValidationError) as exc_info:
            Asset(
                symbol="",
                name="Apple Inc.",
                asset_type=AssetType.STOCK,
                market=MarketType.US,
                currency="USD",
            )

        assert "Symbol cannot be empty" in str(exc_info.value)


class TestDataQuery:
    """Test DataQuery model."""

    def test_basic_query_creation(self):
        """Test creating a basic data query."""
        query = DataQuery(
            asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL", "GOOGL"]
        )

        assert query.asset == AssetType.STOCK
        assert query.market == MarketType.US
        assert query.symbols == ["AAPL", "GOOGL"]
        assert query.provider is None
        assert query.timeframe is None

    def test_symbols_normalization(self):
        """Test symbols list normalization."""
        query = DataQuery(asset=AssetType.STOCK, symbols=["  aapl  ", "googl", "MSFT"])

        assert query.symbols == ["AAPL", "GOOGL", "MSFT"]

    def test_empty_symbols_validation(self):
        """Test empty symbols list validation."""
        with pytest.raises(ValidationError) as exc_info:
            DataQuery(asset=AssetType.STOCK, symbols=[])

        assert "Symbols list cannot be empty if provided" in str(exc_info.value)

    def test_future_date_validation(self):
        """Test future date validation."""
        future_date = datetime.now() + timedelta(days=1)

        with pytest.raises(ValidationError) as exc_info:
            DataQuery(asset=AssetType.STOCK, start=future_date)

        assert "Query dates cannot be in the future" in str(exc_info.value)

    def test_valid_date_validation(self):
        """Test valid date validation passes."""
        past_date = datetime.now() - timedelta(days=1)

        # Should not raise any exception
        query = DataQuery(
            asset=AssetType.STOCK,
            start=past_date,
            end=datetime.now() - timedelta(hours=1),
        )

        assert query.start == past_date
        assert query.end is not None

    def test_limit_validation(self):
        """Test limit parameter validation."""
        # Valid limit
        query = DataQuery(asset=AssetType.STOCK, limit=1000)
        assert query.limit == 1000

        # Invalid limit (too small)
        with pytest.raises(ValidationError):
            DataQuery(asset=AssetType.STOCK, limit=0)

        # Invalid limit (too large)
        with pytest.raises(ValidationError):
            DataQuery(asset=AssetType.STOCK, limit=20000)

    def test_cache_key_generation(self):
        """Test cache key generation."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL", "GOOGL"],
            timeframe=TimeFrame.DAY_1,
            limit=100,
        )

        cache_key = query.cache_key()

        assert "asset:stock" in cache_key
        assert "market:us" in cache_key
        assert "symbols:AAPL,GOOGL" in cache_key
        assert "timeframe:1d" in cache_key
        assert "limit:100" in cache_key

    def test_cache_key_with_optional_fields(self):
        """Test cache key generation with optional fields."""
        query = DataQuery(asset=AssetType.STOCK)
        cache_key = query.cache_key()

        assert cache_key == "asset:stock"


class TestProviderInfo:
    """Test ProviderInfo model."""

    def test_provider_info_creation(self):
        """Test creating provider info."""
        provider_info = ProviderInfo(
            name="test_provider",
            version="1.0.0",
            url="https://api.example.com",
            rate_limit=1000,
            cost="free",
        )

        assert provider_info.name == "test_provider"
        assert provider_info.version == "1.0.0"
        assert provider_info.url == "https://api.example.com"
        assert provider_info.rate_limit == 1000
        assert provider_info.cost == "free"


class TestResponseMetadata:
    """Test ResponseMetadata model."""

    def test_response_metadata_creation(self):
        """Test creating response metadata."""
        metadata = ResponseMetadata(
            execution_time_ms=150.5,
            record_count=100,
            cache_hit=True,
            data_quality_score=0.95,
        )

        assert metadata.execution_time_ms == 150.5
        assert metadata.record_count == 100
        assert metadata.cache_hit is True
        assert metadata.data_quality_score == 0.95
        assert isinstance(metadata.query_time, datetime)
        assert metadata.warnings == []

    def test_data_quality_score_validation(self):
        """Test data quality score validation."""
        # Valid score
        metadata = ResponseMetadata(
            execution_time_ms=100.0, record_count=50, data_quality_score=0.8
        )
        assert metadata.data_quality_score == 0.8

        # Invalid score (too high)
        with pytest.raises(ValidationError):
            ResponseMetadata(
                execution_time_ms=100.0, record_count=50, data_quality_score=1.5
            )

        # Invalid score (negative)
        with pytest.raises(ValidationError):
            ResponseMetadata(
                execution_time_ms=100.0, record_count=50, data_quality_score=-0.1
            )


class TestDataResponse:
    """Test DataResponse model."""

    def create_sample_data_points(self) -> list[DataPoint]:
        """Create sample data points for testing."""
        base_time = datetime.now() - timedelta(hours=2)
        return [
            DataPoint(symbol="AAPL", timestamp=base_time, close=Decimal("150.00")),
            DataPoint(
                symbol="GOOGL",
                timestamp=base_time + timedelta(minutes=1),
                close=Decimal("2500.00"),
            ),
            DataPoint(
                symbol="AAPL",
                timestamp=base_time + timedelta(minutes=2),
                close=Decimal("151.00"),
            ),
        ]

    def test_data_response_creation(self):
        """Test creating a data response."""
        data_points = self.create_sample_data_points()
        query = DataQuery(asset=AssetType.STOCK, symbols=["AAPL", "GOOGL"])
        metadata = ResponseMetadata(execution_time_ms=100.0, record_count=3)
        provider_info = ProviderInfo(name="test_provider")

        response = DataResponse(
            data=data_points, metadata=metadata, source=provider_info, query=query
        )

        assert len(response.data) == 3
        assert response.metadata.record_count == 3
        assert response.source.name == "test_provider"
        assert response.query.asset == AssetType.STOCK

    def test_is_empty_property(self):
        """Test is_empty property."""
        query = DataQuery(asset=AssetType.STOCK)
        metadata = ResponseMetadata(execution_time_ms=100.0, record_count=0)
        provider_info = ProviderInfo(name="test_provider")

        # Empty response
        empty_response = DataResponse(
            data=[], metadata=metadata, source=provider_info, query=query
        )
        assert empty_response.is_empty is True

        # Non-empty response
        data_points = self.create_sample_data_points()
        non_empty_response = DataResponse(
            data=data_points, metadata=metadata, source=provider_info, query=query
        )
        assert non_empty_response.is_empty is False

    def test_symbols_property(self):
        """Test symbols property."""
        data_points = self.create_sample_data_points()
        query = DataQuery(asset=AssetType.STOCK)
        metadata = ResponseMetadata(execution_time_ms=100.0, record_count=3)
        provider_info = ProviderInfo(name="test_provider")

        response = DataResponse(
            data=data_points, metadata=metadata, source=provider_info, query=query
        )

        symbols = response.symbols
        assert set(symbols) == {"AAPL", "GOOGL"}

    def test_date_range_property(self):
        """Test date_range property."""
        data_points = self.create_sample_data_points()
        query = DataQuery(asset=AssetType.STOCK)
        metadata = ResponseMetadata(execution_time_ms=100.0, record_count=3)
        provider_info = ProviderInfo(name="test_provider")

        response = DataResponse(
            data=data_points, metadata=metadata, source=provider_info, query=query
        )

        start_date, end_date = response.date_range

        # Should return the earliest and latest timestamps
        timestamps = [point.timestamp for point in data_points]
        assert start_date == min(timestamps)
        assert end_date == max(timestamps)

    def test_date_range_empty_response(self):
        """Test date_range property with empty response."""
        query = DataQuery(asset=AssetType.STOCK)
        metadata = ResponseMetadata(execution_time_ms=100.0, record_count=0)
        provider_info = ProviderInfo(name="test_provider")

        empty_response = DataResponse(
            data=[], metadata=metadata, source=provider_info, query=query
        )

        with pytest.raises(ValueError) as exc_info:
            _ = empty_response.date_range

        assert "Cannot get date range from empty response" in str(exc_info.value)
