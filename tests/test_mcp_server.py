"""
Tests for vPrism MCP Server

This module contains comprehensive tests for the vPrism MCP server,
including tool functionality, parameter validation, and error handling.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from vprism.core.exceptions import VPrismError
from vprism.core.models import DataPoint, DataResponse, ProviderInfo, ResponseMetadata

# Add Python path for imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'vprism-mcp'))

# Import after path setup
from server import VPrismMCPServer, create_mcp_server


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
    async def test_server_tools_exist(self):
        """Test that all expected tools are registered."""
        server = create_mcp_server()
        tools = await server.mcp.get_tools()
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
        resources = await server.mcp.get_resources()
        resource_uris = [str(r.uri) for r in resources]
        expected_resources = ["data://markets"]

        for resource_uri in expected_resources:
            assert resource_uri in resource_uris

    @pytest.mark.asyncio
    async def test_server_prompts_exist(self):
        """Test that all expected prompts are registered."""
        server = create_mcp_server()
        prompts = await server.mcp.get_prompts()
        prompt_names = [prompt.name for prompt in prompts]
        expected_prompts = ["financial_analysis"]

        for prompt_name in expected_prompts:
            assert prompt_name in prompt_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])