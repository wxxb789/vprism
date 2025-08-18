"""
Tests for data consistency validation between vprism and akshare.
"""

from datetime import datetime
from unittest.mock import patch, Mock

import pandas as pd
import pytest

from vprism.core.validation import ConsistencyReport, DataConsistencyValidator
from vprism.core.client.client import VPrismClient
from vprism.core.models.market import AssetType, MarketType

class TestDataConsistencyValidator:
    """Test DataConsistencyValidator class."""

    @pytest.fixture
    def validator(self):
        """Fixture for DataConsistencyValidator with a mock client."""
        mock_client = Mock(spec=VPrismClient)
        return DataConsistencyValidator(client=mock_client, tolerance=0.01)

    async def test_validate_consistency_identical_data(self, validator):
        """Test validation with identical data."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 5)

        dates = pd.date_range(start=start_date, end=end_date, freq="D")
        data = pd.DataFrame({"timestamp": dates, "close_price": [100.5, 101.5, 102.5, 103.5, 104.5]})

        with patch.object(validator, "_get_vprism_data", return_value=data.copy()), \
             patch.object(validator, "_get_external_data", return_value=data.copy()):
            report = await validator.validate_consistency("TEST", start_date.date(), end_date.date(), AssetType.STOCK, MarketType.CN)

        assert report.symbol == "TEST"
        assert report.total_records == 5
        assert report.matching_records == 5
        assert report.mismatching_records == 0
        assert report.consistency_percentage == 100.0
        assert len(report.issues) == 0

    async def test_validate_consistency_with_differences(self, validator):
        """Test validation with slight differences."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)

        vprism_data = pd.DataFrame({"timestamp": pd.date_range(start=start_date, periods=3, freq="D"), "close_price": [100.5, 101.5, 102.5]})
        akshare_data = vprism_data.copy()
        akshare_data.loc[1, "close_price"] = 101.6

        with patch.object(validator, "_get_vprism_data", return_value=vprism_data), \
             patch.object(validator, "_get_external_data", return_value=akshare_data):
            report = await validator.validate_consistency("TEST", start_date.date(), end_date.date(), AssetType.STOCK, MarketType.CN)

        assert report.symbol == "TEST"
        assert report.total_records == 3
        assert report.mismatching_records == 1
        assert report.matching_records == 2

    async def test_validate_consistency_missing_data(self, validator):
        """Test validation with missing data."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 5)

        vprism_data = pd.DataFrame({"timestamp": pd.date_range(start=start_date, periods=3, freq="D"), "close_price": [100.5, 101.5, 102.5]})
        akshare_data = pd.DataFrame({"timestamp": pd.date_range(start=start_date, periods=5, freq="D"), "close_price": [100.5, 101.5, 102.5, 103.5, 104.5]})

        with patch.object(validator, "_get_vprism_data", return_value=vprism_data), \
             patch.object(validator, "_get_external_data", return_value=akshare_data):
            report = await validator.validate_consistency("TEST", start_date.date(), end_date.date(), AssetType.STOCK, MarketType.CN)

        assert report.missing_in_vprism == 2
        assert report.missing_in_external == 0


class TestConsistencyIntegration:
    """Integration tests for consistency validation."""

    @pytest.fixture(scope="class")
    def validator(self):
        """Fixture to provide an instance of the DataConsistencyValidator."""
        client = VPrismClient()
        # Compare against a different provider for a more realistic test
        return DataConsistencyValidator(client=client, external_provider="yfinance")

    @pytest.mark.integration
    async def test_realistic_stock_comparison(self, validator):
        """Test realistic stock data comparison."""
        start_date = datetime(2023, 1, 15).date()
        end_date = datetime(2023, 1, 19).date()

        # This symbol is known to exist in both yfinance (as 000001.SZ) and akshare
        report = await validator.validate_consistency(
            symbol="000001.SZ",
            start_date=start_date,
            end_date=end_date,
            asset_type=AssetType.STOCK,
            market=MarketType.CN
        )

        assert report.symbol == "000001.SZ"
        assert report.total_records > 0
        # It's okay to have mismatches, we are just testing the validator runs
        assert report.mismatching_records >= 0
        assert 0 <= report.consistency_percentage <= 100.0

    @pytest.mark.integration
    async def test_weekend_data_handling(self, validator):
        """Test handling of weekend data (when markets are closed)."""
        start_date = datetime(2024, 1, 6).date()  # A Saturday
        end_date = datetime(2024, 1, 7).date()  # A Sunday

        report = await validator.validate_consistency(
            symbol="000001.SZ",
            start_date=start_date,
            end_date=end_date,
            asset_type=AssetType.STOCK,
            market=MarketType.CN
        )

        # Expect no records for a weekend
        assert report.total_records == 0
        assert report.matching_records == 0
        assert report.consistency_percentage == 100.0
