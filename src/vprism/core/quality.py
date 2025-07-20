"""
Data quality assurance system for vprism financial data platform.

This module provides comprehensive data validation, cleaning, and quality scoring
capabilities to ensure high-quality financial data.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

from vprism.core.models import DataPoint
from vprism.core.exceptions import VPrismError


class QualityLevel(Enum):
    """Data quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNACCEPTABLE = "unacceptable"


@dataclass
class QualityScore:
    """Data quality score with detailed metrics."""
    completeness: float  # 0-1 score for missing data
    accuracy: float      # 0-1 score for data validity
    timeliness: float    # 0-1 score for data freshness
    consistency: float   # 0-1 score for data relationships
    overall: float       # 0-1 composite score
    level: QualityLevel  # Overall quality level
    issues: List[str]    # List of identified issues


class DataQualityValidator:
    """Validates financial data quality and identifies issues."""
    
    def __init__(self, 
                 completeness_threshold: float = 0.95,
                 accuracy_threshold: float = 0.90,
                 timeliness_threshold: float = 0.80,
                 consistency_threshold: float = 0.95):
        self.completeness_threshold = completeness_threshold
        self.accuracy_threshold = accuracy_threshold
        self.timeliness_threshold = timeliness_threshold
        self.consistency_threshold = consistency_threshold
        self.logger = logging.getLogger(__name__)
    
    def validate_data_point(self, data_point: DataPoint) -> List[str]:
        """Validate a single data point and return list of issues."""
        issues = []
        
        # Price validation
        if data_point.open is not None and data_point.open <= 0:
            issues.append("Open price must be positive")
            
        if data_point.high is not None and data_point.high <= 0:
            issues.append("High price must be positive")
            
        if data_point.low is not None and data_point.low <= 0:
            issues.append("Low price must be positive")
            
        if data_point.close is not None and data_point.close <= 0:
            issues.append("Close price must be positive")
            
        # OHLCV relationships
        if (data_point.high is not None and data_point.low is not None and 
            data_point.high < data_point.low):
            issues.append("High price must be >= low price")
            
        if (data_point.high is not None and data_point.open is not None and 
            data_point.close is not None):
            if data_point.high < max(data_point.open, data_point.close):
                issues.append("High price must be >= max(open, close)")
                
        if (data_point.low is not None and data_point.open is not None and 
            data_point.close is not None):
            if data_point.low > min(data_point.open, data_point.close):
                issues.append("Low price must be <= min(open, close)")
                
        # Volume validation
        if data_point.volume is not None and data_point.volume < 0:
            issues.append("Volume must be non-negative")
            
        return issues
    
    def validate_dataframe(self, df: pd.DataFrame) -> List[str]:
        """Validate a pandas DataFrame and return list of issues."""
        issues = []
        
        if df.empty:
            issues.append("DataFrame is empty")
            return issues
            
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            issues.append(f"Missing required columns: {missing_columns}")
            
        # Check for negative prices
        price_columns = ['open', 'high', 'low', 'close']
        for col in price_columns:
            if col in df.columns and (df[col] < 0).any():
                issues.append(f"Negative values found in {col}")
                
        # Check for negative volume
        if 'volume' in df.columns and (df['volume'] < 0).any():
            issues.append("Negative values found in volume")
            
        # Check OHLC relationships
        if all(col in df.columns for col in ['high', 'low']):
            invalid_ohlc = df['high'] < df['low']
            if invalid_ohlc.any():
                issues.append("High price < low price in some rows")
                
        return issues
    
    def detect_missing_data(self, df: pd.DataFrame, 
                           expected_frequency: str = 'D') -> Dict[str, Any]:
        """Detect missing data points based on expected frequency."""
        if df.empty or 'timestamp' not in df.columns:
            return {'missing_count': 0, 'missing_percentage': 0.0, 'gaps': []}
            
        df = df.sort_values('timestamp')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Create expected date range
        start_date = df['timestamp'].min()
        end_date = df['timestamp'].max()
        expected_range = pd.date_range(start=start_date, end=end_date, freq=expected_frequency)
        
        # Find missing dates
        actual_dates = set(df['timestamp'].dt.date)
        expected_dates = set(expected_range.date)
        missing_dates = expected_dates - actual_dates
        
        missing_count = len(missing_dates)
        total_expected = len(expected_range)
        missing_percentage = missing_count / total_expected if total_expected > 0 else 0.0
        
        return {
            'missing_count': missing_count,
            'missing_percentage': missing_percentage,
            'gaps': sorted(list(missing_dates))
        }
    
    def detect_outliers(self, df: pd.DataFrame, 
                       method: str = 'iqr',
                       threshold: float = 1.5) -> pd.DataFrame:
        """Detect outliers in price and volume data."""
        if df.empty:
            return pd.DataFrame()
            
        outlier_mask = pd.Series([False] * len(df))
        
        # Detect price outliers
        price_columns = ['open', 'high', 'low', 'close']
        for col in price_columns:
            if col in df.columns:
                col_series = pd.to_numeric(df[col], errors='coerce')
                
                if method == 'iqr':
                    Q1 = col_series.quantile(0.25)
                    Q3 = col_series.quantile(0.75)
                    IQR = Q3 - Q1
                    lower_bound = Q1 - threshold * IQR
                    upper_bound = Q3 + threshold * IQR
                    
                    col_outliers = (col_series < lower_bound) | (col_series > upper_bound)
                    outlier_mask |= col_outliers
                    
                elif method == 'zscore':
                    mean = col_series.mean()
                    std = col_series.std()
                    if std > 0:
                        z_scores = abs((col_series - mean) / std)
                        col_outliers = z_scores > threshold
                        outlier_mask |= col_outliers
        
        # Detect volume outliers
        if 'volume' in df.columns:
            volume_series = pd.to_numeric(df['volume'], errors='coerce')
            
            if method == 'iqr':
                Q1 = volume_series.quantile(0.25)
                Q3 = volume_series.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - threshold * IQR
                upper_bound = Q3 + threshold * IQR
                
                volume_outliers = (volume_series < lower_bound) | (volume_series > upper_bound)
                outlier_mask |= volume_outliers
        
        return df[outlier_mask]
    
    def check_consistency(self, df: pd.DataFrame) -> List[str]:
        """Check data consistency across related fields."""
        issues = []
        
        if df.empty:
            return issues
            
        # OHLC consistency
        if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
            for idx, row in df.iterrows():
                try:
                    high = float(row['high'])
                    low = float(row['low'])
                    open_p = float(row['open'])
                    close = float(row['close'])
                    
                    if high < low:
                        issues.append(f"Row {idx}: High (>{high}) < Low (>{low})")
                        
                    if high < max(open_p, close):
                        issues.append(f"Row {idx}: High (>{high}) < max(Open=>{open_p}, Close=>{close})")
                        
                    if low > min(open_p, close):
                        issues.append(f"Row {idx}: Low (>{low}) > min(Open=>{open_p}, Close=>{close})")
                        
                except (ValueError, TypeError):
                    issues.append(f"Row {idx}: Invalid numeric values")
        
        return issues


class DataQualityScorer:
    """Calculates comprehensive data quality scores."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_completeness_score(self, df: pd.DataFrame) -> float:
        """Calculate completeness score based on missing data."""
        if df.empty:
            return 0.0
            
        total_cells = df.size
        missing_cells = df.isna().sum().sum()
        
        return max(0.0, 1.0 - (missing_cells / total_cells))
    
    def calculate_accuracy_score(self, df: pd.DataFrame) -> float:
        """Calculate accuracy score based on data validity."""
        if df.empty:
            return 0.0
            
        validator = DataQualityValidator()
        issues = validator.validate_dataframe(df)
        
        # Simple scoring: fewer issues = higher score
        # More sophisticated scoring can be implemented
        max_expected_issues = max(1, len(df) * 0.1)  # Allow 10% issues
        accuracy = max(0.0, 1.0 - (len(issues) / max_expected_issues))
        
        return min(1.0, accuracy)
    
    def calculate_timeliness_score(self, df: pd.DataFrame, 
                                 current_time: Optional[datetime] = None) -> float:
        """Calculate timeliness score based on data freshness."""
        if df.empty or 'timestamp' not in df.columns:
            return 0.0
            
        if current_time is None:
            current_time = datetime.now()
            
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        max_age = timedelta(days=7)  # Consider data >7 days old as stale
        
        ages = [(current_time - ts).total_seconds() for ts in df['timestamp']]
        max_age_seconds = max_age.total_seconds()
        
        scores = [max(0.0, 1.0 - (age / max_age_seconds)) for age in ages]
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def calculate_consistency_score(self, df: pd.DataFrame) -> float:
        """Calculate consistency score based on data relationships."""
        if df.empty:
            return 0.0
            
        validator = DataQualityValidator()
        consistency_issues = validator.check_consistency(df)
        
        # Simple scoring based on consistency issues
        max_expected_issues = max(1, len(df) * 0.05)  # Allow 5% issues
        consistency = max(0.0, 1.0 - (len(consistency_issues) / max_expected_issues))
        
        return min(1.0, consistency)
    
    def calculate_overall_score(self, df: pd.DataFrame,
                              current_time: Optional[datetime] = None) -> QualityScore:
        """Calculate comprehensive data quality score."""
        validator = DataQualityValidator()
        
        completeness = self.calculate_completeness_score(df)
        accuracy = self.calculate_accuracy_score(df)
        timeliness = self.calculate_timeliness_score(df, current_time)
        consistency = self.calculate_consistency_score(df)
        
        # Weighted average for overall score
        weights = {'completeness': 0.25, 'accuracy': 0.30, 
                  'timeliness': 0.20, 'consistency': 0.25}
        
        overall = (
            completeness * weights['completeness'] +
            accuracy * weights['accuracy'] +
            timeliness * weights['timeliness'] +
            consistency * weights['consistency']
        )
        
        # Collect all issues
        issues = validator.validate_dataframe(df)
        issues.extend(validator.check_consistency(df))
        
        # Determine quality level
        if overall >= 0.90:
            level = QualityLevel.EXCELLENT
        elif overall >= 0.75:
            level = QualityLevel.GOOD
        elif overall >= 0.60:
            level = QualityLevel.FAIR
        elif overall >= 0.40:
            level = QualityLevel.POOR
        else:
            level = QualityLevel.UNACCEPTABLE
        
        return QualityScore(
            completeness=completeness,
            accuracy=accuracy,
            timeliness=timeliness,
            consistency=consistency,
            overall=overall,
            level=level,
            issues=issues
        )


class DataCleaner:
    """Cleans and normalizes financial data."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def clean_missing_values(self, df: pd.DataFrame, 
                           method: str = 'interpolate') -> pd.DataFrame:
        """Clean missing values using specified method."""
        df_cleaned = df.copy()
        
        if method == 'interpolate':
            # Linear interpolation for numeric columns
            numeric_cols = df_cleaned.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                df_cleaned[col] = df_cleaned[col].interpolate(method='linear')
                # Fill any remaining NaN with forward fill
                df_cleaned[col] = df_cleaned[col].ffill()
                
        elif method == 'forward_fill':
            df_cleaned = df_cleaned.ffill()
            
        elif method == 'drop':
            df_cleaned = df_cleaned.dropna()
            
        return df_cleaned
    
    def remove_outliers(self, df: pd.DataFrame, 
                       method: str = 'iqr',
                       threshold: float = 1.5) -> pd.DataFrame:
        """Remove outliers from the dataset."""
        validator = DataQualityValidator()
        outlier_df = validator.detect_outliers(df, method, threshold)
        
        if outlier_df.empty:
            return df
            
        # Remove outliers
        outlier_indices = outlier_df.index
        df_cleaned = df.drop(outlier_indices)
        
        self.logger.info(f"Removed {len(outlier_indices)} outliers")
        return df_cleaned
    
    def normalize_data(self, df: pd.DataFrame, 
                      method: str = 'minmax') -> pd.DataFrame:
        """Normalize numeric data using specified method."""
        df_normalized = df.copy()
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if method == 'minmax':
            for col in numeric_cols:
                min_val = df[col].min()
                max_val = df[col].max()
                if max_val > min_val:
                    df_normalized[col] = (df[col] - min_val) / (max_val - min_val)
                    
        elif method == 'zscore':
            for col in numeric_cols:
                mean = df[col].mean()
                std = df[col].std()
                if std > 0:
                    df_normalized[col] = (df[col] - mean) / std
                    
        return df_normalized
    
    def standardize_timestamps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize timestamp format and timezone."""
        df_standardized = df.copy()
        
        if 'timestamp' in df.columns:
            df_standardized['timestamp'] = pd.to_datetime(df['timestamp'])
            # Ensure consistent timezone handling
            df_standardized['timestamp'] = df_standardized['timestamp'].dt.tz_localize(None)
            
        return df_standardized