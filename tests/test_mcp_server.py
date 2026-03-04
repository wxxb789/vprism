"""Tests for vprism MCP Server.

Validates the 2-tool MCP server: get_financial_data and get_market_overview.
"""

from __future__ import annotations

from vprism.mcp.server import VPrismMCPServer, create_mcp_server


class TestVPrismMCPServer:
    """Test suite for vprism MCP Server."""

    def test_mcp_server_creation_and_defaults(self) -> None:
        """Test MCP server creation with default configuration."""
        server = create_mcp_server()
        assert isinstance(server, VPrismMCPServer)
        assert server.mcp.name == "vprism-financial-data"
        assert server.client is not None
        assert server.config == {}

    def test_create_mcp_server_with_config(self) -> None:
        """Test MCP server creation with custom config."""
        config = {"cache_enabled": True, "timeout": 30}
        server = create_mcp_server(config)
        assert server.config == config
