"""
Data consistency validation between different data sources.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd
from vprism.core.client.client import VPrismClient
from vprism.core.models.market import AssetType, MarketType

@dataclass
class ConsistencyReport:
    """Report containing data consistency validation results."""

    symbol: str
    start_date: date
    end_date: date
    total_records: int
    matching_records: int
    mismatching_records: int
    missing_in_vprism: int
    missing_in_external: int
    average_price_difference: float
    max_price_difference: float
    issues: list[str]
    detailed_comparison: dict[str, dict[str, Any]]
    consistency_percentage: float = field(init=False)

    def __post_init__(self) -> None:
        """Validate report data after initialization."""
        if self.total_records > 0:
            self.consistency_percentage = (self.matching_records / self.total_records) * 100.0
        else:
            self.consistency_percentage = 100.0


class DataConsistencyValidator:
    """Validates data consistency between vprism and an external data source."""

    def __init__(self, client: VPrismClient, external_provider: str = "akshare", tolerance: float = 0.01):
        """
        Initialize validator.
        Args:
            client: An instance of VPrismClient.
            external_provider: The name of the external provider to compare against.
            tolerance: Maximum allowed price difference as a percentage.
        """
        self.client = client
        self.external_provider = external_provider
        self.tolerance = tolerance

    async def validate_consistency(
        self, symbol: str, start_date: date, end_date: date, asset_type: AssetType, market: MarketType
    ) -> ConsistencyReport:
        """
        Validate data consistency for a symbol between a date range.
        """
        vprism_data = await self._get_vprism_data(symbol, start_date, end_date, asset_type, market)
        external_data = await self._get_external_data(symbol, start_date, end_date, asset_type, market)

        return self._compare_dataframes(vprism_data, external_data, symbol, start_date, end_date)

    async def _get_vprism_data(self, symbol: str, start_date: date, end_date: date, asset_type: AssetType, market: MarketType) -> pd.DataFrame:
        """Get data from vprism's default providers."""
        response = await self.client.get_async(
            symbols=[symbol],
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            asset=asset_type.value,
            market=market.value,
        )
        if not response or not response.data:
            return pd.DataFrame()
        return pd.DataFrame([dp.model_dump() for dp in response.data])

    async def _get_external_data(self, symbol: str, start_date: date, end_date: date, asset_type: AssetType, market: MarketType) -> pd.DataFrame:
        """Get data from the specified external provider."""
        response = await self.client.get_async(
            symbols=[symbol],
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            asset=asset_type.value,
            market=market.value,
            provider=self.external_provider,
        )
        if not response or not response.data:
            return pd.DataFrame()
        return pd.DataFrame([dp.model_dump() for dp in response.data])

    def _compare_dataframes(self, vprism_df: pd.DataFrame, external_df: pd.DataFrame, symbol: str, start_date: date, end_date: date) -> ConsistencyReport:
        """Compare dataframes and return a consistency report."""
        if vprism_df.empty and external_df.empty:
            return ConsistencyReport(
                symbol=symbol, start_date=start_date, end_date=end_date, total_records=0,
                matching_records=0, mismatching_records=0, missing_in_vprism=0,
                missing_in_external=0, average_price_difference=0.0, max_price_difference=0.0,
                issues=["Both data sources returned no data."], detailed_comparison={}
            )

        if "timestamp" in vprism_df.columns:
            vprism_df["date"] = pd.to_datetime(vprism_df["timestamp"]).dt.date
        if "timestamp" in external_df.columns:
            external_df["date"] = pd.to_datetime(external_df["timestamp"]).dt.date

        if 'date' not in vprism_df.columns and not vprism_df.empty:
            vprism_df['date'] = pd.to_datetime(vprism_df['timestamp']).dt.date
        if 'date' not in external_df.columns and not external_df.empty:
            external_df['date'] = pd.to_datetime(external_df['timestamp']).dt.date

        # Ensure 'date' column exists before merging
        if 'date' not in vprism_df.columns:
            vprism_df['date'] = None
        if 'date' not in external_df.columns:
            external_df['date'] = None

        merged = pd.merge(
            vprism_df,
            external_df,
            on="date",
            how="outer",
            suffixes=("_vprism", "_external"),
        )

        merged['close_price_vprism'] = pd.to_numeric(merged['close_price_vprism'], errors='coerce')
        merged['close_price_external'] = pd.to_numeric(merged['close_price_external'], errors='coerce')

        mismatched_dates = merged[merged["close_price_vprism"].notna() & merged["close_price_external"].notna() & (merged["close_price_vprism"] != merged["close_price_external"])]

        issues = []
        for _, row in mismatched_dates.iterrows():
            issues.append(
                f"Mismatch on {row['date']}: "
                f"vprism={row['close_price_vprism']:.2f}, "
                f"external={row['close_price_external']:.2f}"
            )

        diff = abs(merged['close_price_vprism'] - merged['close_price_external'])

        return ConsistencyReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            total_records=len(merged),
            matching_records=len(merged) - len(mismatched_dates),
            mismatching_records=len(mismatched_dates),
            missing_in_vprism=merged["close_price_vprism"].isnull().sum(),
            missing_in_external=merged["close_price_external"].isnull().sum(),
            average_price_difference=diff.mean(),
            max_price_difference=diff.max(),
            issues=issues,
            detailed_comparison={} # Placeholder for now
        )
