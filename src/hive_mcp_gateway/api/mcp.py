"""
⚠️ Semi-Working/Incomplete Components:

Credential Management:
- Basic ENV/Secrets storage implemented
- Missing auto-detection feature for credentials in MCP configs
- Incomplete mapping between credentials and MCP entries
- UI needs descriptive text about secure OS storage

LLM Configuration:
- UI needs complete overhaul (based on design files)
- Missing tabbed interface for CLI vs API authentication
- Provider selection with quick preset buttons not implemented
- Path override sections incomplete

Auto Start Manager:
- Button shows "Auto Start Manager is not Available"
- Cross-platform auto-start functionality not implemented
- No persistence of auto-start settings

Client Configuration Window:
- Previously missing feature now partially implemented
- Client detection for popular IDEs working
- Configuration generation functional
- Needs integration with main window redesign

Branding and Theming:
- Inconsistent branding ("Tool Gating MCP" vs "Hive MCP Gateway")
- Current theme doesn't match Hive Night design specifications
- Logo assets may need regeneration (green vs black/yellow)
"""

"""Simplified MCP Server Management - Essential functionality only"""

from typing import Any, List, Dict
import os
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List as _List

from ..models.mcp_config import MCPServerConfig, MCPServerRegistration
from ..models.config import BackendServerConfig
from ..services.mcp_registry import MCPDiscoveryService, MCPServerRegistry
from ..models.config import ServerStatus
from .tools import get_tool_repository

router = APIRouter(prefix="/api/mcp", tags=["mcp"])
logger = logging.getLogger(__name__)

# Singleton registry instance
_mcp_registry: MCPServerRegistry | None = None


def get_mcp_registry() -> MCPServerRegistry:
    """Get the process-wide MCP registry, preferring the FastAPI app's instance."""
    global _mcp_registry
    try:
        # Prefer the registry created during app startup (shared state)
        from ..main import app  # noqa: WPS433 (import inside function by design)
        if hasattr(app, "state") and getattr(app.state, "registry", None) is not None:
            return app.state.registry  # type: ignore[return-value]
    except Exception:
        # If app import/state access fails, fall back to module-level singleton
        pass
    if _mcp_registry is None:
        _mcp_registry = MCPServerRegistry()
    return _mcp_registry


async def get_discovery_service() -> MCPDiscoveryService:
    """Get discovery service instance"""
    repo = await get_tool_repository()
    return MCPDiscoveryService(tool_repo=repo)


class AddServerRequest(BaseModel):
    """Request to add a new MCP server with auto-discovery"""
    name: str
    config: MCPServerConfig
    description: str | None = None


class ServerStatusResponse(BaseModel):
    """Response model for server status"""
    name: str
    enabled: bool
    connected: bool
    tool_count: int
    health_status: str
    last_seen: str | None
    error_message: str | None
    description: str | None
    
    # New state fields
    discovery_state: str = "idle"
    discovery_started_at: str | None = None
    discovery_finished_at: str | None = None
    last_discovery_error: str | None = None
    last_discovery_error_at: str | None = None
    connection_state: str = "disconnected"
    connection_path: str = "unknown"


class ReconnectServerRequest(BaseModel):
    """Request to reconnect a server"""
    server_id: str


class DiscoverToolsRequest(BaseModel):
    """Request to force tool discovery for a server"""
    server_id: str


class ProxyStatusResponse(BaseModel):
    running: bool
    managed: bool
    base_url: str | None


class LogsResponse(BaseModel):
    lines: _List[str]


@router.post("/reconnect", operation_id="reconnect_server")
async def reconnect_server(
    request: ReconnectServerRequest,
    registry: MCPServerRegistry = Depends(get_mcp_registry),  # noqa: B008
    wait_for_discovery: bool = True,
    discovery_timeout: float = 30.0
) -> dict[str, Any]:
    """
    Reconnect a backend MCP server and optionally wait for tool discovery.
    
    This attempts to reconnect a disconnected server and discover its tools.
    """
    from datetime import datetime
    import asyncio
    
    try:
        from ..main import app
        
        # Check if server exists
        backend_servers = registry.list_active_servers()
        if request.server_id not in backend_servers:
            raise HTTPException(status_code=404, detail=f"Server '{request.server_id}' not found")
        
        # Get server status
        server_status = registry.get_server_status(request.server_id)
        if not server_status:
            raise HTTPException(status_code=500, detail=f"Server status not found for '{request.server_id}'")
        
        # Check if the server is enabled
        if not server_status.enabled:
            raise HTTPException(status_code=400, detail=f"Server '{request.server_id}' is disabled. Enable it first.")
        
        # Attempt to reconnect the server through the client manager
        if not hasattr(app.state, "client_manager"):
            raise HTTPException(status_code=500, detail="Client manager not available")
            
        client_manager = app.state.client_manager
        
        # Get server config
        server_config = registry.get_server(request.server_id)
        if not server_config:
            raise HTTPException(status_code=500, detail=f"Server configuration not found for '{request.server_id}'")
        
        # Update connection state
        registry.set_connection_state(request.server_id, "connecting")
        registry.set_discovery_state(request.server_id, "pending")
        
        # Disconnect first if connected
        await client_manager.disconnect_server(request.server_id)
        
        # Reconnect
        connect_result = await client_manager.connect_server(
            request.server_id, 
            server_config.model_dump() if hasattr(server_config, "model_dump") else server_config.dict()
        )
        
        if connect_result["status"] != "success":
            registry.set_connection_state(request.server_id, "error")
            registry.set_server_error(request.server_id, connect_result.get("message", "Connection failed"))
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to reconnect server '{request.server_id}': {connect_result['message']}"
            )
        
        # Update connection success
        registry.set_server_connected(request.server_id, True)
        registry.set_connection_state(request.server_id, "connected", 
                                     path=connect_result.get("connection_path", "unknown"))
        
        # Wait for tool discovery if requested
        tools_count = 0
        discovery_error = None
        
        if wait_for_discovery:
            try:
                # Start discovery
                registry.set_discovery_state(request.server_id, "running", 
                                           started_at=datetime.now().isoformat())
                
                # Perform discovery with timeout
                discovery_result = await asyncio.wait_for(
                    client_manager.discover_tools_now(request.server_id),
                    timeout=discovery_timeout
                )
                
                if discovery_result["status"] == "success":
                    tools_count = discovery_result.get("tools_count", 0)
                    registry.update_server_tool_count(request.server_id, tools_count)
                    registry.set_discovery_state(request.server_id, "success", 
                                               finished_at=datetime.now().isoformat())
                    registry.clear_last_error(request.server_id)
                else:
                    discovery_error = discovery_result.get("message", "Discovery failed")
                    registry.set_discovery_state(request.server_id, "error",
                                               finished_at=datetime.now().isoformat())
                    registry.set_last_discovery_error(request.server_id, discovery_error,
                                                     when=datetime.now().isoformat())
                    
            except asyncio.TimeoutError:
                discovery_error = f"Discovery timed out after {discovery_timeout}s"
                registry.set_discovery_state(request.server_id, "timeout",
                                           finished_at=datetime.now().isoformat())
                registry.set_last_discovery_error(request.server_id, discovery_error,
                                                 when=datetime.now().isoformat())
            except Exception as e:
                discovery_error = str(e)
                registry.set_discovery_state(request.server_id, "error",
                                           finished_at=datetime.now().isoformat())
                registry.set_last_discovery_error(request.server_id, discovery_error,
                                                 when=datetime.now().isoformat())
        else:
            # Just get current tool count if not waiting
            tools_count = connect_result.get("tools_count", 0)
            registry.update_server_tool_count(request.server_id, tools_count)
        
        # Get updated status
        final_status = registry.get_server_status(request.server_id)
        
        return {
            "status": "success",
            "message": f"Server '{request.server_id}' reconnected successfully",
            "server_id": request.server_id,
            "connection_state": final_status.connection_state if final_status else "unknown",
            "connection_path": final_status.connection_path if final_status else "unknown",
            "discovery_state": final_status.discovery_state if final_status else "unknown",
            "tools_count": tools_count,
            "discovery_error": discovery_error
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reconnect server: {str(e)}")


@router.post("/register_all", operation_id="register_all_servers")
async def register_all_servers() -> dict[str, Any]:
    """Force the background registration pipeline to run now and return a summary."""
    try:
        from ..main import app
        if not hasattr(app.state, "auto_registration"):
            raise HTTPException(status_code=500, detail="AutoRegistrationService not available")

        config_manager = getattr(app.state, "config_manager", None)
        if not config_manager:
            raise HTTPException(status_code=500, detail="Config manager not available")

        config = config_manager.load_config()
        results = await app.state.auto_registration.register_all_servers(config)
        return {"status": "ok", "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register servers: {str(e)}")


@router.post("/discover_tools", operation_id="discover_tools_now")
async def discover_tools_now(
    request: DiscoverToolsRequest,
    registry: MCPServerRegistry = Depends(get_mcp_registry),  # noqa: B008
) -> dict[str, Any]:
    """Force immediate tool discovery for a server and update registry."""
    from datetime import datetime
    
    try:
        from ..main import app
        if not hasattr(app.state, "client_manager"):
            raise HTTPException(status_code=500, detail="Client manager not available")

        client_manager = app.state.client_manager
        
        # Ensure server exists in registry
        if request.server_id not in registry.list_active_servers():
            raise HTTPException(status_code=404, detail=f"Server '{request.server_id}' not found")
        
        # Get current server status
        server_status = registry.get_server_status(request.server_id)
        if not server_status:
            raise HTTPException(status_code=500, detail=f"Server status not found for '{request.server_id}'")
        
        # Check connection state and connect if needed
        if server_status.connection_state in ["disconnected", "error"]:
            logger.info(f"Server {request.server_id} is {server_status.connection_state}, attempting connection first")
            
            # Get server config and connect
            server_config = registry.get_server(request.server_id)
            if not server_config:
                raise HTTPException(status_code=500, detail=f"Server configuration not found")
            
            registry.set_connection_state(request.server_id, "connecting")
            connect_result = await client_manager.connect_server(
                request.server_id,
                server_config.model_dump() if hasattr(server_config, "model_dump") else server_config.dict()
            )
            
            if connect_result["status"] != "success":
                registry.set_connection_state(request.server_id, "error")
                registry.set_server_error(request.server_id, connect_result.get("message"))
                raise HTTPException(status_code=500, detail=f"Failed to connect: {connect_result.get('message')}")
            
            registry.set_server_connected(request.server_id, True)
            registry.set_connection_state(request.server_id, "connected",
                                        path=connect_result.get("connection_path", "unknown"))
        
        # Update discovery state
        registry.set_discovery_state(request.server_id, "running",
                                    started_at=datetime.now().isoformat())
        
        # Perform discovery
        try:
            result = await client_manager.discover_tools_now(request.server_id)
            
            if result.get("status") == "success":
                tools_count = result.get("tools_count", 0)
                registry.update_server_tool_count(request.server_id, tools_count)
                registry.set_discovery_state(request.server_id, "success",
                                           finished_at=datetime.now().isoformat())
                registry.clear_last_error(request.server_id)
                
                # Get updated status
                st = registry.get_server_status(request.server_id)
                
                return {
                    "status": "success",
                    "server": request.server_id,
                    "tools_count": tools_count,
                    "connected": bool(st.connected) if st else False,
                    "connection_state": st.connection_state if st else "unknown",
                    "connection_path": st.connection_path if st else "unknown",
                    "discovery_state": st.discovery_state if st else "unknown"
                }
            else:
                error_msg = result.get("message", "Discovery failed")
                registry.set_discovery_state(request.server_id, "error",
                                           finished_at=datetime.now().isoformat())
                registry.set_last_discovery_error(request.server_id, error_msg,
                                                 when=datetime.now().isoformat())
                raise HTTPException(status_code=500, detail=error_msg)
                
        except Exception as e:
            registry.set_discovery_state(request.server_id, "error",
                                       finished_at=datetime.now().isoformat())
            registry.set_last_discovery_error(request.server_id, str(e),
                                            when=datetime.now().isoformat())
            raise
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to discover tools: {str(e)}")


@router.get("/proxy_status", response_model=ProxyStatusResponse, operation_id="proxy_status")
async def proxy_status() -> ProxyStatusResponse:
    """Return current MCP Proxy status from orchestrator/settings."""
    try:
        from ..main import app
        app_settings = getattr(app.state, "app_settings", None)
        orchestrator = getattr(app.state, "proxy_orchestrator", None)
        base = getattr(app_settings, "proxy_url", None) if app_settings else None
        managed = bool(getattr(app_settings, "manage_proxy", False)) if app_settings else False
        running = bool(base)
        # Additional signal: if orchestrator exists and has a live process
        try:
            if orchestrator and getattr(orchestrator, "proc", None) is not None:
                running = running and (orchestrator.proc.poll() is None)
        except Exception:
            pass
        return ProxyStatusResponse(running=running, managed=managed, base_url=base)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get proxy status: {str(e)}")


@router.get("/logs", response_model=LogsResponse, operation_id="tail_logs")
async def tail_logs(lines: int = 200) -> LogsResponse:
    """Tail the backend log file (run/backend.log)."""
    try:
        from pathlib import Path
        from ..main import app
        # Determine run dir relative to project root
        proj_root = Path(__file__).resolve().parents[3]
        log_path = proj_root / 'run' / 'backend.log'
        if not log_path.exists():
            return LogsResponse(lines=[])
        content = log_path.read_text(encoding='utf-8', errors='ignore').splitlines()
        if lines > 0 and len(content) > lines:
            content = content[-lines:]
        return LogsResponse(lines=content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {str(e)}")


@router.get("/debug/registry", operation_id="debug_registry")
async def debug_registry(
    registry: MCPServerRegistry = Depends(get_mcp_registry),  # noqa: B008
) -> list[dict[str, Any]]:
    """Return raw registry status for debugging."""
    try:
        names = registry.list_active_servers()
        out: list[dict[str, Any]] = []
        for n in names:
            st = registry.get_server_status(n)
            if st:
                out.append({
                    "name": st.name,
                    "enabled": st.enabled,
                    "connected": st.connected,
                    "tool_count": st.tool_count,
                    "health_status": st.health_status,
                    "error_message": st.error_message,
                })
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read registry: {str(e)}")


@router.get("/servers", operation_id="list_servers")
async def list_servers(
    registry: MCPServerRegistry = Depends(get_mcp_registry)  # noqa: B008
) -> List[ServerStatusResponse]:
    """
    List all registered MCP servers with their status information.
    """
    try:
        server_names = registry.list_active_servers()
        server_statuses = []
        
        for name in server_names:
            status = registry.get_server_status(name)
            if status:
                server_statuses.append(ServerStatusResponse(
                    name=status.name,
                    enabled=status.enabled,
                    connected=status.connected,
                    tool_count=status.tool_count,
                    health_status=status.health_status,
                    last_seen=status.last_seen,
                    error_message=status.error_message,
                    description=getattr(status, 'description', None),
                    # Include all new state fields
                    discovery_state=getattr(status, 'discovery_state', 'idle'),
                    discovery_started_at=getattr(status, 'discovery_started_at', None),
                    discovery_finished_at=getattr(status, 'discovery_finished_at', None),
                    last_discovery_error=getattr(status, 'last_discovery_error', None),
                    last_discovery_error_at=getattr(status, 'last_discovery_error_at', None),
                    connection_state=getattr(status, 'connection_state', 'disconnected'),
                    connection_path=getattr(status, 'connection_path', 'unknown')
                ))
        
        return server_statuses
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list servers: {str(e)}")


@router.post("/add_server", operation_id="add_server")
async def add_server(
    request: AddServerRequest,
    registry: MCPServerRegistry = Depends(get_mcp_registry),  # noqa: B008
    discovery: MCPDiscoveryService = Depends(get_discovery_service),  # noqa: B008
) -> dict[str, Any]:
    """
    Add a new MCP server with automatic tool discovery.
    
    This is the essential endpoint for AI agents to expand capabilities.
    It combines server registration + tool discovery in one step.
    """
    try:
        # Register the server
        registration = MCPServerRegistration(
            name=request.name,
            config=request.config,
            description=request.description or f"MCP server: {request.name}",
            estimated_tools=10
        )
        # Persist to main configuration so the proxy orchestrator can hot-reload
        try:
            from ..main import app as _app
            cfg_mgr = getattr(_app.state, "config_manager", None)
            if cfg_mgr:
                bcfg = BackendServerConfig(
                    type="stdio",
                    via="proxy",
                    command=request.config.command,
                    args=request.config.args,
                    env=request.config.env,
                    enabled=True,
                    description=registration.description,
                )
                cfg_mgr.add_backend_server(request.name, bcfg)
                # Hot-apply to proxy orchestrator immediately
                try:
                    orch = getattr(_app.state, "proxy_orchestrator", None)
                    if orch:
                        orch.update_config(cfg_mgr.load_config())
                except Exception:
                    pass
        except Exception:
            # Non-fatal; continue
            pass

        server_result = await registry.register_server(registration)
        
        if server_result["status"] != "success":
            return server_result
        
        # Feature flag (no-op placeholder): LLM-assisted tool enumeration path
        # Enable by setting HMG_ENABLE_LLM_ENUM=1 to test later.
        # This currently does not alter behavior; it only logs intent and annotates response.
        llm_enum_enabled = os.getenv("HMG_ENABLE_LLM_ENUM", "0") not in (None, "", "0", "false", "False")
        if llm_enum_enabled:
            logger.info("LLM-assisted enumeration is ENABLED (placeholder). Deterministic enumeration remains in effect.")
            # TODO: Wire LLM enumeration (services.mcp_connector.discover_via_anthropic_api)
            # and merge/enrich results with deterministic discovery when ready.

        # Auto-discover and register tools
        from ..main import app
        if hasattr(app.state, "client_manager"):
            client_manager = app.state.client_manager
            connection_result = await client_manager.connect_server(request.name, request.config.model_dump())
            
            # Register tools in repository
            tools = client_manager.server_tools.get(request.name, [])
            registered_tools = []
            
            for tool in tools:
                try:
                    from ..models.tool import Tool
                    tool_model = Tool(
                        id=f"{request.name}_{getattr(tool, 'name', 'unknown')}",
                        name=getattr(tool, 'name', 'unknown'),
                        description=getattr(tool, 'description', 'No description available'),
                        parameters=getattr(tool, 'inputSchema', getattr(tool, 'parameters', {})),
                        server=request.name,
                        tags=[],
                        estimated_tokens=100
                    )
                    await discovery.tool_repo.add_tool(tool_model)
                    registered_tools.append(getattr(tool, 'name', 'unknown'))
                except Exception:
                    # Continue with other tools if one fails
                    pass
            
            # Update tool count in server status
            registry.update_server_tool_count(request.name, len(registered_tools))
            
            response = {
                "status": "success",
                "message": f"Added {request.name} with {len(registered_tools)} tools",
                "server": request.name,
                "tools_discovered": registered_tools,
                "total_tools": len(registered_tools),
                "connection_result": connection_result,
            }
            if llm_enum_enabled:
                response["llm_enumeration"] = "enabled_noop"
            return response
        else:
            response = {
                "status": "success", 
                "message": f"Server {request.name} registered (tool discovery pending initialization)",
                "server": request.name
            }
            if llm_enum_enabled:
                response["llm_enumeration"] = "enabled_noop"
            return response
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add server: {str(e)}")


# Note: Simplified to essential server management only.
# AI agents use add_server to expand capabilities with automatic tool discovery.
