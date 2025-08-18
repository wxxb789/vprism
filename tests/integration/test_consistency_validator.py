import pytest
from datetime import date
from vprism.core.client.client import VPrismClient
from vprism.core.validation.consistency import DataConsistencyValidator
from vprism.core.models.market import AssetType, MarketType

@pytest.mark.integration
class TestConsistencyValidatorIntegration:
    """Integration tests for the DataConsistencyValidator."""

    @pytest.fixture(scope="class")
    def validator(self):
        """Fixture to provide an instance of the DataConsistencyValidator."""
        client = VPrismClient()
        return DataConsistencyValidator(client=client, external_provider="yfinance")

    @pytest.mark.xfail(reason="Intermittent network issues with external providers")
    async def test_validate_consistency_real_data(self, validator):
        """Test consistency validation with real data from providers."""
        report = await validator.validate_consistency(
            symbol="000001.SZ", # Ping An Bank, supported by both akshare and yfinance
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 31),
            asset_type=AssetType.STOCK,
            market=MarketType.CN,
        )

        assert report is not None
        assert report.total_records > 0
        assert report.symbol == "000001.SZ"
        # We expect some mismatches due to different data sources, so this can be > 0
        assert report.mismatching_records >= 0
        assert report.consistency_percentage is not None
