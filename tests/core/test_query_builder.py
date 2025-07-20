"""
Tests for the QueryBuilder class.

This module tests the fluent query builder interface that provides
a chainable API for constructing complex data queries.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from vprism.core.models import AssetType, MarketType, TimeFrame
from vprism.core.query_builder import QueryBuilder


class TestQueryBuilder:
    """Test suite for QueryBuilder class."""

    def test_basic_query_construction(self):
        """Test basic query construction with required fields."""
        query = (QueryBuilder()
            .asset(AssetType.STOCK)
            .build())

        assert query.asset == AssetType.STOCK
        assert query.market is None
        assert query.symbols is None

    def test_full_query_construction(self):
        """Test query construction with all fields."""
        query = (QueryBuilder()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001", "000002"])
            .provider("tushare")
            .timeframe(TimeFrame.DAY_1)
            .start("2024-01-01")
            .end("2024-12-31")
            .limit(100)
            .fields(["open", "close", "volume"])
            .filter("custom_param", "custom_value")
            .build())

        assert query.asset == AssetType.STOCK
        assert query.market == MarketType.CN
        assert query.symbols == ["000001", "000002"]
        assert query.provider == "tushare"
        assert query.timeframe == TimeFrame.DAY_1
        assert query.start == datetime(2024, 1, 1)
        assert query.end == datetime(2024, 12, 31)
        assert query.limit == 100
        assert query.fields == ["open", "close", "volume"]
        assert query.filters == {"custom_param": "custom_value"}

    def test_date_range_method(self):
        """Test date_range convenience method."""
        query = (QueryBuilder()
            .asset(AssetType.STOCK)
            .date_range("2024-01-01", "2024-12-31")
            .build())

        assert query.start == datetime(2024, 1, 1)
        assert query.end == datetime(2024, 12, 31)

    def test_single_symbol_method(self):
        """Test adding single symbols."""
        query = (QueryBuilder()
            .asset(AssetType.STOCK)
            .symbol("000001")
            .symbol("000002")
            .build())

        assert query.symbols == ["000001", "000002"]

    def test_single_field_method(self):
        """Test adding single fields."""
        query = (QueryBuilder()
            .asset(AssetType.STOCK)
            .field("open")
            .field("close")
            .build())

        assert query.fields == ["open", "close"]

    def test_multiple_filters(self):
        """Test adding multiple filters."""
        query = (QueryBuilder()
            .asset(AssetType.STOCK)
            .filter("param1", "value1")
            .filter("param2", "value2")
            .filters({"param3": "value3", "param4": "value4"})
            .build())

        expected_filters = {
            "param1": "value1",
            "param2": "value2",
            "param3": "value3",
            "param4": "value4",
        }
        assert query.filters == expected_filters

    def test_datetime_objects(self):
        """Test using datetime objects directly."""
        start_dt = datetime(2024, 1, 1, 10, 30, 0)
        end_dt = datetime(2024, 12, 31, 15, 45, 0)

        query = (QueryBuilder()
            .asset(AssetType.STOCK)
            .start(start_dt)
            .end(end_dt)
            .build())

        assert query.start == start_dt
        assert query.end == end_dt

    def test_date_string_parsing(self):
        """Test various date string formats."""
        builder = QueryBuilder()

        # Test different formats
        test_cases = [
            ("2024-01-01", datetime(2024, 1, 1)),
            ("2024-01-01T10:30:00", datetime(2024, 1, 1, 10, 30, 0)),
            ("2024-01-01T10:30:00Z", datetime(2024, 1, 1, 10, 30, 0)),
            ("2024-01-01 10:30:00", datetime(2024, 1, 1, 10, 30, 0)),
            ("2024/01/01", datetime(2024, 1, 1)),
            ("2024/01/01 10:30:00", datetime(2024, 1, 1, 10, 30, 0)),
        ]

        for date_str, expected_dt in test_cases:
            result = builder._parse_date_string(date_str)
            assert result == expected_dt

    def test_invalid_date_string(self):
        """Test invalid date string parsing."""
        builder = QueryBuilder()

        with pytest.raises(ValueError) as exc_info:
            builder._parse_date_string("invalid-date")

        assert "Unable to parse date string" in str(exc_info.value)

    def test_missing_asset_error(self):
        """Test error when asset is not provided."""
        with pytest.raises(ValueError) as exc_info:
            QueryBuilder().build()

        assert "Asset type is required" in str(exc_info.value)

    def test_method_chaining(self):
        """Test that all methods return self for chaining."""
        builder = QueryBuilder()

        # Test that each method returns the builder instance
        assert builder.asset(AssetType.STOCK) is builder
        assert builder.market(MarketType.CN) is builder
        assert builder.symbols(["000001"]) is builder
        assert builder.symbol("000002") is builder
        assert builder.provider("test") is builder
        assert builder.timeframe(TimeFrame.DAY_1) is builder
        assert builder.start("2024-01-01") is builder
        assert builder.end("2024-12-31") is builder
        assert builder.date_range("2024-01-01", "2024-12-31") is builder
        assert builder.limit(100) is builder
        assert builder.fields(["open"]) is builder
        assert builder.field("close") is builder
        assert builder.filter("key", "value") is builder
        assert builder.filters({"key2": "value2"}) is builder

    def test_reset_method(self):
        """Test resetting builder to initial state."""
        builder = (QueryBuilder()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001"])
            .provider("test")
            .reset())

        # After reset, should require asset again
        with pytest.raises(ValueError):
            builder.build()

        # Should be able to build after setting asset again
        query = builder.asset(AssetType.BOND).build()
        assert query.asset == AssetType.BOND
        assert query.market is None
        assert query.symbols is None

    def test_copy_method(self):
        """Test copying builder state."""
        original = (QueryBuilder()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001"])
            .provider("test")
            .filter("key", "value"))

        copy = original.copy()

        # Modify copy
        copy.asset(AssetType.BOND).symbols(["000002"])

        # Original should be unchanged
        original_query = original.build()
        copy_query = copy.build()

        assert original_query.asset == AssetType.STOCK
        assert original_query.symbols == ["000001"]
        assert copy_query.asset == AssetType.BOND
        assert copy_query.symbols == ["000002"]

        # Both should have the same market and provider
        assert original_query.market == copy_query.market == MarketType.CN
        assert original_query.provider == copy_query.provider == "test"

    def test_list_copying(self):
        """Test that lists are properly copied to avoid mutation."""
        symbols = ["000001", "000002"]
        fields = ["open", "close"]

        query = (QueryBuilder()
            .asset(AssetType.STOCK)
            .symbols(symbols)
            .fields(fields)
            .build())

        # Modify original lists
        symbols.append("000003")
        fields.append("volume")

        # Query should not be affected
        assert query.symbols == ["000001", "000002"]
        assert query.fields == ["open", "close"]

    def test_empty_lists_handling(self):
        """Test handling of empty lists."""
        query = (QueryBuilder()
            .asset(AssetType.STOCK)
            .symbols([])
            .fields([])
            .build())

        assert query.symbols is None
        assert query.fields is None

    def test_none_values_handling(self):
        """Test handling of None values."""
        query = (QueryBuilder()
            .asset(AssetType.STOCK)
            .symbols(None)
            .fields(None)
            .build())

        assert query.symbols is None
        assert query.fields is None

    def test_repr_method(self):
        """Test string representation of builder."""
        builder = (QueryBuilder()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbols(["000001"]))

        repr_str = repr(builder)
        assert "QueryBuilder(" in repr_str
        assert "asset=stock" in repr_str
        assert "market=cn" in repr_str
        assert "symbols=['000001']" in repr_str

    def test_complex_chaining_example(self):
        """Test a complex real-world example."""
        query = (QueryBuilder()
            .asset(AssetType.STOCK)
            .market(MarketType.CN)
            .symbol("000001")
            .symbol("000002")
            .timeframe(TimeFrame.DAY_1)
            .date_range("2024-01-01", "2024-03-31")
            .provider("tushare")
            .field("open")
            .field("close")
            .field("volume")
            .limit(100)
            .filter("adj", "qfq")
            .filter("ma_period", 20)
            .build())

        assert query.asset == AssetType.STOCK
        assert query.market == MarketType.CN
        assert query.symbols == ["000001", "000002"]
        assert query.timeframe == TimeFrame.DAY_1
        assert query.start == datetime(2024, 1, 1)
        assert query.end == datetime(2024, 3, 31)
        assert query.provider == "tushare"
        assert query.fields == ["open", "close", "volume"]
        assert query.limit == 100
        assert query.filters == {"adj": "qfq", "ma_period": 20}