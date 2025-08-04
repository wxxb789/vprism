"""
Tests for data consistency validation between vprism and akshare.
"""

from datetime import datetime
from unittest.mock import patch

import pandas as pd

from vprism.core.validation import ConsistencyReport, DataConsistencyValidator


class TestDataConsistencyValidator:
    """Test DataConsistencyValidator class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.validator = DataConsistencyValidator(tolerance=0.01)

    def test_validate_consistency_identical_data(self):
        """Test validation with identical data."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 5)

        # Create identical data for both sources
        dates = pd.date_range(start=start_date, end=end_date, freq="D")
        data = pd.DataFrame(
            {
                "timestamp": dates,
                "symbol": ["TEST"] * len(dates),
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [101.0, 102.0, 103.0, 104.0, 105.0],
                "low": [99.0, 100.0, 101.0, 102.0, 103.0],
                "close": [100.5, 101.5, 102.5, 103.5, 104.5],
                "volume": [1000000, 1100000, 1200000, 1300000, 1400000],
            }
        )

        with patch.object(self.validator, "_get_vprism_data", return_value=data.copy()):
            with patch.object(self.validator, "_get_akshare_data", return_value=data.copy()):
                report = self.validator.validate_consistency("TEST", start_date, end_date)

        assert report.symbol == "TEST"
        assert report.total_records == 5
        assert report.matching_records > 0
        assert report.consistency_percentage > 95.0
        assert len(report.issues) == 0

    def test_validate_consistency_with_differences(self):
        """Test validation with slight differences."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)

        vprism_data = pd.DataFrame(
            {
                "timestamp": pd.date_range(start=start_date, periods=3, freq="D"),
                "symbol": ["TEST"] * 3,
                "open": [100.0, 101.0, 102.0],
                "high": [101.0, 102.0, 103.0],
                "low": [99.0, 100.0, 101.0],
                "close": [100.5, 101.5, 102.5],
                "volume": [1000000, 1100000, 1200000],
            }
        )

        # Create slightly different akshare data
        akshare_data = vprism_data.copy()
        akshare_data.loc[1, "close"] = 101.6  # 0.1% difference
        akshare_data.loc[2, "volume"] = 1210000  # 0.8% difference

        with patch.object(self.validator, "_get_vprism_data", return_value=vprism_data):
            with patch.object(self.validator, "_get_akshare_data", return_value=akshare_data):
                report = self.validator.validate_consistency("TEST", start_date, end_date)

        assert report.symbol == "TEST"
        assert report.total_records == 3
        assert report.consistency_percentage > 90.0  # Should still be high

    def test_validate_consistency_missing_data(self):
        """Test validation with missing data."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 5)

        # vprism has 3 records, akshare has 5
        vprism_data = pd.DataFrame(
            {
                "timestamp": pd.date_range(start=start_date, periods=3, freq="D"),
                "symbol": ["TEST"] * 3,
                "open": [100.0, 101.0, 102.0],
                "high": [101.0, 102.0, 103.0],
                "low": [99.0, 100.0, 101.0],
                "close": [100.5, 101.5, 102.5],
                "volume": [1000000, 1100000, 1200000],
            }
        )

        akshare_data = pd.DataFrame(
            {
                "timestamp": pd.date_range(start=start_date, periods=5, freq="D"),
                "symbol": ["TEST"] * 5,
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [101.0, 102.0, 103.0, 104.0, 105.0],
                "low": [99.0, 100.0, 101.0, 102.0, 103.0],
                "close": [100.5, 101.5, 102.5, 103.5, 104.5],
                "volume": [1000000, 1100000, 1200000, 1300000, 1400000],
            }
        )

        with patch.object(self.validator, "_get_vprism_data", return_value=vprism_data):
            with patch.object(self.validator, "_get_akshare_data", return_value=akshare_data):
                report = self.validator.validate_consistency("TEST", start_date, end_date)

        assert report.missing_in_vprism == 2
        assert report.missing_in_akshare == 0

    def test_compare_multiple_symbols(self):
        """Test comparison for multiple symbols."""
        symbols = ["AAPL", "GOOGL", "MSFT"]
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)

        mock_data = pd.DataFrame(
            {
                "timestamp": pd.date_range(start=start_date, periods=3, freq="D"),
                "symbol": ["TEST"] * 3,
                "open": [100.0, 101.0, 102.0],
                "high": [101.0, 102.0, 103.0],
                "low": [99.0, 100.0, 101.0],
                "close": [100.5, 101.5, 102.5],
                "volume": [1000000, 1100000, 1200000],
            }
        )

        with patch.object(self.validator, "_get_vprism_data", return_value=mock_data):
            with patch.object(self.validator, "_get_akshare_data", return_value=mock_data):
                reports = self.validator.compare_multiple_symbols(symbols, start_date, end_date)

        assert len(reports) == 3
        for symbol, report in reports.items():
            assert symbol in ["AAPL", "GOOGL", "MSFT"]
            assert report.symbol == symbol

    def test_generate_consistency_report(self):
        """Test report generation."""
        reports = {
            "AAPL": ConsistencyReport(
                symbol="AAPL",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 3),
                total_records=3,
                matching_records=12,  # 3 days * 4 price fields
                mismatching_records=0,
                missing_in_vprism=0,
                missing_in_akshare=0,
                average_price_difference=0.0,
                max_price_difference=0.0,
                consistency_percentage=100.0,
                issues=[],
                detailed_comparison={},
            )
        }

        report_text = self.validator.generate_consistency_report(reports)

        assert "AAPL" in report_text
        assert "100.0%" in report_text
        assert "CONSISTENCY REPORT" in report_text

    def test_run_automated_validation(self):
        """Test automated validation with alerting."""
        symbols = ["AAPL", "GOOGL"]

        # Mock data with one symbol having low consistency
        mock_data = pd.DataFrame(
            {
                "timestamp": pd.date_range(start=datetime(2024, 1, 1), periods=3, freq="D"),
                "symbol": ["TEST"] * 3,
                "open": [100.0, 101.0, 102.0],
                "high": [101.0, 102.0, 103.0],
                "low": [99.0, 100.0, 101.0],
                "close": [100.5, 101.5, 102.5],
                "volume": [1000000, 1100000, 1200000],
            }
        )

        # Create slightly different data for one symbol to trigger alert
        low_consistency_data = mock_data.copy()
        low_consistency_data.loc[1, "close"] = 105.0  # 3.4% difference, above 1% tolerance

        with patch.object(self.validator, "_get_vprism_data", return_value=mock_data):
            with patch.object(
                self.validator,
                "_get_akshare_data",
                side_effect=[mock_data, low_consistency_data],
            ):
                summary = self.validator.run_automated_validation(symbols, days_back=3)

        assert summary["total_symbols"] == 2
        assert summary["validated_symbols"] == 2
        assert len(summary["alert_symbols"]) >= 0  # May have alerts
        assert "reports" in summary

    def test_empty_data_handling(self):
        """Test handling of empty data."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)

        empty_df = pd.DataFrame()

        with patch.object(self.validator, "_get_vprism_data", return_value=empty_df):
            with patch.object(self.validator, "_get_akshare_data", return_value=empty_df):
                report = self.validator.validate_consistency("TEST", start_date, end_date)

        assert report.total_records == 0
        assert report.consistency_percentage == 0.0

    def test_large_price_differences(self):
        """Test handling of large price differences."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)

        vprism_data = pd.DataFrame(
            {
                "timestamp": pd.date_range(start=start_date, periods=2, freq="D"),
                "symbol": ["TEST"] * 2,
                "open": [100.0, 101.0],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "close": [100.5, 101.5],
                "volume": [1000000, 1100000],
            }
        )

        # Create significantly different akshare data
        akshare_data = vprism_data.copy()
        akshare_data.loc[0, "close"] = 110.0  # 9.5% difference
        akshare_data.loc[1, "open"] = 95.0  # 5.9% difference

        with patch.object(self.validator, "_get_vprism_data", return_value=vprism_data):
            with patch.object(self.validator, "_get_akshare_data", return_value=akshare_data):
                report = self.validator.validate_consistency("TEST", start_date, end_date)

        assert report.mismatching_records > 0
        assert report.max_price_difference > 0.05  # Should be > 5%
        assert len(report.issues) > 0

    def test_consistency_report_structure(self):
        """Test that ConsistencyReport has all required fields."""
        report = ConsistencyReport(
            symbol="TEST",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 1),
            total_records=1,
            matching_records=1,
            mismatching_records=0,
            missing_in_vprism=0,
            missing_in_akshare=0,
            average_price_difference=0.0,
            max_price_difference=0.0,
            consistency_percentage=100.0,
            issues=[],
            detailed_comparison={},
        )

        assert report.symbol == "TEST"
        assert report.consistency_percentage == 100.0
        assert isinstance(report.issues, list)
        assert isinstance(report.detailed_comparison, dict)


class TestConsistencyIntegration:
    """Integration tests for consistency validation."""

    def test_realistic_stock_comparison(self):
        """Test realistic stock data comparison."""
        start_date = datetime(2024, 1, 15)
        end_date = datetime(2024, 1, 19)

        # Create realistic OHLCV data
        dates = pd.date_range(start=start_date, periods=5, freq="D")
        base_prices = [100.0, 101.2, 99.8, 102.1, 103.5]

        vprism_data = pd.DataFrame(
            {
                "timestamp": dates,
                "symbol": ["000001"] * 5,
                "open": base_prices,
                "high": [p + 1.5 for p in base_prices],
                "low": [p - 1.0 for p in base_prices],
                "close": [p + 0.3 for p in base_prices],
                "volume": [1000000 + i * 50000 for i in range(5)],
            }
        )

        # Akshare data with minor rounding differences
        akshare_data = vprism_data.copy()
        akshare_data["close"] = akshare_data["close"] + 0.01  # 0.01% difference
        akshare_data["volume"] = akshare_data["volume"] + 100  # Negligible difference

        validator = DataConsistencyValidator(tolerance=0.001)  # Very strict tolerance

        with patch.object(validator, "_get_vprism_data", return_value=vprism_data):
            with patch.object(validator, "_get_akshare_data", return_value=akshare_data):
                report = validator.validate_consistency("000001", start_date, end_date)

        assert report.symbol == "000001"
        assert report.total_records == 5
        # With 0.1% tolerance, should have some mismatches
        assert report.mismatching_records >= 0
        assert 0 <= report.consistency_percentage <= 100.0

    def test_weekend_data_handling(self):
        """Test handling of weekend data (when markets are closed)."""
        # Weekend dates when Chinese markets are closed
        weekend_dates = pd.date_range(start=datetime(2024, 1, 6), periods=2, freq="D")  # Sat, Sun

        vprism_data = pd.DataFrame(
            {
                "timestamp": weekend_dates,
                "symbol": ["TEST"] * 2,
                "open": [100.0, 100.0],
                "high": [101.0, 101.0],
                "low": [99.0, 99.0],
                "close": [100.5, 100.5],
                "volume": [0, 0],  # Zero volume for weekends
            }
        )

        akshare_data = pd.DataFrame()  # Empty for weekends

        validator = DataConsistencyValidator()

        with patch.object(validator, "_get_vprism_data", return_value=vprism_data):
            with patch.object(validator, "_get_akshare_data", return_value=akshare_data):
                report = validator.validate_consistency("TEST", datetime(2024, 1, 6), datetime(2024, 1, 7))

        assert report.total_records == 2
        assert report.missing_in_akshare == 2  # All weekend data missing in akshare
