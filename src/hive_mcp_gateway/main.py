# FastAPI application entry point
# Defines the main app instance and core routes

import logging
import os
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from .api import mcp, tools, proxy, oauth_endpoints, ide_endpoints
from .services.mcp_client_manager import MCPClientManager
from .services.proxy_service import ProxyService
from .services.config_manager import ConfigManager
from .services.file_watcher import FileWatcherService
from .services.repository import InMemoryToolRepository
from .services.mcp_registry import MCPServerRegistry
from .services.auto_registration import AutoRegistrationService
from .services.error_handler import ErrorHandler

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
    logger.info("Starting Hive MCP Gateway Proxy...")
    
    try:
        # Initialize configuration manager
        config_path = os.getenv('CONFIG_PATH', 'config/tool_gating_config.yaml')
        config_manager = ConfigManager(config_path)
        
        # Load configuration
        config = config_manager.load_config()
        app_settings = config.tool_gating
        backend_servers = config.backend_mcp_servers
        
        logger.info(f"Loaded configuration: {len(backend_servers)} backend servers configured")
        logger.info(f"Application port: {app_settings.port}, Host: {app_settings.host}")
        
        # Initialize services
        client_manager = MCPClientManager()
        registry = MCPServerRegistry(config_path)
        auto_registration = AutoRegistrationService(config_manager, client_manager, registry)
        error_handler = ErrorHandler()
        
        # Automatically register all servers with multi-stage pipeline
        logger.info("Starting automatic server registration pipeline...")
        registration_results = await auto_registration.register_all_servers(config)
        
        # Log registration results
        logger.info(f"Registration complete - Successful: {len(registration_results['successful'])}, "
                    f"Failed: {len(registration_results['failed'])}, "
                    f"Skipped: {len(registration_results['skipped'])}")
        
        if registration_results["failed"]:
            logger.warning("Some servers failed to register:")
            for failed in registration_results["failed"]:
                logger.warning(f" - {failed['server']}: {failed['error']}")
        
        # Get tool repository
        tool_repository = InMemoryToolRepository()
        
        # Initialize proxy service
        proxy_service = ProxyService(client_manager, tool_repository)
        await proxy_service.discover_all_tools()
        
        # Initialize file watcher for dynamic configuration updates
        file_watcher = FileWatcherService(config_manager, client_manager)
        
        # Start file watching if enabled
        if app_settings.config_watch_enabled:
            await file_watcher.start_watching(config_path)
            logger.info("✓ Configuration file watching enabled")
        
        # Store in app state for dependency injection
        app.state.client_manager = client_manager
        app.state.proxy_service = proxy_service
        app.state.config_manager = config_manager
        app.state.file_watcher = file_watcher
        app.state.app_settings = app_settings
        app.state.registry = registry
        app.state.auto_registration = auto_registration
        app.state.error_handler = error_handler
        
        logger.info("✓ Proxy initialization complete")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Hive MCP Gateway Proxy...")
    
    # Stop file watcher
    if hasattr(app.state, "file_watcher"):
        await app.state.file_watcher.stop_watching()
    
    # Disconnect all MCP servers
    if hasattr(app.state, "client_manager"):
        await app.state.client_manager.disconnect_all()
    
    logger.info("Shutdown complete")


app = FastAPI(
    title="Hive MCP Gateway",
    description="FastAPI application for tool gating MCP",
    version="0.2.0",
    lifespan=lifespan
)

# Include API routers
app.include_router(tools.router)
app.include_router(mcp.router)
app.include_router(proxy.router)
app.include_router(oauth_endpoints.router)
app.include_router(ide_endpoints.router)


@app.get("/", operation_id="root")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Welcome to Hive MCP Gateway"}


@app.get("/health", response_model=HealthResponse, operation_id="health")
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", message="Service is running")


# Create and mount MCP server AFTER all routes are defined
from fastapi_mcp import FastApiMCP

# Include only specific operations to be exposed as MCP tools
# This prevents context bloat by only exposing essential tools
mcp_server = FastApiMCP(
    app,
    name="hive-gateway",
    description=(
        "Intelligently manage MCP tools to prevent context bloat. "
        "Discover and provision only the most relevant tools for each task. "
        "Works with any MCP-compatible client including Claude Desktop, Claude Code, Gemini CLI, etc."
    ),
    include_operations=["add_server", "discover_tools", "execute_tool", "register_tool"]
)


# Note: Tool execution is handled by /api/proxy/execute endpoint
# This avoids duplication and keeps the API organized


# Mount the MCP server to make it available at /mcp endpoint
# This automatically calls setup_server() internally
mcp_server.mount()


def main():
    """Main entry point for running the application."""
    import uvicorn
    
    # Load configuration to get host and port
    try:
        config_path = os.getenv('CONFIG_PATH', 'config/tool_gating_config.yaml')
        config_manager = ConfigManager(config_path)
        config = config_manager.load_config()
        
        host = os.getenv('HOST', config.tool_gating.host)
        port = int(os.getenv('PORT', config.tool_gating.port))
        log_level = os.getenv('LOG_LEVEL', config.tool_gating.log_level).lower()
        
        logger.info(f"Starting Hive MCP Gateway on {host}:{port}")
        logger.info(f"Log level: {log_level}")
        logger.info(f"Configuration file: {config_path}")
        
        uvicorn.run(
            "hive_mcp_gateway.main:app",
            host=host,
            port=port,
            log_level=log_level,
            reload=False,  # Disable reload in production
            access_log=True
        )
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise


if __name__ == "__main__":
    main()
