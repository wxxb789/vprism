"""
Data Quality Assurance System Example.

This example demonstrates the complete data quality assurance system
including validation, cleaning, and consistency checking.
"""
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from vprism.core.quality import DataQualityValidator, DataQualityScorer, DataCleaner
from vprism.core.consistency import DataConsistencyValidator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_data():
    """Create sample financial data for demonstration."""
    dates = pd.date_range(start=datetime(2024, 1, 1), periods=10, freq='D')
    
    # Create realistic OHLCV data with some issues
    data = pd.DataFrame({
        'timestamp': dates,
        'symbol': ['AAPL'] * len(dates),
        'open': [100.0, 101.5, 102.3, 98.7, 99.2, 101.1, 102.8, 103.5, 104.2, 105.1],
        'high': [101.2, 102.8, 103.5, 100.1, 100.8, 102.5, 104.0, 104.8, 105.5, 106.2],
        'low': [99.5, 100.8, 101.2, 97.3, 98.1, 99.8, 101.5, 102.3, 103.1, 103.9],
        'close': [100.8, 102.1, 102.9, 99.4, 99.8, 101.9, 103.7, 104.2, 104.9, 105.8],
        'volume': [1000000, 1100000, 950000, 1200000, 1050000, 1150000, 1080000, 1250000, 1300000, 1350000]
    })
    
    # Introduce some data quality issues
    data.loc[2, 'close'] = np.nan  # Missing close price
    data.loc[5, 'high'] = 95.0     # Invalid: high < low
    data.loc[7, 'volume'] = -500000  # Negative volume
    data.loc[3, 'open'] = 150.0    # Outlier
    
    return data


def demonstrate_data_quality_validation():
    """Demonstrate data quality validation."""
    print("=" * 60)
    print("DATA QUALITY VALIDATION DEMONSTRATION")
    print("=" * 60)
    
    # Create sample data
    data = create_sample_data()
    print(f"Original data shape: {data.shape}")
    print("\nSample data:")
    print(data.head())
    
    # Initialize validator
    validator = DataQualityValidator()
    
    # Validate data
    issues = validator.validate_dataframe(data)
    print(f"\nValidation Issues Found: {len(issues)}")
    for issue in issues:
        print(f"  - {issue}")
    
    # Check for missing data
    missing_info = validator.detect_missing_data(data, expected_frequency='D')
    print(f"\nMissing Data Analysis:")
    print(f"  Missing records: {missing_info['missing_count']}")
    print(f"  Missing percentage: {missing_info['missing_percentage']:.2%}")
    
    # Detect outliers
    outliers = validator.detect_outliers(data)
    print(f"\nOutliers Detected: {len(outliers)}")
    if not outliers.empty:
        print(outliers[['timestamp', 'open', 'high', 'low', 'close', 'volume']])


def demonstrate_data_quality_scoring():
    """Demonstrate data quality scoring."""
    print("\n" + "=" * 60)
    print("DATA QUALITY SCORING DEMONSTRATION")
    print("=" * 60)
    
    # Create sample data
    data = create_sample_data()
    
    # Initialize scorer
    scorer = DataQualityScorer()
    
    # Calculate comprehensive score
    score = scorer.calculate_overall_score(data)
    
    print(f"Data Quality Score for AAPL:")
    print(f"  Overall Score: {score.overall:.2%}")
    print(f"  Quality Level: {score.level.value}")
    print(f"  Completeness: {score.completeness:.2%}")
    print(f"  Accuracy: {score.accuracy:.2%}")
    print(f"  Timeliness: {score.timeliness:.2%}")
    print(f"  Consistency: {score.consistency:.2%}")
    print(f"  Issues: {len(score.issues)}")


def demonstrate_data_cleaning():
    """Demonstrate data cleaning."""
    print("\n" + "=" * 60)
    print("DATA CLEANING DEMONSTRATION")
    print("=" * 60)
    
    # Create sample data
    data = create_sample_data()
    print(f"\nBefore cleaning:")
    print(f"  Records: {len(data)}")
    print(f"  Missing values: {data.isna().sum().sum()}")
    
    # Initialize cleaner
    cleaner = DataCleaner()
    
    # Clean the data
    cleaned = cleaner.clean_missing_values(data, method='interpolate')
    cleaned = cleaner.remove_outliers(cleaned)
    
    print(f"\nAfter cleaning:")
    print(f"  Records: {len(cleaned)}")
    print(f"  Missing values: {cleaned.isna().sum().sum()}")
    print(f"  Records removed: {len(data) - len(cleaned)}")


async def demonstrate_consistency_validation():
    """Demonstrate consistency validation with akshare."""
    print("\n" + "=" * 60)
    print("CONSISTENCY VALIDATION DEMONSTRATION")
    print("=" * 60)
    
    # Create validator
    validator = DataConsistencyValidator(tolerance=0.01)
    
    # Create sample data for demonstration
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 5)
    
    # Since we don't have real repository, we'll mock the data
    print("Note: This example uses mock data for demonstration.")
    print("In real usage, this would compare actual vprism data with akshare data.")
    
    # Create identical data to show perfect consistency
    identical_data = pd.DataFrame({
        'timestamp': pd.date_range(start=start_date, periods=5, freq='D'),
        'symbol': ['000001'] * 5,
        'open': [100.0, 101.0, 102.0, 103.0, 104.0],
        'high': [101.0, 102.0, 103.0, 104.0, 105.0],
        'low': [99.0, 100.0, 101.0, 102.0, 103.0],
        'close': [100.5, 101.5, 102.5, 103.5, 104.5],
        'volume': [1000000, 1100000, 1200000, 1300000, 1400000]
    })
    
    # Simulate consistency validation
    from unittest.mock import patch
    
    with patch.object(validator, '_get_vprism_data', return_value=identical_data):
        with patch.object(validator, '_get_akshare_data', return_value=identical_data):
            report = validator.validate_consistency("000001", start_date, end_date)
    
    print(f"\nConsistency Validation Results for 000001:")
    print(f"  Total Records: {report.total_records}")
    print(f"  Matching Records: {report.matching_records}")
    print(f"  Consistency Percentage: {report.consistency_percentage:.1f}%")
    print(f"  Average Price Difference: {report.average_price_difference:.2%}")
    print(f"  Max Price Difference: {report.max_price_difference:.2%}")


def run_complete_workflow():
    """Run a complete data quality workflow."""
    print("\n" + "=" * 60)
    print("COMPLETE DATA QUALITY WORKFLOW")
    print("=" * 60)
    
    # Step 1: Create sample data
    data = create_sample_data()
    print(f"Step 1: Created {len(data)} records of sample data")
    
    # Step 2: Validate data quality
    validator = DataQualityValidator()
    issues = validator.validate_dataframe(data)
    print(f"Step 2: Found {len(issues)} quality issues")
    
    # Step 3: Calculate quality score
    scorer = DataQualityScorer()
    score = scorer.calculate_overall_score(data)
    print(f"Step 3: Quality score: {score.overall:.2%} ({score.level.value})")
    
    # Step 4: Clean the data
    cleaner = DataCleaner()
    cleaned = cleaner.clean_missing_values(data, method='interpolate')
    cleaned = cleaner.remove_outliers(cleaned)
    print(f"Step 4: Cleaned data: {len(cleaned)} records (removed {len(data) - len(cleaned)})")
    
    # Step 5: Re-evaluate quality
    new_score = scorer.calculate_overall_score(cleaned)
    print(f"Step 5: New quality score: {new_score.overall:.2%} ({new_score.level.value})")
    
    print(f"\nQuality improvement: {new_score.overall - score.overall:.2%}")


if __name__ == "__main__":
    """Main demonstration function."""
    print("VPRISM DATA QUALITY ASSURANCE SYSTEM")
    print("====================================")
    
    # Run all demonstrations
    demonstrate_data_quality_validation()
    demonstrate_data_quality_scoring()
    demonstrate_data_cleaning()
    
    # Run consistency validation (will use mocked data)
    asyncio.run(demonstrate_consistency_validation())
    
    # Run complete workflow
    run_complete_workflow()
    
    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("The data quality assurance system is ready for production use!")