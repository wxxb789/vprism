"""
Data Quality Assurance System Example.

This example demonstrates the complete data quality assurance system
including validation, cleaning, and consistency checking.
"""

import asyncio
import logging
from datetime import datetime

import numpy as np
import pandas as pd

from vprism.core.validation.consistency import DataConsistencyValidator
from vprism.core.validation.quality import DataCleaner, DataQualityScorer, DataQualityValidator

# Configure logging
logging.basicConfig(level=logging.INFO)
vprism_logger = logging.getLogger(__name__)


def vprism_create_sample_data():
    """Create sample financial data for demonstration."""
    vprism_dates = pd.date_range(start=datetime(2024, 1, 1), periods=10, freq="D")

    # Create realistic OHLCV data with some issues
    vprism_data = pd.DataFrame(
        {
            "timestamp": vprism_dates,
            "symbol": ["AAPL"] * len(vprism_dates),
            "open": [
                100.0,
                101.5,
                102.3,
                98.7,
                99.2,
                101.1,
                102.8,
                103.5,
                104.2,
                105.1,
            ],
            "high": [
                101.2,
                102.8,
                103.5,
                100.1,
                100.8,
                102.5,
                104.0,
                104.8,
                105.5,
                106.2,
            ],
            "low": [99.5, 100.8, 101.2, 97.3, 98.1, 99.8, 101.5, 102.3, 103.1, 103.9],
            "close": [
                100.8,
                102.1,
                102.9,
                99.4,
                99.8,
                101.9,
                103.7,
                104.2,
                104.9,
                105.8,
            ],
            "volume": [
                1000000,
                1100000,
                950000,
                1200000,
                1050000,
                1150000,
                1080000,
                1250000,
                1300000,
                1350000,
            ],
        }
    )

    # Introduce some data quality issues
    vprism_data.loc[2, "close"] = np.nan  # Missing close price
    vprism_data.loc[5, "high"] = 95.0  # Invalid: high < low
    vprism_data.loc[7, "volume"] = -500000  # Negative volume
    vprism_data.loc[3, "open"] = 150.0  # Outlier

    return vprism_data


def vprism_demonstrate_data_quality_validation():
    """Demonstrate data quality validation."""
    print("=" * 60)
    print("DATA QUALITY VALIDATION DEMONSTRATION")
    print("=" * 60)

    # Create sample data
    vprism_data = vprism_create_sample_data()
    print(f"Original data shape: {vprism_data.shape}")
    print("\nSample data:")
    print(vprism_data.head())

    # Initialize validator
    vprism_validator = DataQualityValidator()

    # Validate data
    vprism_issues = vprism_validator.validate_dataframe(vprism_data)
    print(f"\nValidation Issues Found: {len(vprism_issues)}")
    for vprism_issue in vprism_issues:
        print(f"  - {vprism_issue}")

    # Check for missing data
    vprism_missing_info = vprism_validator.detect_missing_data(vprism_data, expected_frequency="D")
    print("\nMissing Data Analysis:")
    print(f"  Missing records: {vprism_missing_info['missing_count']}")
    print(f"  Missing percentage: {vprism_missing_info['missing_percentage']:.2%}")

    # Detect outliers
    vprism_outliers = vprism_validator.detect_outliers(vprism_data)
    print(f"\nOutliers Detected: {len(vprism_outliers)}")
    if not vprism_outliers.empty:
        print(vprism_outliers[["timestamp", "open", "high", "low", "close", "volume"]])


def vprism_demonstrate_data_quality_scoring():
    """Demonstrate data quality scoring."""
    print("\n" + "=" * 60)
    print("DATA QUALITY SCORING DEMONSTRATION")
    print("=" * 60)

    # Create sample data
    vprism_data = vprism_create_sample_data()

    # Initialize scorer
    vprism_scorer = DataQualityScorer()

    # Calculate comprehensive score
    vprism_score = vprism_scorer.calculate_overall_score(vprism_data)

    print("Data Quality Score for AAPL:")
    print(f"  Overall Score: {vprism_score.overall:.2%}")
    print(f"  Quality Level: {vprism_score.level.value}")
    print(f"  Completeness: {vprism_score.completeness:.2%}")
    print(f"  Accuracy: {vprism_score.accuracy:.2%}")
    print(f"  Timeliness: {vprism_score.timeliness:.2%}")
    print(f"  Consistency: {vprism_score.consistency:.2%}")
    print(f"  Issues: {len(vprism_score.issues)}")


def vprism_demonstrate_data_cleaning():
    """Demonstrate data cleaning."""
    print("\n" + "=" * 60)
    print("DATA CLEANING DEMONSTRATION")
    print("=" * 60)

    # Create sample data
    vprism_data = vprism_create_sample_data()
    print("\nBefore cleaning:")
    print(f"  Records: {len(vprism_data)}")
    print(f"  Missing values: {vprism_data.isna().sum().sum()}")

    # Initialize cleaner
    vprism_cleaner = DataCleaner()

    # Clean the data
    vprism_cleaned = vprism_cleaner.clean_missing_values(vprism_data, method="interpolate")
    vprism_cleaned = vprism_cleaner.remove_outliers(vprism_cleaned)

    print("\nAfter cleaning:")
    print(f"  Records: {len(vprism_cleaned)}")
    print(f"  Missing values: {vprism_cleaned.isna().sum().sum()}")
    print(f"  Records removed: {len(vprism_data) - len(vprism_cleaned)}")


async def vprism_demonstrate_consistency_validation():
    """Demonstrate consistency validation with akshare."""
    print("\n" + "=" * 60)
    print("CONSISTENCY VALIDATION DEMONSTRATION")
    print("=" * 60)

    # Create validator
    vprism_validator = DataConsistencyValidator(tolerance=0.01)

    # Create sample data for demonstration
    vprism_start_date = datetime(2024, 1, 1)
    vprism_end_date = datetime(2024, 1, 5)

    # Since we don't have real repository, we'll mock the data
    print("Note: This example uses mock data for demonstration.")
    print("In real usage, this would compare actual vprism data with akshare data.")

    # Create identical data to show perfect consistency
    vprism_identical_data = pd.DataFrame(
        {
            "timestamp": pd.date_range(start=vprism_start_date, periods=5, freq="D"),
            "symbol": ["000001"] * 5,
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [101.0, 102.0, 103.0, 104.0, 105.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "volume": [1000000, 1100000, 1200000, 1300000, 1400000],
        }
    )

    # Simulate consistency validation
    from unittest.mock import patch

    with (
        patch.object(vprism_validator, "_get_vprism_data", return_value=vprism_identical_data),
        patch.object(vprism_validator, "_get_akshare_data", return_value=vprism_identical_data),
    ):
        vprism_report = vprism_validator.validate_consistency("000001", vprism_start_date, vprism_end_date)

    print("\nConsistency Validation Results for 000001:")
    print(f"  Total Records: {vprism_report.total_records}")
    print(f"  Matching Records: {vprism_report.matching_records}")
    print(f"  Consistency Percentage: {vprism_report.consistency_percentage:.1f}%")
    print(f"  Average Price Difference: {vprism_report.average_price_difference:.2%}")
    print(f"  Max Price Difference: {vprism_report.max_price_difference:.2%}")


def vprism_run_complete_workflow():
    """Run a complete data quality workflow."""
    print("\n" + "=" * 60)
    print("COMPLETE DATA QUALITY WORKFLOW")
    print("=" * 60)

    # Step 1: Create sample data
    vprism_data = vprism_create_sample_data()
    print(f"Step 1: Created {len(vprism_data)} records of sample data")

    # Step 2: Validate data quality
    vprism_validator = DataQualityValidator()
    vprism_issues = vprism_validator.validate_dataframe(vprism_data)
    print(f"Step 2: Found {len(vprism_issues)} quality issues")

    # Step 3: Calculate quality score
    vprism_scorer = DataQualityScorer()
    vprism_score = vprism_scorer.calculate_overall_score(vprism_data)
    print(f"Step 3: Quality score: {vprism_score.overall:.2%} ({vprism_score.level.value})")

    # Step 4: Clean the data
    vprism_cleaner = DataCleaner()
    vprism_cleaned = vprism_cleaner.clean_missing_values(vprism_data, method="interpolate")
    vprism_cleaned = vprism_cleaner.remove_outliers(vprism_cleaned)
    print(f"Step 4: Cleaned data: {len(vprism_cleaned)} records (removed {len(vprism_data) - len(vprism_cleaned)})")

    # Step 5: Re-evaluate quality
    vprism_new_score = vprism_scorer.calculate_overall_score(vprism_cleaned)
    print(f"Step 5: New quality score: {vprism_new_score.overall:.2%} ({vprism_new_score.level.value})")

    print(f"\nQuality improvement: {vprism_new_score.overall - vprism_score.overall:.2%}")


if __name__ == "__main__":
    """Main demonstration function."""
    print("vprism Data Quality Assurance System")
    print("====================================")

    # Run all demonstrations
    vprism_demonstrate_data_quality_validation()
    vprism_demonstrate_data_quality_scoring()
    vprism_demonstrate_data_cleaning()

    # Run consistency validation (will use mocked data)
    asyncio.run(vprism_demonstrate_consistency_validation())

    # Run complete workflow
    vprism_run_complete_workflow()

    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("The data quality assurance system is ready for production use!")
