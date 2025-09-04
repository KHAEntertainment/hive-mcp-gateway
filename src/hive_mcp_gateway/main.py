# FastAPI application entry point
# Defines the main app instance and core routes
print("=== FILE IS BEING IMPORTED ===")

import logging
from logging.handlers import RotatingFileHandler
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
from .services.proxy_orchestrator import MCPProxyOrchestrator

# Configure logging: console + rotating file under run/backend.log
_log_formatter = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.DEBUG, format=_log_formatter)
try:
    from pathlib import Path
    proj_root = Path(__file__).resolve().parents[2]
    run_dir = proj_root / 'run'
    run_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(run_dir / 'backend.log', maxBytes=2_000_000, backupCount=3)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_log_formatter))
    logging.getLogger().addHandler(file_handler)
except Exception:
    # best-effort: continue with console logging only
    pass
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
        # Initialize gating service (skeleton) and honor default policy from settings
        from .services.gating_service import GatingService
        gating_service = GatingService(default_policy=getattr(app_settings, 'default_policy', 'deny'))
        logger.info("Initializing FileWatcherService...")
        file_watcher = FileWatcherService(config_manager, registry)  # pass registry instead of client_manager

        # Optionally manage an embedded MCP Proxy for stdio servers
        proxy_url = getattr(app_settings, "proxy_url", None)
        if getattr(app_settings, "manage_proxy", False):
            try:
                from pathlib import Path
                run_dir = Path(__file__).resolve().parents[2] / "run"
                orchestrator = MCPProxyOrchestrator(config_path, run_dir)
                proxy_conf = orchestrator.build_proxy_config(config)
                conf_file = orchestrator.write_config_file(proxy_conf)
                if orchestrator.try_start(conf_file):
                    proxy_url = orchestrator.base_url
                    app_settings.proxy_url = proxy_url
                    logger.info(f"Managed MCP Proxy started at {proxy_url}")
                else:
                    logger.warning("MCP Proxy could not be started automatically (binary/docker not found)")
                app.state.proxy_orchestrator = orchestrator
            except Exception as e:
                logger.warning(f"Failed to start managed MCP Proxy: {e}")

        # Store services in app state before spawning background work
        logger.info("Storing services in app state...")
        app.state.client_manager = client_manager
        app.state.proxy_service = proxy_service
        app.state.gating = gating_service
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

        # Write PID for external managers/GUI
        try:
            from pathlib import Path
            proj_root = Path(__file__).resolve().parents[2]
            run_dir = proj_root / 'run'
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / 'backend.pid').write_text(str(os.getpid()), encoding='utf-8')
        except Exception:
            pass

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
    # Remove PID file
    try:
        from pathlib import Path
        proj_root = Path(__file__).resolve().parents[2]
        pid_path = proj_root / 'run' / 'backend.pid'
        if pid_path.exists():
            pid_path.unlink()
    except Exception:
        pass
    # Stop managed proxy
    orchestrator = getattr(app.state, "proxy_orchestrator", None)
    if orchestrator:
        try:
            logger.info("Stopping managed MCP Proxy...")
            orchestrator.stop()
        except Exception:
            pass
    
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
        configured_port = int(os.getenv('PORT', config.tool_gating.port))

        # Determine an available port with fallback: 8001 default, else 8002-8025
        def _is_port_busy(h: str, p: int) -> bool:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                return s.connect_ex(("127.0.0.1" if h in ("0.0.0.0", "::") else h, p)) == 0

        port = configured_port
        # Build a set of ports reserved by configured upstream servers (e.g., exa at 8002)
        reserved_ports: set[int] = set()
        try:
            import re
            from urllib.parse import urlparse
            for name, srv in config.backend_mcp_servers.items():
                url = getattr(srv, 'url', None)
                if url:
                    try:
                        parsed = urlparse(url)
                        if parsed.port:
                            reserved_ports.add(int(parsed.port))
                    except Exception:
                        # Best-effort: fallback regex for :<port>
                        m = re.search(r":(\d+)", str(url))
                        if m:
                            reserved_ports.add(int(m.group(1)))
        except Exception:
            pass

        fallback_ports: list[int] = []
        # If user configured something other than 8001, still try that first, then our policy
        if port != 8001:
            fallback_ports.append(8001)
        # Add range 8002-8025 as requested, excluding reserved upstream ports
        for p in range(8002, 8026):
            if p not in reserved_ports:
                fallback_ports.append(p)

        # If configured port is reserved by upstream URLs, skip it immediately
        if port in reserved_ports:
            logger.warning(f"Configured port {port} is reserved by upstream servers; selecting fallback port")
            selected = None
            # Try 8001 first if not reserved
            if 8001 not in reserved_ports and not _is_port_busy(host, 8001):
                selected = 8001
            else:
                for fp in fallback_ports:
                    if not _is_port_busy(host, fp):
                        selected = fp
                        break
            if selected is None:
                raise RuntimeError("No available port found (avoiding reserved upstream ports)")
            logger.info(f"Selected available port: {selected}")
            port = selected
        elif _is_port_busy(host, port):
            logger.warning(
                f"Configured port {port} is busy; attempting fallback within 8002-8025"
            )
            selected = None
            for fp in fallback_ports:
                if not _is_port_busy(host, fp):
                    selected = fp
                    break
            if selected is None:
                raise RuntimeError("No available port found in range 8001,8002-8025")
            logger.info(f"Selected available port: {selected}")
            port = selected
        log_level = os.getenv('LOG_LEVEL', config.tool_gating.log_level).lower()
        
        # Persist the selected port for GUI consumption (best-effort)
        try:
            from pathlib import Path
            proj_root = Path(__file__).resolve().parents[2]
            run_dir = proj_root / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "hmg_port").write_text(str(port), encoding="utf-8")
        except Exception:
            pass

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
