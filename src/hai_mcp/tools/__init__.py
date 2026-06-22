"""Tool registration for the HAI MCP server."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import connection, discovery, instances, remote


def register_all(mcp: FastMCP) -> None:
    """Register every tool group on the given FastMCP server."""
    discovery.register(mcp)
    instances.register(mcp)
    connection.register(mcp)
    remote.register(mcp)
