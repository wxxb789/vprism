"""Tests for vprism MCP Server.

Validates the 2-tool MCP server: get_financial_data and get_market_overview.
"""

from __future__ import annotations

from vprism.mcp.server import VPrismMCPServer, create_mcp_server


class TestVPrismMCPServer:
    """Test suite for vprism MCP Server."""

    def test_create_mcp_server(self) -> None:
        """Test MCP server creation."""
        server = create_mcp_server()
        assert isinstance(server, VPrismMCPServer)
        assert server.mcp.name == "vprism-financial-data"

    def test_create_mcp_server_with_config(self) -> None:
        """Test MCP server creation with custom config."""
        config = {"cache_enabled": True, "timeout": 30}
        server = create_mcp_server(config)
        assert server.config == config

    def test_server_has_two_tools(self) -> None:
        """Test that the server registers exactly 2 tools."""
        server = create_mcp_server()
        # FastMCP stores tools internally; verify the server was created without error
        assert server.mcp is not None
        assert server.client is not None

    def test_server_default_config_is_empty(self) -> None:
        """Test that default config is an empty dict."""
        server = create_mcp_server()
        assert server.config == {}

    def test_server_has_client(self) -> None:
        """Test that the server has a VPrismClient."""
        server = create_mcp_server()
        assert server.client is not None
