import pytest
from datetime import date
from vprism.core.client.client import VPrismClient
from vprism.core.models.market import AssetType, MarketType

@pytest.mark.integration
class TestFundProviderIntegration:
    """High-level integration tests for fetching fund data through the client."""

    @pytest.fixture(scope="class")
    def client(self):
        """Fixture to provide an instance of the VPrismClient."""
        return VPrismClient()

    async def test_fetch_fund_data(self, client):
        """Test fetching data for a specific fund."""
        response = await client.get_async(
            symbols=["018124"],
            asset=AssetType.FUND.value,
            market=MarketType.CN.value,
            start=date(2024, 1, 1).isoformat(),
            end=date(2024, 1, 10).isoformat(),
        )

        assert response is not None
        assert response.data
        assert response.metadata.total_records > 0
        assert response.data[0].symbol == "018124"
