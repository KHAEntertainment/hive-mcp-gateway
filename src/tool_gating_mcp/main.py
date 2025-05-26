# FastAPI application entry point
# Defines the main app instance and core routes

from fastapi import FastAPI
from pydantic import BaseModel

from .api import mcp, tools


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    message: str


app = FastAPI(
    title="Tool Gating MCP",
    description="FastAPI application for tool gating MCP",
    version="0.2.0",
)

# Include API routers
app.include_router(tools.router)
app.include_router(mcp.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Welcome to Tool Gating MCP"}


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", message="Service is running")


# Create and mount MCP server AFTER all routes are defined
from fastapi_mcp import FastApiMCP

mcp_server = FastApiMCP(
    app,
    name="tool-gating",
    description=(
        "Intelligently manage MCP tools to prevent context bloat. "
        "Discover and provision only the most relevant tools for each task."
    )
)

# Mount the MCP server to make it available at /mcp endpoint
# This automatically calls setup_server() internally
mcp_server.mount()
