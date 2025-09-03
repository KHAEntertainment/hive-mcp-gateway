# FastAPI application for tool gating MCP
# Main module initialization

import sys

from .main import app as app

__version__ = "0.2.0"


def main() -> None:
    """CLI entry point for the application."""
    print("=== INIT.PY MAIN FUNCTION CALLED ===")
    import uvicorn

    # Always run as standard HTTP API for debugging
    print("=== STARTING UVICORN SERVER AS HTTP API ===")
    uvicorn.run("hive_mcp_gateway.main:app", host="0.0.0.0", port=8001, reload=False)
    print("=== UVICORN SERVER STOPPED ===")
        
    print("=== INIT.PY MAIN FUNCTION ENDED ===")
