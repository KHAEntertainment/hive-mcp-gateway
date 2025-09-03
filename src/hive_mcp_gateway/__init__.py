# FastAPI application for tool gating MCP
# Main module initialization

import sys

from .main import app as app

__version__ = "0.2.0"


def main() -> None:
    """CLI entry point for the application."""
    print("=== INIT.PY MAIN FUNCTION CALLED ===")
    import uvicorn

    # Check if running in MCP mode
    if "--mcp" in sys.argv:
        # Run as MCP server using stdio transport
        from .mcp_server import run_mcp_stdio
        run_mcp_stdio()
    else:
        # Run as standard HTTP API
        print("=== STARTING UVICORN SERVER ===")
        uvicorn.run("hive_mcp_gateway.main:app", host="0.0.0.0", port=8001, reload=True)
        print("=== UVICORN SERVER STOPPED ===")
        
    print("=== INIT.PY MAIN FUNCTION ENDED ===")
