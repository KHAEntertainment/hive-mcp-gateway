"""
MCP Server wrapper for Tool Gating service

This module converts our FastAPI service into an MCP server,
allowing Claude and other LLMs to use it natively via MCP protocol.
"""

from fastapi_mcp import FastApiMCP
from .main import app


# Create the MCP server from our FastAPI app
mcp = FastApiMCP(
    app,
    name="tool-gating",
    description=(
        "Intelligently manage MCP tools to prevent context bloat. "
        "Discover and provision only the most relevant tools for each task."
    )
)

# Mount the MCP server to make it available at /mcp endpoint
mcp.mount()


def run_mcp_stdio():
    """Run as MCP server with stdio transport for Claude Desktop"""
    # For stdio transport, we need to use mcp-proxy as a bridge
    # This is documented in the MCP_NATIVE_USAGE.md
    import subprocess
    import sys
    
    # Run mcp-proxy to bridge HTTP SSE to stdio
    subprocess.run([
        "mcp-proxy",
        "http://localhost:8000/mcp"
    ])