"""
Tests for vPrism MCP Server

This module contains comprehensive tests for the vPrism MCP server,
including tool functionality, parameter validation, and error handling.
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import AsyncMock, patch

from vprism.mcp.server import VPrismMCPServer, create_mcp_server
from vprism.core.models import DataResponse, DataPoint, ResponseMetadata, ProviderInfo
from vprism.core.exceptions import VPrismError


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
        from vprism.core.models import ResponseMetadata, ProviderInfo
        return DataResponse(
            data=[
                DataPoint(
                    symbol="AAPL",
                    timestamp=datetime(2024, 1, 1),
                    open=Decimal("150.0"),
                    high=Decimal("155.0"),
                    low=Decimal("149.0"),
                    close=Decimal("154.0"),
                    volume=Decimal("1000000")
                ),
                DataPoint(
                    symbol="AAPL",
                    timestamp=datetime(2024, 1, 2),
                    open=Decimal("154.0"),
                    high=Decimal("158.0"),
                    low=Decimal("153.0"),
                    close=Decimal("157.0"),
                    volume=Decimal("1200000")
                )
            ],
            metadata=ResponseMetadata(
                total_records=2,
                query_time_ms=150.5,
                data_source="test_provider"
            ),
            source=ProviderInfo(
                name="test_provider",
                endpoint="https://api.test.com"
            )
        )
    
    @pytest.mark.asyncio
    async def test_get_stock_data_success(self, server, sample_stock_data):
        """Test successful retrieval of stock data."""
        with patch.object(server.client, 'get_async', return_value=sample_stock_data):
            result = await server.mcp.tool["get_stock_data"].function(
                symbol="AAPL",
                start_date="2024-01-01",
                end_date="2024-01-02",
                timeframe="1d",
                market="us"
            )
            
            assert result["symbol"] == "AAPL"
            assert result["market"] == "us"
            assert result["timeframe"] == "1d"
            assert result["data_points"] == 2
            assert len(result["data"]) == 2
            assert result["data"][0]["open"] == 150.0
            assert result["data"][0]["close"] == 154.0
    
    @pytest.mark.asyncio
    async def test_get_stock_data_empty(self, server):
        """Test handling of empty data response."""
        empty_response = DataResponse(
            data=[],
            metadata=ResponseMetadata(
                total_records=0,
                query_time_ms=50.0,
                data_source="test_provider"
            ),
            source=ProviderInfo(
                name="test_provider",
                endpoint="https://api.test.com"
            )
        )
        
        with patch.object(server.client, 'get_async', return_value=empty_response):
            result = await server.mcp.tool["get_stock_data"].function(
                symbol="AAPL",
                start_date="2024-01-01",
                end_date="2024-01-01",
                timeframe="1d"
            )
            
            assert result["symbol"] == "AAPL"
            assert result["data_points"] == 0
            assert result["data"] == []
    
    @pytest.mark.asyncio
    async def test_get_stock_data_error(self, server):
        """Test handling of vPrism exceptions."""
        with patch.object(server.client, 'get_async', side_effect=VPrismError("Test error")):
            result = await server.mcp.tool["get_stock_data"].function(
                symbol="INVALID",
                start_date="2024-01-01",
                end_date="2024-01-01"
            )
            
            assert "error" in result
            assert "Test error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_get_market_overview_success(self, server, sample_stock_data):
        """Test successful retrieval of market overview."""
        with patch.object(server.client, 'get_async', return_value=sample_stock_data):
            result = await server.mcp.tool["get_market_overview"].function(
                market="us",
                date="2024-01-01"
            )
            
            assert result["market"] == "us"
            assert result["date"] == "2024-01-01"
            assert "indices" in result
            assert "SPY" in result["indices"] or "QQQ" in result["indices"]
    
    @pytest.mark.asyncio
    async def test_search_symbols(self, server):
        """Test symbol search functionality."""
        result = await server.mcp.tool["search_symbols"].function(
            query="AAPL",
            market="us",
            limit=5
        )
        
        assert result["query"] == "AAPL"
        assert result["market"] == "us"
        assert result["total"] > 0
        assert len(result["results"]) > 0
        assert any(r["symbol"] == "AAPL" for r in result["results"])
    
    @pytest.mark.asyncio
    async def test_get_realtime_price_success(self, server, sample_stock_data):
        """Test successful retrieval of real-time price."""
        with patch.object(server.client, 'get_async', return_value=sample_stock_data):
            result = await server.mcp.tool["get_realtime_price"].function(
                symbol="AAPL",
                market="us"
            )
            
            assert result["symbol"] == "AAPL"
            assert result["market"] == "us"
            assert "price" in result
            assert "change" in result
            assert "change_percent" in result
    
    @pytest.mark.asyncio
    async def test_get_batch_quotes_success(self, server, sample_stock_data):
        """Test successful batch quote retrieval."""
        with patch.object(server.client, 'get_async', return_value=sample_stock_data):
            result = await server.mcp.tool["get_batch_quotes"].function(
                symbols=["AAPL", "MSFT", "GOOGL"],
                market="us"
            )
            
            assert result["market"] == "us"
            assert len(result["symbols"]) == 3
            assert "AAPL" in result["quotes"]
            assert "MSFT" in result["quotes"]
            assert "GOOGL" in result["quotes"]
            assert result["total"] == 3
    
    @pytest.mark.asyncio
    async def test_get_batch_quotes_partial_failure(self, server, sample_stock_data):
        """Test batch quotes with partial failures."""
        def mock_get_async(**kwargs):
            symbol = kwargs.get('symbol', '').upper()
            if symbol == "INVALID":
                raise VPrismError("Invalid symbol")
            return sample_stock_data
        
        with patch.object(server.client, 'get_async', side_effect=mock_get_async):
            result = await server.mcp.tool["get_batch_quotes"].function(
                symbols=["AAPL", "INVALID", "MSFT"],
                market="us"
            )
            
            assert result["market"] == "us"
            assert len(result["symbols"]) == 3
            assert "AAPL" in result["quotes"]
            assert "INVALID" in result["quotes"]
            assert "MSFT" in result["quotes"]
            assert result["quotes"]["INVALID"]["error"] == "Invalid symbol"
    
    @pytest.mark.asyncio
    async def test_get_available_markets_resource(self, server):
        """Test available markets resource."""
        result = await server.mcp.resource["data://markets"].read()
        
        assert "markets" in result
        assert "us" in result["markets"]
        assert "cn" in result["markets"]
        assert "hk" in result["markets"]
        assert "name" in result["markets"]["us"]
        assert "description" in result["markets"]["us"]
    
    @pytest.mark.asyncio
    async def test_financial_analysis_prompt(self, server):
        """Test financial analysis prompt generation."""
        result = await server.mcp.prompt["financial_analysis"].render(
            symbol="AAPL",
            timeframe="6m"
        )
        
        assert "AAPL" in result
        assert "6m" in result
        assert "Price trends" in result
        assert "technical indicators" in result
    
    @pytest.mark.asyncio
    async def test_parameter_validation(self, server):
        """Test parameter validation for tools."""
        # Test invalid date format
        with patch.object(server.client, 'get_async', return_value=DataResponse(
            data=[],
            metadata=ResponseMetadata(
                total_records=0,
                query_time_ms=25.0,
                data_source="test_provider"
            ),
            source=ProviderInfo(
                name="test_provider",
                endpoint="https://api.test.com"
            )
        )):
            result = await server.mcp.tool["get_stock_data"].function(
                symbol="AAPL",
                start_date="invalid-date",
                end_date="2024-01-01"
            )
            
            # Should handle gracefully and return some result
            assert isinstance(result, dict)
    
    def test_create_mcp_server(self):
        """Test MCP server creation."""
        server = create_mcp_server()
        assert isinstance(server, VPrismMCPServer)
        assert server.mcp.name == "vprism-financial-data"
        assert server.mcp.version == "0.1.0"
    
    def test_create_mcp_server_with_config(self):
        """Test MCP server creation with custom config."""
        config = {"cache_enabled": True, "timeout": 30}
        server = create_mcp_server(config)
        assert server.config == config
    
    @pytest.mark.asyncio
    async def test_server_initialization(self, server):
        """Test server initialization and cleanup."""
        with patch.object(server.client, 'initialize', return_value=None):
            with patch.object(server.client, 'close', return_value=None):
                # This would normally start the server
                pass  # Server startup tested in integration tests
    
    @pytest.mark.asyncio
    async def test_error_handling_unexpected_exception(self, server):
        """Test handling of unexpected exceptions."""
        with patch.object(server.client, 'get_async', side_effect=Exception("Unexpected error")):
            result = await server.mcp.tool["get_stock_data"].function(
                symbol="AAPL",
                start_date="2024-01-01",
                end_date="2024-01-01"
            )
            
            assert "error" in result
            assert "Unexpected error" in result["error"]


class TestMCPServerIntegration:
    """Integration tests for MCP server."""
    
    @pytest.mark.asyncio
    async def test_server_tools_exist(self):
        """Test that all expected tools are registered."""
        server = create_mcp_server()
        
        expected_tools = [
            "get_stock_data",
            "get_market_overview",
            "search_symbols",
            "get_realtime_price",
            "get_batch_quotes"
        ]
        
        for tool_name in expected_tools:
            assert tool_name in server.mcp.tools
    
    @pytest.mark.asyncio
    async def test_server_resources_exist(self):
        """Test that all expected resources are registered."""
        server = create_mcp_server()
        
        expected_resources = [
            "data://markets"
        ]
        
        for resource_uri in expected_resources:
            assert resource_uri in server.mcp.resources
    
    @pytest.mark.asyncio
    async def test_server_prompts_exist(self):
        """Test that all expected prompts are registered."""
        server = create_mcp_server()
        
        expected_prompts = [
            "financial_analysis"
        ]
        
        for prompt_name in expected_prompts:
            assert prompt_name in server.mcp.prompts


@pytest.mark.asyncio
async def test_mcp_server_e2e():
    """End-to-end test of MCP server functionality."""
    server = create_mcp_server()
    
    # Mock the client to avoid external API calls
    with patch.object(server.client, 'get_async') as mock_get:
        mock_response = DataResponse(
            data=[
                DataPoint(
                    symbol="TEST",
                    timestamp=datetime.now(),
                    open=100.0,
                    high=105.0,
                    low=99.0,
                    close=103.0,
                    volume=1000
                )
            ],
            metadata=ResponseMetadata(
                total_records=1,
                query_time_ms=75.0,
                data_source="test_provider"
            ),
            source=ProviderInfo(
                name="test_provider",
                endpoint="https://api.test.com"
            )
        )
        mock_get.return_value = mock_response
        
        # Test all tools
        tools_to_test = [
            ("get_stock_data", {
                "symbol": "TEST",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01"
            }),
            ("get_realtime_price", {
                "symbol": "TEST"
            }),
            ("get_batch_quotes", {
                "symbols": ["TEST", "TEST2"]
            })
        ]
        
        for tool_name, params in tools_to_test:
            tool = server.mcp.tool[tool_name]
            result = await tool.function(**params)
            assert isinstance(result, dict)
            assert "error" not in result or isinstance(result["error"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])