"""
vPrism MCP Server Package

This package provides the MCP (Model Context Protocol) server implementation
for vPrism financial data platform, enabling AI assistants to access
real-time and historical financial data through standardized MCP tools.
"""

__version__ = "0.1.0"
__author__ = "vPrism Team"
__description__ = "vPrism Financial Data Platform MCP Server"

from vprism.mcp.server import VPrismMCPServer, create_mcp_server

__all__ = ["VPrismMCPServer", "create_mcp_server"]
