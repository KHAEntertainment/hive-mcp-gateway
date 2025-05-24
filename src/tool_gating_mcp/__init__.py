# FastAPI application for tool gating MCP
# Main module initialization

from .main import app as app

__version__ = "0.1.0"


def main() -> None:
    """CLI entry point for the application."""
    import uvicorn

    uvicorn.run("tool_gating_mcp.main:app", host="0.0.0.0", port=8000, reload=True)
