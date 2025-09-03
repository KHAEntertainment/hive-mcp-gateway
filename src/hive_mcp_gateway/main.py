# FastAPI application entry point
# Defines the main app instance and core routes
print("=== FILE IS BEING IMPORTED ===")

import logging
import os
from typing import Any
from contextlib import asynccontextmanager
import asyncio

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

# Configure logging with debug level
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    message: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    print("=== LIFESPAN STARTUP PHASE STARTING ===")
    logger.info("=== LIFESPAN STARTUP PHASE STARTING ===")
    
    try:
        logger.info("Initializing configuration manager...")
        # Initialize configuration manager
        config_path = os.getenv('CONFIG_PATH', 'config/tool_gating_config.yaml')
        config_manager = ConfigManager(config_path)
        
        logger.info("Loading configuration...")
        # Load configuration
        config = config_manager.load_config()
        app_settings = config.tool_gating
        backend_servers = config.backend_mcp_servers
        
        logger.info(f"Loaded configuration: {len(backend_servers)} backend servers configured")
        logger.info(f"Application port: {app_settings.port}, Host: {app_settings.host}")
        
        # Initialize services
        logger.info("Initializing MCPClientManager...")
        client_manager = MCPClientManager()
        # Use the main config file instead of separate registry
        logger.info("Initializing MCPServerRegistry...")
        registry = MCPServerRegistry("config/tool_gating_config.yaml")
        
        # Register all backend servers from main config into the registry
        logger.info("Registering backend servers from main configuration...")
        for server_name, server_config in backend_servers.items():
            logger.info(f"Attempting to register server: {server_name}")
            result = await registry.register_server_from_config(server_name, server_config)
            if result["status"] == "success":
                logger.info(f"✓ Registered server: {server_name}")
            else:
                logger.warning(f"✗ Failed to register server {server_name}: {result['message']}")
        
        logger.info("Initializing AutoRegistrationService...")
        auto_registration = AutoRegistrationService(config_manager, client_manager, registry)
        logger.info("Initializing ErrorHandler...")
        error_handler = ErrorHandler()
        
        # Initialize lightweight services (non-blocking)
        logger.info("Initializing InMemoryToolRepository...")
        tool_repository = InMemoryToolRepository()
        logger.info("Initializing ProxyService...")
        proxy_service = ProxyService(client_manager, tool_repository)
        logger.info("Initializing FileWatcherService...")
        file_watcher = FileWatcherService(config_manager, registry)  # pass registry instead of client_manager

        # Store services in app state before spawning background work
        logger.info("Storing services in app state...")
        app.state.client_manager = client_manager
        app.state.proxy_service = proxy_service
        app.state.config_manager = config_manager
        app.state.file_watcher = file_watcher
        app.state.app_settings = app_settings
        app.state.registry = registry
        app.state.auto_registration = auto_registration
        app.state.error_handler = error_handler

        # Spawn background startup pipeline to avoid blocking bind/listen
        async def _background_startup():
            try:
                logger.info("Background startup: Starting automatic server registration pipeline...")
                registration_results = await auto_registration.register_all_servers(config)
                logger.info(
                    "Background startup: Registration complete - Successful: %d, Failed: %d, Skipped: %d",
                    len(registration_results.get('successful', [])),
                    len(registration_results.get('failed', [])),
                    len(registration_results.get('skipped', [])),
                )
                if registration_results.get("failed"):
                    for failed in registration_results["failed"]:
                        logger.warning("Background startup: Registration failed - %s: %s", failed.get('server'), failed.get('error'))
                # Discover tools after registration
                try:
                    logger.info("Background startup: Discovering all tools...")
                    await proxy_service.discover_all_tools()
                    logger.info("Background startup: Tool discovery complete")
                except Exception as e:
                    logger.exception(f"Background startup: Tool discovery failed: {e}")
                # Start file watcher if enabled (non-blocking long-running)
                if app_settings.config_watch_enabled:
                    try:
                        logger.info("Background startup: Starting file watcher...")
                        await file_watcher.start_watching(config_path)
                        logger.info("Background startup: File watcher running")
                    except asyncio.CancelledError:
                        logger.info("Background startup: File watcher task cancelled")
                        raise
                    except Exception as e:
                        logger.exception(f"Background startup: File watcher failed to start: {e}")
            except asyncio.CancelledError:
                logger.info("Background startup task cancelled")
                raise
            except Exception as e:
                logger.exception(f"Background startup pipeline error: {e}")

        logger.info("Spawning background startup tasks (fast start)...")
        startup_task = asyncio.create_task(_background_startup(), name="hmg_background_startup")
        app.state.startup_task = startup_task
         
        logger.info("✓ Proxy initialization complete")
        logger.info("Lifespan startup phase completed successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    logger.info("=== YIELDING CONTROL TO APPLICATION ===")
    yield
    
    # Shutdown
    logger.info("=== LIFESPAN SHUTDOWN PHASE STARTING ===")
    logger.info("Shutting down Hive MCP Gateway Proxy...")
    
    # Cancel background startup task if still running
    startup_task = getattr(app.state, "startup_task", None)
    if startup_task:
        try:
            logger.info("Cancelling background startup task...")
            startup_task.cancel()
            await asyncio.gather(startup_task, return_exceptions=True)
        except Exception as e:
            logger.warning(f"Error cancelling background startup task: {e}")

    # Stop file watcher
    if hasattr(app.state, "file_watcher"):
        logger.info("Stopping file watcher...")
        await app.state.file_watcher.stop_watching()
    
    # Disconnect all MCP servers
    if hasattr(app.state, "client_manager"):
        logger.info("Disconnecting all MCP servers...")
        await app.state.client_manager.disconnect_all()
    
    logger.info("Shutdown complete")
    logger.info("=== LIFESPAN SHUTDOWN PHASE COMPLETE ===")


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
    print("=== MAIN FUNCTION CALLED ===")
    logger.info("=== MAIN FUNCTION CALLED ===")
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
    print("=== IF __NAME__ == '__MAIN__' BLOCK EXECUTED ===")
    main()