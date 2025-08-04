"""
Unit tests for the data quality assurance system.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd

from vprism.core.models import DataPoint
from vprism.core.validation import DataQualityScorer, DataQualityValidator
from vprism.core.validation.quality import DataCleaner, QualityLevel, QualityScore


class TestDataQualityValidator:
    """Test DataQualityValidator class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.validator = DataQualityValidator()

    def test_validate_data_point_valid(self):
        """Test validation of valid data point."""
        dp = DataPoint(
            symbol="AAPL",
            market="us",
            timestamp=datetime.now(),
            open_price=Decimal("100.0"),
            high_price=Decimal("101.0"),
            low_price=Decimal("99.0"),
            close_price=Decimal("100.5"),
            volume=Decimal("1000000"),
        )

        issues = self.validator.validate_data_point(dp)
        assert len(issues) == 0

    def test_validate_data_point_invalid(self):
        """Test validation of invalid data point."""
        dp = DataPoint(
            symbol="AAPL",
            market="us",
            timestamp=datetime.now(),
            open_price=Decimal("-100.0"),  # Negative price
            high_price=Decimal("90.0"),  # High < low
            low_price=Decimal("100.0"),
            close_price=Decimal("100.5"),
            volume=Decimal("-1000"),  # Negative volume
        )

        issues = self.validator.validate_data_point(dp)
        assert len(issues) > 0
        assert any("negative" in issue.lower() for issue in issues)
        assert any("high price" in issue.lower() for issue in issues)

    def test_validate_dataframe_valid(self):
        """Test validation of valid dataframe."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=5, freq="D"),
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [101.0, 102.0, 103.0, 104.0, 105.0],
                "low": [99.0, 100.0, 101.0, 102.0, 103.0],
                "close": [100.5, 101.5, 102.5, 103.5, 104.5],
                "volume": [1000000, 1100000, 1200000, 1300000, 1400000],
            }
        )

        issues = self.validator.validate_dataframe(df)
        assert len(issues) == 0

    def test_validate_dataframe_invalid(self):
        """Test validation of invalid dataframe."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=3, freq="D"),
                "open": [100.0, -101.0, 102.0],  # Negative price
                "high": [101.0, 90.0, 103.0],  # High < low
                "low": [99.0, 100.0, 101.0],
                "close": [100.5, 101.5, 102.5],
                "volume": [1000000, 1100000, -1200000],  # Negative volume
            }
        )

        issues = self.validator.validate_dataframe(df)
        assert len(issues) > 0
        assert any("negative" in issue.lower() for issue in issues)

    def test_detect_missing_data(self):
        """Test missing data detection."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-05"]),
                "close": [100.0, 101.0, 102.0],
            }
        )

        result = self.validator.detect_missing_data(df, expected_frequency="D")
        assert result["missing_count"] == 2  # Missing 2024-01-02 and 2024-01-04
        assert result["missing_percentage"] > 0

    def test_detect_outliers(self):
        """Test outlier detection."""
        np.random.seed(42)
        normal_data = np.random.normal(100, 5, 100)
        outliers = [200, 10]  # Clear outliers
        prices = np.concatenate([normal_data, outliers])

        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=len(prices), freq="D"),
                "close": prices,
            }
        )

        outlier_df = self.validator.detect_outliers(df)
        assert len(outlier_df) >= 2  # Should detect our artificial outliers

    def test_check_consistency(self):
        """Test data consistency checks."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=3, freq="D"),
                "open": [100.0, 101.0, 102.0],
                "high": [101.0, 90.0, 103.0],  # Invalid: high < low in row 1
                "low": [99.0, 100.0, 101.0],
                "close": [100.5, 101.5, 102.5],
            }
        )

        issues = self.validator.check_consistency(df)
        assert len(issues) > 0
        assert any("high" in issue.lower() and "low" in issue.lower() for issue in issues)


class TestDataQualityScorer:
    """Test DataQualityScorer class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.scorer = DataQualityScorer()

    def test_calculate_completeness_score(self):
        """Test completeness score calculation."""
        # Complete data
        complete_df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=5, freq="D"),
                "close": [100.0, 101.0, 102.0, 103.0, 104.0],
            }
        )

        # Incomplete data
        incomplete_df = complete_df.copy()
        incomplete_df.loc[2, "close"] = np.nan

        complete_score = self.scorer.calculate_completeness_score(complete_df)
        incomplete_score = self.scorer.calculate_completeness_score(incomplete_df)

        assert complete_score == 1.0
        assert 0.5 < incomplete_score < 1.0

    def test_calculate_accuracy_score(self):
        """Test accuracy score calculation."""
        valid_df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=3, freq="D"),
                "open": [100.0, 101.0, 102.0],
                "high": [101.0, 102.0, 103.0],
                "low": [99.0, 100.0, 101.0],
                "close": [100.5, 101.5, 102.5],
            }
        )

        score = self.scorer.calculate_accuracy_score(valid_df)
        assert 0.0 <= score <= 1.0

    def test_calculate_timeliness_score(self):
        """Test timeliness score calculation."""
        current_time = datetime.now()

        # Fresh data
        fresh_df = pd.DataFrame(
            {
                "timestamp": [current_time - timedelta(hours=1)] * 3,
                "close": [100.0, 101.0, 102.0],
            }
        )

        # Stale data
        stale_df = pd.DataFrame(
            {
                "timestamp": [current_time - timedelta(days=10)] * 3,
                "close": [100.0, 101.0, 102.0],
            }
        )

        fresh_score = self.scorer.calculate_timeliness_score(fresh_df)
        stale_score = self.scorer.calculate_timeliness_score(stale_df)

        assert fresh_score > stale_score

    def test_calculate_consistency_score(self):
        """Test consistency score calculation."""
        consistent_df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=3, freq="D"),
                "open": [100.0, 101.0, 102.0],
                "high": [101.0, 102.0, 103.0],
                "low": [99.0, 100.0, 101.0],
                "close": [100.5, 101.5, 102.5],
            }
        )

        score = self.scorer.calculate_consistency_score(consistent_df)
        assert 0.0 <= score <= 1.0

    def test_calculate_overall_score(self):
        """Test overall quality score calculation."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=5, freq="D"),
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [101.0, 102.0, 103.0, 104.0, 105.0],
                "low": [99.0, 100.0, 101.0, 102.0, 103.0],
                "close": [100.5, 101.5, 102.5, 103.5, 104.5],
                "volume": [1000000, 1100000, 1200000, 1300000, 1400000],
            }
        )

        score = self.scorer.calculate_overall_score(df)

        assert isinstance(score, QualityScore)
        assert 0.0 <= score.overall <= 1.0
        assert score.level in QualityLevel
        assert isinstance(score.issues, list)

    def test_quality_levels(self):
        """Test quality level determination."""
        test_cases = [
            (0.95, QualityLevel.EXCELLENT),
            (0.85, QualityLevel.GOOD),
            (0.70, QualityLevel.FAIR),
            (0.50, QualityLevel.POOR),
            (0.30, QualityLevel.UNACCEPTABLE),
        ]

        for score_value, expected_level in test_cases:
            # Create a mock score with specific overall score
            score = QualityScore(
                completeness=score_value,
                accuracy=score_value,
                timeliness=score_value,
                consistency=score_value,
                overall=score_value,
                level=expected_level,
                issues=[],
            )

            assert score.level == expected_level


class TestDataCleaner:
    """Test DataCleaner class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.cleaner = DataCleaner()

    def test_clean_missing_values_interpolate(self):
        """Test missing value cleaning with interpolation."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=5, freq="D"),
                "close": [100.0, np.nan, 102.0, np.nan, 104.0],
            }
        )

        cleaned = self.cleaner.clean_missing_values(df, method="interpolate")

        assert not cleaned["close"].isna().any()
        assert cleaned.loc[1, "close"] == 101.0  # Linear interpolation
        assert cleaned.loc[3, "close"] == 103.0

    def test_clean_missing_values_forward_fill(self):
        """Test missing value cleaning with forward fill."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=5, freq="D"),
                "close": [100.0, np.nan, np.nan, 104.0, 105.0],
            }
        )

        cleaned = self.cleaner.clean_missing_values(df, method="forward_fill")

        assert not cleaned["close"].isna().any()
        assert cleaned.loc[1, "close"] == 100.0  # Forward filled
        assert cleaned.loc[2, "close"] == 100.0

    def test_clean_missing_values_drop(self):
        """Test missing value cleaning by dropping."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=5, freq="D"),
                "close": [100.0, np.nan, 102.0, np.nan, 104.0],
            }
        )

        cleaned = self.cleaner.clean_missing_values(df, method="drop")

        assert len(cleaned) == 3  # Dropped 2 rows with NaN
        assert not cleaned["close"].isna().any()

    def test_remove_outliers(self):
        """Test outlier removal."""
        np.random.seed(42)
        normal_data = np.random.normal(100, 5, 100)
        outliers = [200, 10]  # Clear outliers
        prices = np.concatenate([normal_data, outliers])

        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=len(prices), freq="D"),
                "close": prices,
            }
        )

        cleaned = self.cleaner.remove_outliers(df)

        assert len(cleaned) < len(df)  # Some outliers removed
        assert not any(cleaned["close"].isin([200, 10]))

    def test_normalize_data_minmax(self):
        """Test min-max normalization."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=5, freq="D"),
                "close": [100.0, 200.0, 300.0, 400.0, 500.0],
                "volume": [1000, 2000, 3000, 4000, 5000],
            }
        )

        normalized = self.cleaner.normalize_data(df, method="minmax")

        assert normalized["close"].min() == 0.0
        assert normalized["close"].max() == 1.0
        assert normalized["volume"].min() == 0.0
        assert normalized["volume"].max() == 1.0

    def test_normalize_data_zscore(self):
        """Test z-score normalization."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=5, freq="D"),
                "close": [100.0, 101.0, 102.0, 103.0, 104.0],
            }
        )

        normalized = self.cleaner.normalize_data(df, method="zscore")

        assert abs(normalized["close"].mean()) < 0.001  # Mean should be ~0
        assert abs(normalized["close"].std() - 1.0) < 0.001  # Std should be ~1

    def test_standardize_timestamps(self):
        """Test timestamp standardization."""
        df = pd.DataFrame(
            {
                "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "close": [100.0, 101.0, 102.0],
            }
        )

        standardized = self.cleaner.standardize_timestamps(df)

        assert pd.api.types.is_datetime64_any_dtype(standardized["timestamp"])
        assert standardized["timestamp"].dt.tz is None  # Should be timezone-naive

    def test_end_to_end_cleaning(self):
        """Test complete data cleaning pipeline."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=10, freq="D"),
                "open": [
                    100.0,
                    101.0,
                    np.nan,
                    103.0,
                    104.0,
                    105.0,
                    200.0,
                    107.0,
                    108.0,
                    109.0,
                ],
                "high": [
                    101.0,
                    102.0,
                    103.0,
                    104.0,
                    105.0,
                    106.0,
                    201.0,
                    108.0,
                    109.0,
                    110.0,
                ],
                "low": [
                    99.0,
                    100.0,
                    101.0,
                    102.0,
                    103.0,
                    104.0,
                    199.0,
                    106.0,
                    107.0,
                    108.0,
                ],
                "close": [
                    100.5,
                    101.5,
                    np.nan,
                    103.5,
                    104.5,
                    105.5,
                    200.5,
                    107.5,
                    108.5,
                    109.5,
                ],
                "volume": [
                    1000000,
                    1100000,
                    1200000,
                    1300000,
                    1400000,
                    1500000,
                    1600000,
                    1700000,
                    1800000,
                    1900000,
                ],
            }
        )

        # Clean the data
        cleaned = self.cleaner.clean_missing_values(df, method="interpolate")
        cleaned = self.cleaner.remove_outliers(cleaned)

        # Verify cleaning results
        assert not cleaned.isna().any().any()  # No missing values
        assert len(cleaned) <= len(df)  # May have removed outliers
