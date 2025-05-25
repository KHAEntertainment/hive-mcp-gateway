"""
MCP Server utilities for Tool Gating service

DEPRECATED: MCP server is now created directly in main.py to ensure
all routes are registered before mounting.

This module now only contains utilities for running with stdio transport.
"""


def run_mcp_stdio():
    """Run as MCP server with stdio transport for Claude Desktop"""
    # For stdio transport, we need to use mcp-proxy as a bridge
    # This is documented in the MCP_NATIVE_USAGE.md
    import subprocess
    
    # Run mcp-proxy to bridge HTTP SSE to stdio
    subprocess.run([
        "mcp-proxy",
        "http://localhost:8000/mcp"
    ])