"""
vprism MCP Server Package

This package provides the MCP (Model Context Protocol) server implementation
for vprism financial data platform, enabling AI assistants to access
real-time and historical financial data through standardized MCP tools.
"""

__version__ = "0.1.0"
__author__ = "vprism team"
__description__ = "vprism Financial Data Platform MCP Server"

from vprism.mcp.server import VPrismMCPServer, create_mcp_server

__all__ = ["VPrismMCPServer", "create_mcp_server"]
