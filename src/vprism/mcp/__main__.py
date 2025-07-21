"""
Main entry point for vPrism MCP Server.

This module provides command-line interface for running the vPrism MCP server
with different transport modes and configurations.
"""

import argparse
import asyncio
import sys
from typing import Optional

from loguru import logger

from vprism.mcp.server import create_mcp_server


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the MCP server."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8>}</level> | <cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level.upper()
    )


async def main():
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="vPrism Financial Data MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="Transport method for MCP communication"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address for HTTP/SSE transport"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for HTTP/SSE transport"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file (JSON/YAML)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.debug else args.log_level
    setup_logging(log_level)
    
    # Load configuration
    config = {}
    if args.config:
        import json
        import yaml
        
        try:
            with open(args.config, 'r') as f:
                if args.config.endswith('.yaml') or args.config.endswith('.yml'):
                    config = yaml.safe_load(f)
                else:
                    config = json.load(f)
            logger.info(f"Loaded configuration from {args.config}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
    
    logger.info(f"Starting vPrism MCP Server with transport: {args.transport}")
    
    # Create and start MCP server
    try:
        server = create_mcp_server(config)
        
        if args.transport == "stdio":
            await server.start("stdio")
        elif args.transport == "http":
            await server.mcp.run(
                transport="http",
                host=args.host,
                port=args.port
            )
        elif args.transport == "sse":
            await server.mcp.run(
                transport="sse",
                host=args.host,
                port=args.port
            )
            
    except KeyboardInterrupt:
        logger.info("Shutting down vPrism MCP Server...")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())