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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models.mcp_config import MCPServerConfig, MCPServerRegistration
from ..services.mcp_registry import MCPDiscoveryService, MCPServerRegistry
from ..models.config import ServerStatus
from .tools import get_tool_repository

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

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


class ReconnectServerRequest(BaseModel):
    """Request to reconnect a server"""
    server_id: str


@router.post("/reconnect", operation_id="reconnect_server")
async def reconnect_server(
    request: ReconnectServerRequest,
    registry: MCPServerRegistry = Depends(get_mcp_registry),  # noqa: B008
) -> dict[str, Any]:
    """
    Reconnect a backend MCP server.
    
    This attempts to reconnect a disconnected server without restarting the entire service.
    """
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
        if hasattr(app.state, "client_manager"):
            client_manager = app.state.client_manager
            
            # Get server config
            server_config = await registry.get_server(request.server_id)
            if not server_config:
                raise HTTPException(status_code=500, detail=f"Server configuration not found for '{request.server_id}'")
            
            # Disconnect first if connected
            await client_manager.disconnect_server(request.server_id)
            
            # Reconnect
            result = await client_manager.connect_server(
                request.server_id, 
                server_config.model_dump() if hasattr(server_config, "model_dump") else server_config.dict()
            )
            
            if result["status"] == "success":
                # Update registry with tool count
                tools_count = result.get("tools_count", 0)
                registry.update_server_tool_count(request.server_id, tools_count)
                
                # Update connection status
                registry.set_server_connected(request.server_id, True)
                
                return {
                    "status": "success",
                    "message": f"Server '{request.server_id}' reconnected successfully",
                    "tools_count": tools_count
                }
            else:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to reconnect server '{request.server_id}': {result['message']}"
                )
        else:
            raise HTTPException(status_code=500, detail="Client manager not available")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reconnect server: {str(e)}")


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
                    description=getattr(status, 'description', None)
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
        
        server_result = await registry.register_server(registration)
        
        if server_result["status"] != "success":
            return server_result
        
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
            
            return {
                "status": "success",
                "message": f"Added {request.name} with {len(registered_tools)} tools",
                "server": request.name,
                "tools_discovered": registered_tools,
                "total_tools": len(registered_tools),
                "connection_result": connection_result
            }
        else:
            return {
                "status": "success", 
                "message": f"Server {request.name} registered (tool discovery pending initialization)",
                "server": request.name
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add server: {str(e)}")


# Note: Simplified to essential server management only.
# AI agents use add_server to expand capabilities with automatic tool discovery.