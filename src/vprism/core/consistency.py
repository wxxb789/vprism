"""
Data consistency validation between vprism and akshare.

This module provides comprehensive comparison and validation between vprism data
and akshare data to ensure accuracy and consistency.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from vprism.core.quality import DataQualityValidator
from vprism.infrastructure.providers.akshare import AkShare
from vprism.infrastructure.repositories.data import DataRepository


@dataclass
class ConsistencyReport:
    """Data consistency comparison report."""

    symbol: str
    start_date: datetime
    end_date: datetime
    total_records: int
    matching_records: int
    mismatching_records: int
    missing_in_vprism: int
    missing_in_akshare: int
    average_price_difference: float
    max_price_difference: float
    consistency_percentage: float
    issues: list[str]
    detailed_comparison: dict[str, Any]


class DataConsistencyValidator:
    """Validates data consistency between vprism and akshare."""

    def __init__(
        self,
        tolerance: float = 0.01,  # 1% tolerance for price differences
        repository: DataRepository | None = None,
    ):
        self.tolerance = tolerance
        self.repository = repository
        self.akshare_provider = AkShare()
        self.validator = DataQualityValidator()
        self.logger = logging.getLogger(__name__)

    def validate_consistency(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1d",
    ) -> ConsistencyReport:
        """Validate data consistency for a specific symbol and date range."""
        self.logger.info(
            f"Validating consistency for {symbol} from {start_date} to {end_date}"
        )

        # Get data from both sources
        vprism_data = self._get_vprism_data(symbol, start_date, end_date, timeframe)
        akshare_data = self._get_akshare_data(symbol, start_date, end_date, timeframe)

        # Perform comparison
        return self._compare_data(
            symbol, vprism_data, akshare_data, start_date, end_date
        )

    def _get_vprism_data(
        self, symbol: str, start_date: datetime, end_date: datetime, timeframe: str
    ) -> pd.DataFrame:
        """Get data from vprism repository."""
        if not self.repository:
            return pd.DataFrame()

        try:
            # Import here to avoid circular imports

            # Get data records using the repository's existing method
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                records = loop.run_until_complete(
                    self.repository.find_by_date_range(start_date, end_date, symbol)
                )
            finally:
                loop.close()

            if not records:
                return pd.DataFrame()

            # Convert DataRecord objects to DataFrame
            records_data = []
            for record in records:
                if hasattr(record, "__dict__"):
                    # DataRecord object
                    rec_dict = record.__dict__
                else:
                    # Dictionary
                    rec_dict = record

                records_data.append(
                    {
                        "timestamp": rec_dict.get("timestamp"),
                        "symbol": rec_dict.get("symbol"),
                        "open": rec_dict.get("open"),
                        "high": rec_dict.get("high"),
                        "low": rec_dict.get("low"),
                        "close": rec_dict.get("close"),
                        "volume": rec_dict.get("volume"),
                    }
                )

            return pd.DataFrame(records_data)

        except Exception as e:
            self.logger.error(f"Error getting vprism data: {e}")
            return pd.DataFrame()

    def _get_akshare_data(
        self, symbol: str, start_date: datetime, end_date: datetime, timeframe: str
    ) -> pd.DataFrame:
        """Get data from akshare."""
        try:
            # Create query for akshare provider
            from vprism.core.models import (
                Asset,
                AssetType,
                DataQuery,
                MarketType,
                TimeFrame,
            )

            Asset(
                symbol=symbol,
                name=symbol,
                asset_type=AssetType.STOCK,
                market=MarketType.CN,
                currency="CNY",
            )

            query = DataQuery(
                asset=AssetType.STOCK,
                market=MarketType.CN,
                start=start_date,
                end=end_date,
                timeframe=TimeFrame.DAY_1,
                symbols=[symbol],
            )

            # Use the sync method to get data
            try:
                # Import asyncio for sync execution
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    data_points = loop.run_until_complete(
                        self.akshare_provider._fetch_data(query)
                    )
                finally:
                    loop.close()

            except Exception:
                # Fallback to direct sync call
                data_points = self.akshare_provider._sync_fetch_data(query)

            if not data_points:
                return pd.DataFrame()

            # Convert DataPoint objects to DataFrame
            records = []
            for dp in data_points:
                records.append(
                    {
                        "timestamp": dp.timestamp,
                        "symbol": dp.symbol,
                        "open": float(dp.open) if dp.open else None,
                        "high": float(dp.high) if dp.high else None,
                        "low": float(dp.low) if dp.low else None,
                        "close": float(dp.close) if dp.close else None,
                        "volume": float(dp.volume) if dp.volume else None,
                    }
                )

            df = pd.DataFrame(records)
            return df.sort_values("timestamp")

        except Exception as e:
            self.logger.error(f"Error getting akshare data: {e}")
            return pd.DataFrame()

    def _compare_data(
        self,
        symbol: str,
        vprism_df: pd.DataFrame,
        akshare_df: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
    ) -> ConsistencyReport:
        """Compare data between vprism and akshare."""

        # Handle empty dataframes
        if vprism_df.empty or akshare_df.empty:
            return ConsistencyReport(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                total_records=max(len(vprism_df), len(akshare_df)),
                matching_records=0,
                mismatching_records=0,
                missing_in_vprism=0 if akshare_df.empty else len(akshare_df),
                missing_in_akshare=0 if vprism_df.empty else len(vprism_df),
                average_price_difference=0.0,
                max_price_difference=0.0,
                consistency_percentage=0.0,
                issues=["Empty data from one or both sources"],
                detailed_comparison={},
            )

        # Ensure timestamp column exists
        if (
            "timestamp" not in vprism_df.columns
            or "timestamp" not in akshare_df.columns
        ):
            return ConsistencyReport(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                total_records=max(len(vprism_df), len(akshare_df)),
                matching_records=0,
                mismatching_records=0,
                missing_in_vprism=0,
                missing_in_akshare=0,
                average_price_difference=0.0,
                max_price_difference=0.0,
                consistency_percentage=0.0,
                issues=["Missing timestamp column in data"],
                detailed_comparison={},
            )

        # Standardize timestamps
        vprism_df["timestamp"] = pd.to_datetime(vprism_df["timestamp"]).dt.date
        akshare_df["timestamp"] = pd.to_datetime(akshare_df["timestamp"]).dt.date

        # Find common timestamps
        common_timestamps = set(vprism_df["timestamp"]).intersection(
            set(akshare_df["timestamp"])
        )

        # Calculate statistics
        total_vprism = len(vprism_df)
        total_akshare = len(akshare_df)
        total_common = len(common_timestamps)

        missing_in_vprism = len(
            set(akshare_df["timestamp"]) - set(vprism_df["timestamp"])
        )
        missing_in_akshare = len(
            set(vprism_df["timestamp"]) - set(akshare_df["timestamp"])
        )

        # Compare matching records
        matching_records = 0
        mismatched_records = 0
        price_differences = []
        issues = []
        detailed_comparison = {}

        for timestamp in common_timestamps:
            vprism_row = vprism_df[vprism_df["timestamp"] == timestamp].iloc[0]
            akshare_row = akshare_df[akshare_df["timestamp"] == timestamp].iloc[0]

            comparison = {
                "timestamp": timestamp,
                "vprism_data": vprism_row.to_dict(),
                "akshare_data": akshare_row.to_dict(),
                "differences": {},
            }

            # Check price consistency
            price_fields = ["open", "high", "low", "close"]
            day_differences = []

            for field in price_fields:
                vprism_val = vprism_row.get(field)
                akshare_val = akshare_row.get(field)

                if vprism_val is not None and akshare_val is not None:
                    diff = abs(vprism_val - akshare_val)
                    relative_diff = diff / max(abs(vprism_val), abs(akshare_val), 1e-10)

                    comparison["differences"][field] = {
                        "vprism": vprism_val,
                        "akshare": akshare_val,
                        "absolute_diff": diff,
                        "relative_diff": relative_diff,
                    }

                    if relative_diff > self.tolerance:
                        mismatched_records += 1
                        issues.append(
                            f"{timestamp}: {field} differs by {relative_diff:.2%}"
                        )
                    else:
                        matching_records += 1

                    day_differences.append(relative_diff)

            if day_differences:
                price_differences.extend(day_differences)

            detailed_comparison[str(timestamp)] = comparison

        # Calculate summary statistics
        avg_price_diff = np.mean(price_differences) if price_differences else 0.0
        max_price_diff = np.max(price_differences) if price_differences else 0.0

        total_vprism + total_akshare - total_common
        consistency_percentage = (
            (matching_records / max(total_common * 4, 1)) * 100
            if total_common > 0
            else 0.0
        )

        return ConsistencyReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            total_records=max(total_vprism, total_akshare),
            matching_records=matching_records,
            mismatching_records=mismatched_records,
            missing_in_vprism=missing_in_vprism,
            missing_in_akshare=missing_in_akshare,
            average_price_difference=avg_price_diff,
            max_price_difference=max_price_diff,
            consistency_percentage=consistency_percentage,
            issues=issues,
            detailed_comparison=detailed_comparison,
        )

    def compare_multiple_symbols(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1d",
    ) -> dict[str, ConsistencyReport]:
        """Compare consistency for multiple symbols."""
        reports = {}

        for symbol in symbols:
            try:
                report = self.validate_consistency(
                    symbol, start_date, end_date, timeframe
                )
                reports[symbol] = report
            except Exception as e:
                self.logger.error(f"Error validating {symbol}: {e}")
                reports[symbol] = ConsistencyReport(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    total_records=0,
                    matching_records=0,
                    mismatching_records=0,
                    missing_in_vprism=0,
                    missing_in_akshare=0,
                    average_price_difference=0.0,
                    max_price_difference=0.0,
                    consistency_percentage=0.0,
                    issues=[f"Error: {str(e)}"],
                    detailed_comparison={},
                )

        return reports

    def generate_consistency_report(self, reports: dict[str, ConsistencyReport]) -> str:
        """Generate a formatted consistency report."""
        lines = []
        lines.append("=" * 80)
        lines.append("VPRISM vs AKSHARE DATA CONSISTENCY REPORT")
        lines.append("=" * 80)

        overall_consistency = []

        for symbol, report in reports.items():
            lines.append(f"\nSymbol: {symbol}")
            lines.append("-" * 40)
            lines.append(
                f"Date Range: {report.start_date.strftime('%Y-%m-%d')} to {report.end_date.strftime('%Y-%m-%d')}"
            )
            lines.append(f"Total Records: {report.total_records}")
            lines.append(f"Matching Records: {report.matching_records}")
            lines.append(f"Mismatching Records: {report.mismatching_records}")
            lines.append(f"Missing in vprism: {report.missing_in_vprism}")
            lines.append(f"Missing in akshare: {report.missing_in_akshare}")
            lines.append(
                f"Average Price Difference: {report.average_price_difference:.2%}"
            )
            lines.append(f"Max Price Difference: {report.max_price_difference:.2%}")
            lines.append(
                f"Consistency Percentage: {report.consistency_percentage:.1f}%"
            )

            if report.issues:
                lines.append("Issues:")
                for issue in report.issues:
                    lines.append(f"  - {issue}")

            overall_consistency.append(report.consistency_percentage)

        # Summary
        if overall_consistency:
            avg_consistency = np.mean(overall_consistency)
            lines.append("\n" + "=" * 80)
            lines.append("SUMMARY")
            lines.append("-" * 20)
            lines.append(
                f"Average Consistency Across All Symbols: {avg_consistency:.1f}%"
            )
            lines.append(
                f"Symbols with >95% consistency: {sum(1 for c in overall_consistency if c > 95)}"
            )
            lines.append(
                f"Symbols with <90% consistency: {sum(1 for c in overall_consistency if c < 90)}"
            )

        return "\n".join(lines)

    def run_automated_validation(
        self,
        symbols: list[str],
        days_back: int = 30,
        timeframe: str = "1d",
        alert_threshold: float = 95.0,
    ) -> dict[str, Any]:
        """Run automated consistency validation with alerting."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        reports = self.compare_multiple_symbols(
            symbols, start_date, end_date, timeframe
        )

        # Generate summary
        alert_symbols = []
        summary = {
            "total_symbols": len(symbols),
            "validated_symbols": len(
                [r for r in reports.values() if r.total_records > 0]
            ),
            "failed_symbols": len(
                [r for r in reports.values() if r.total_records == 0]
            ),
            "low_consistency_symbols": [],
            "alert_symbols": [],
            "reports": reports,
        }

        for symbol, report in reports.items():
            if (
                report.consistency_percentage < alert_threshold
                and report.total_records > 0
            ):
                alert_symbols.append(symbol)
                summary["low_consistency_symbols"].append(
                    {
                        "symbol": symbol,
                        "consistency": report.consistency_percentage,
                        "issues": len(report.issues),
                    }
                )

        summary["alert_symbols"] = alert_symbols

        return summary
