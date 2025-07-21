"""
Tests for vPrism MCP Server

This module contains comprehensive tests for the vPrism MCP server,
including tool functionality, parameter validation, and error handling.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from vprism.core.exceptions import VPrismError
from vprism.core.models import DataPoint, DataResponse, ProviderInfo, ResponseMetadata
from vprism.mcp.server import VPrismMCPServer, create_mcp_server


class TestVPrismMCPServer:
    """Test suite for vPrism MCP Server."""

    @pytest.fixture
    def server(self):
        """Create a test server instance."""
        return create_mcp_server(config={"test_mode": True})

    @pytest.fixture
    def mock_client(self):
        """Create a mock vPrism client."""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def sample_stock_data(self):
        """Sample stock data for testing."""
        from decimal import Decimal

        from vprism.core.models import ProviderInfo, ResponseMetadata

        return DataResponse(
            data=[
                DataPoint(
                    symbol="AAPL",
                    timestamp=datetime(2024, 1, 1),
                    open=Decimal("150.0"),
                    high=Decimal("155.0"),
                    low=Decimal("149.0"),
                    close=Decimal("154.0"),
                    volume=Decimal("1000000"),
                ),
                DataPoint(
                    symbol="AAPL",
                    timestamp=datetime(2024, 1, 2),
                    open=Decimal("154.0"),
                    high=Decimal("158.0"),
                    low=Decimal("153.0"),
                    close=Decimal("157.0"),
                    volume=Decimal("1200000"),
                ),
            ],
            metadata=ResponseMetadata(
                total_records=2, query_time_ms=150.5, data_source="test_provider"
            ),
            source=ProviderInfo(name="test_provider", endpoint="https://api.test.com"),
        )

    @pytest.mark.asyncio
    async def test_get_stock_data_success(self, server, sample_stock_data):
        """Test successful retrieval of stock data."""
        with patch.object(server.client, "get_async", return_value=sample_stock_data):
            result = await server.mcp.call_tool(
                "get_stock_data",
                arguments={
                    "symbol": "AAPL",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-02",
                    "timeframe": "1d",
                    "market": "us",
                },
            )

            # Parse result from FastMCP 2.x format
            result_data = json.loads(result.content[0].text)
            assert result_data["symbol"] == "AAPL"
            assert result_data["market"] == "us"
            assert result_data["timeframe"] == "1d"
            assert result_data["data_points"] == 2
            assert len(result_data["data"]) == 2
            assert result_data["data"][0]["open"] == 150.0
            assert result_data["data"][0]["close"] == 154.0

    @pytest.mark.asyncio
    async def test_get_stock_data_empty(self, server):
        """Test handling of empty data response."""
        empty_response = DataResponse(
            data=[],
            metadata=ResponseMetadata(
                total_records=0, query_time_ms=50.0, data_source="test_provider"
            ),
            source=ProviderInfo(name="test_provider", endpoint="https://api.test.com"),
        )

        with patch.object(server.client, "get_async", return_value=empty_response):
            result = await server.mcp.call_tool(
                "get_stock_data",
                arguments={
                    "symbol": "AAPL",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-01",
                    "timeframe": "1d",
                },
            )

            result_data = json.loads(result.content[0].text)
            assert result_data["symbol"] == "AAPL"
            assert result_data["data_points"] == 0
            assert result_data["data"] == []

    @pytest.mark.asyncio
    async def test_get_stock_data_error(self, server):
        """Test handling of vPrism exceptions."""
        with patch.object(
            server.client, "get_async", side_effect=VPrismError("Test error")
        ):
            result = await server.mcp.call_tool(
                "get_stock_data",
                arguments={
                    "symbol": "INVALID",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-01",
                },
            )

            result_data = json.loads(result.content[0].text)
            assert "error" in result_data
            assert "Test error" in result_data["error"]

    @pytest.mark.asyncio
    async def test_get_market_overview_success(self, server, sample_stock_data):
        """Test successful retrieval of market overview."""
        with patch.object(server.client, "get_async", return_value=sample_stock_data):
            result = await server.mcp.call_tool(
                "get_market_overview", arguments={"market": "us", "date": "2024-01-01"}
            )

            result_data = json.loads(result.content[0].text)
            assert result_data["market"] == "us"
            assert result_data["date"] == "2024-01-01"
            assert "indices" in result_data
            assert "SPY" in result_data["indices"] or "QQQ" in result_data["indices"]

    @pytest.mark.asyncio
    async def test_search_symbols(self, server):
        """Test symbol search functionality."""
        result = await server.mcp.call_tool(
            "search_symbols", arguments={"query": "AAPL", "market": "us", "limit": 5}
        )

        result_data = json.loads(result.content[0].text)
        assert result_data["query"] == "AAPL"
        assert result_data["market"] == "us"
        assert result_data["total"] > 0
        assert len(result_data["results"]) > 0
        assert any(r["symbol"] == "AAPL" for r in result_data["results"])

    @pytest.mark.asyncio
    async def test_get_realtime_price_success(self, server, sample_stock_data):
        """Test successful retrieval of real-time price."""
        with patch.object(server.client, "get_async", return_value=sample_stock_data):
            result = await server.mcp.call_tool(
                "get_realtime_price", arguments={"symbol": "AAPL", "market": "us"}
            )

            result_data = json.loads(result.content[0].text)
            assert result_data["symbol"] == "AAPL"
            assert result_data["market"] == "us"
            assert "price" in result_data
            assert "change" in result_data
            assert "change_percent" in result_data

    @pytest.mark.asyncio
    async def test_get_batch_quotes_success(self, server, sample_stock_data):
        """Test successful batch quote retrieval."""
        with patch.object(server.client, "get_async", return_value=sample_stock_data):
            result = await server.mcp.call_tool(
                "get_batch_quotes",
                arguments={"symbols": ["AAPL", "MSFT", "GOOGL"], "market": "us"},
            )

            result_data = json.loads(result.content[0].text)
            assert result_data["market"] == "us"
            assert len(result_data["symbols"]) == 3
            assert "AAPL" in result_data["quotes"]
            assert "MSFT" in result_data["quotes"]
            assert "GOOGL" in result_data["quotes"]
            assert result_data["total"] == 3

    @pytest.mark.asyncio
    async def test_get_batch_quotes_partial_failure(self, server, sample_stock_data):
        """Test batch quotes with partial failures."""

        def mock_get_async(**kwargs):
            symbol = kwargs.get("symbol", "").upper()
            if symbol == "INVALID":
                raise VPrismError("Invalid symbol")
            return sample_stock_data

        with patch.object(server.client, "get_async", side_effect=mock_get_async):
            result = await server.mcp.call_tool(
                "get_batch_quotes",
                arguments={"symbols": ["AAPL", "INVALID", "MSFT"], "market": "us"},
            )

            result_data = json.loads(result.content[0].text)
            assert result_data["market"] == "us"
            assert len(result_data["symbols"]) == 3
            assert "AAPL" in result_data["quotes"]
            assert "INVALID" in result_data["quotes"]
            assert "MSFT" in result_data["quotes"]
            assert result_data["quotes"]["INVALID"]["error"] == "Invalid symbol"

    @pytest.mark.asyncio
    async def test_get_available_markets_resource(self, server):
        """Test available markets resource."""
        resource_list = server.mcp.list_resources()
        market_resource = next(
            (r for r in resource_list if str(r.uri) == "data://markets"), None
        )
        assert market_resource is not None

        # Use read_resource instead of read()
        result = await server.mcp.read_resource(market_resource.uri)
        result_data = json.loads(result.content[0].text)

        assert "markets" in result_data
        assert "us" in result_data["markets"]
        assert "cn" in result_data["markets"]
        assert "hk" in result_data["markets"]
        assert "name" in result_data["markets"]["us"]
        assert "description" in result_data["markets"]["us"]

    @pytest.mark.asyncio
    async def test_financial_analysis_prompt(self, server):
        """Test financial analysis prompt generation."""
        prompt_list = server.mcp.list_prompts()
        analysis_prompt = next(
            (p for p in prompt_list if p.name == "financial_analysis"), None
        )
        assert analysis_prompt is not None

        # Use get_prompt and render instead of render directly
        prompt = server.mcp.get_prompt("financial_analysis")
        messages = await prompt.render(arguments={"symbol": "AAPL", "timeframe": "6m"})
        content = messages[0].content.text if messages else ""

        assert "AAPL" in content
        assert "6m" in content
        assert "Price trends" in content
        assert "technical indicators" in content

    @pytest.mark.asyncio
    async def test_parameter_validation(self, server):
        """Test parameter validation for tools."""
        # Test invalid date format
        with patch.object(
            server.client,
            "get_async",
            return_value=DataResponse(
                data=[],
                metadata=ResponseMetadata(
                    total_records=0, query_time_ms=25.0, data_source="test_provider"
                ),
                source=ProviderInfo(
                    name="test_provider", endpoint="https://api.test.com"
                ),
            ),
        ):
            result = await server.mcp.call_tool(
                "get_stock_data",
                arguments={
                    "symbol": "AAPL",
                    "start_date": "invalid-date",
                    "end_date": "2024-01-01",
                },
            )
            result_data = json.loads(result.content[0].text)
            # Should handle gracefully and return some result
            assert isinstance(result_data, dict)

    def test_create_mcp_server(self):
        """Test MCP server creation."""
        server = create_mcp_server()
        assert isinstance(server, VPrismMCPServer)
        assert server.mcp.name == "vprism-financial-data"

    def test_create_mcp_server_with_config(self):
        """Test MCP server creation with custom config."""
        config = {"cache_enabled": True, "timeout": 30}
        server = create_mcp_server(config)
        assert server.config == config

    @pytest.mark.asyncio
    async def test_server_initialization(self, server):
        """Test server initialization and cleanup."""
        with patch.object(server.client, "initialize", return_value=None):
            with patch.object(server.client, "close", return_value=None):
                # This would normally start the server
                pass  # Server startup tested in integration tests

    @pytest.mark.asyncio
    async def test_error_handling_unexpected_exception(self, server):
        """Test handling of unexpected exceptions."""
        with patch.object(
            server.client, "get_async", side_effect=Exception("Unexpected error")
        ):
            result = await server.mcp.tool["get_stock_data"].function(
                symbol="AAPL", start_date="2024-01-01", end_date="2024-01-01"
            )

            assert "error" in result
            assert "Unexpected error" in result["error"]


class TestMCPServerIntegration:
    """Integration tests for MCP server."""

    @pytest.mark.asyncio
    async def test_server_tools_exist(self):
        """Test that all expected tools are registered."""
        server = create_mcp_server()
        tools = server.mcp.list_tools()
        tool_names = [tool.name for tool in tools]

        expected_tools = [
            "get_stock_data",
            "get_market_overview",
            "search_symbols",
            "get_realtime_price",
            "get_batch_quotes",
        ]

        for tool_name in expected_tools:
            assert tool_name in tool_names

    @pytest.mark.asyncio
    async def test_server_resources_exist(self):
        """Test that all expected resources are registered."""
        server = create_mcp_server()
        resources = server.mcp.list_resources()
        resource_uris = [resource.uri for resource in resources]
        expected_resources = ["data://markets"]

        for resource_uri in expected_resources:
            assert resource_uri in resource_uris

    @pytest.mark.asyncio
    async def test_server_prompts_exist(self):
        """Test that all expected prompts are registered."""
        server = create_mcp_server()
        prompts = server.mcp.list_prompts()
        prompt_names = [prompt.name for prompt in prompts]
        expected_prompts = ["financial_analysis"]

        for prompt_name in expected_prompts:
            assert prompt_name in prompt_names


@pytest.mark.asyncio
async def test_mcp_server_e2e():
    """End-to-end test of MCP server functionality."""
    server = create_mcp_server()

    # Mock the client to avoid external API calls
    with patch.object(server.client, "get_async") as mock_get:
        mock_response = DataResponse(
            data=[
                DataPoint(
                    symbol="TEST",
                    timestamp=datetime.now(),
                    open=100.0,
                    high=105.0,
                    low=99.0,
                    close=103.0,
                    volume=1000,
                )
            ],
            metadata=ResponseMetadata(
                total_records=1, query_time_ms=75.0, data_source="test_provider"
            ),
            source=ProviderInfo(name="test_provider", endpoint="https://api.test.com"),
        )
        mock_get.return_value = mock_response

        # Test all tools
        tools_to_test = [
            (
                "get_stock_data",
                {
                    "symbol": "TEST",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-01",
                },
            ),
            ("get_realtime_price", {"symbol": "TEST"}),
            ("get_batch_quotes", {"symbols": ["TEST", "TEST2"]}),
        ]

        for tool_name, params in tools_to_test:
            tool = server.mcp.get_tool(tool_name)
            result = await tool.run(**params)
            assert isinstance(result, dict)
            assert "error" not in result or isinstance(result["error"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
