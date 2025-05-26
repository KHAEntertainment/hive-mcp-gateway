# FastAPI application entry point
# Defines the main app instance and core routes

import logging
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from .api import mcp, tools, proxy
from .services.mcp_client_manager import MCPClientManager
from .services.proxy_service import ProxyService
from .config import MCP_SERVERS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    message: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting Tool Gating MCP Proxy...")
    
    try:
        # Initialize client manager
        client_manager = MCPClientManager()
        
        # Connect to configured servers
        for server_name, config in MCP_SERVERS.items():
            try:
                logger.info(f"Connecting to MCP server: {server_name}")
                await client_manager.connect_server(server_name, config)
                logger.info(f"Successfully connected to {server_name}")
            except Exception as e:
                logger.error(f"Failed to connect to {server_name}: {e}")
        
        # Get tool repository from existing dependency
        from .api.tools import get_tool_repository
        tool_repository = await get_tool_repository()
        
        # Initialize proxy service
        proxy_service = ProxyService(client_manager, tool_repository)
        await proxy_service.discover_all_tools()
        
        # Store in app state for dependency injection
        app.state.client_manager = client_manager
        app.state.proxy_service = proxy_service
        
        logger.info("Proxy initialization complete")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Tool Gating MCP Proxy...")
    if hasattr(app.state, "client_manager"):
        await app.state.client_manager.disconnect_all()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Tool Gating MCP",
    description="FastAPI application for tool gating MCP",
    version="0.2.0",
    lifespan=lifespan
)

# Include API routers
app.include_router(tools.router)
app.include_router(mcp.router)
app.include_router(proxy.router)


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


# Add execute_tool endpoint that will be exposed as MCP tool
@app.post("/execute_tool", 
    summary="Execute a provisioned tool",
    description="Execute a tool on the appropriate backend MCP server")
async def execute_tool(tool_id: str, arguments: dict) -> Any:
    """Execute a provisioned tool on the appropriate MCP server.
    
    This is the main entry point for using tools discovered and provisioned
    through Tool Gating. The tool must be provisioned first using provision_tools.
    
    Args:
        tool_id: The tool identifier (format: "servername_toolname")
        arguments: Tool-specific arguments as required by the tool
        
    Returns:
        The result from the tool execution
        
    Raises:
        ValueError: If tool is not provisioned or server is not connected
    """
    if not hasattr(app.state, "proxy_service"):
        raise ValueError("Proxy service not initialized")
    
    return await app.state.proxy_service.execute_tool(tool_id, arguments)


# Mount the MCP server to make it available at /mcp endpoint
# This automatically calls setup_server() internally
mcp_server.mount()
