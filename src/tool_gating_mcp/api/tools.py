# Tool API endpoints
# Implements discovery, provisioning, and execution endpoints

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends

from ..api.models import (
    MCPToolDefinition,
    ToolDiscoveryRequest,
    ToolDiscoveryResponse,
    ToolMatchResponse,
    ToolProvisionRequest,
    ToolProvisionResponse,
)
from ..models.tool import Tool
from ..services.discovery import DiscoveryService
from ..services.gating import GatingService

router = APIRouter(prefix="/api/tools", tags=["tools"])


# Singleton repository instance
_tool_repository: Any = None


async def get_tool_repository() -> Any:
    """Get or create tool repository instance."""
    global _tool_repository
    if _tool_repository is None:
        from ..services.repository import InMemoryToolRepository
        from ..services.mcp_registry import MCPServerRegistry

        _tool_repository = InMemoryToolRepository()
        
        # Load tools from registered MCP servers instead of demo tools
        # This allows the system to start empty and tools to be added dynamically
        # via the MCP server registration endpoints
        
        # Optional: Pre-load some default servers
        # registry = MCPServerRegistry()
        # await registry.load_default_servers()
        
    return _tool_repository


# Dependency injection for services
async def get_discovery_service() -> DiscoveryService:
    """Get discovery service instance."""
    repo = await get_tool_repository()
    return DiscoveryService(tool_repo=repo)


async def get_gating_service() -> GatingService:
    """Get gating service instance."""
    repo = await get_tool_repository()
    return GatingService(tool_repo=repo)


def get_current_user() -> dict[str, str]:
    """Get current user context."""
    # Placeholder for authentication
    return {"user_id": "test-user"}


@router.post("/discover", response_model=ToolDiscoveryResponse)
async def discover_tools(
    request: ToolDiscoveryRequest,
    discovery_service: DiscoveryService = Depends(get_discovery_service),  # noqa: B008
) -> ToolDiscoveryResponse:
    """Discover relevant tools based on query and context."""
    tools = await discovery_service.search_tools(
        query=request.query,
        tags=request.tags,
        top_k=request.limit or 10,
    )

    # Convert to response format
    tool_matches = [
        ToolMatchResponse(
            tool_id=match.tool.id,
            name=match.tool.name,
            description=match.tool.description,
            score=match.score,
            matched_tags=match.matched_tags,
            estimated_tokens=match.tool.estimated_tokens,
            server=match.tool.server,
        )
        for match in tools
    ]

    return ToolDiscoveryResponse(
        tools=tool_matches, query_id=str(uuid.uuid4()), timestamp=datetime.now()
    )


@router.post("/provision", response_model=ToolProvisionResponse)
async def provision_tools(
    request: ToolProvisionRequest,
    gating_service: GatingService = Depends(get_gating_service),  # noqa: B008
    user: dict[str, str] = Depends(get_current_user),  # noqa: B008
) -> ToolProvisionResponse:
    """Provision tools for LLM consumption based on selection criteria."""
    # Apply token budget if provided
    if request.context_tokens:
        gating_service.max_tokens = request.context_tokens

    # Apply gating logic
    selected_tools = await gating_service.select_tools(
        tool_ids=request.tool_ids, max_tools=request.max_tools, user_context=user
    )

    # Format for MCP
    mcp_tools = await gating_service.format_for_mcp(selected_tools)

    # Convert to response format
    tool_defs = [
        MCPToolDefinition(
            name=tool.name,
            description=tool.description,
            parameters=tool.inputSchema,
            token_count=100,  # Simplified for now
            server=getattr(selected_tools[i], "server", None),
        )
        for i, tool in enumerate(mcp_tools)
    ]
    
    # Update proxy service with provisioned tools
    from ..main import app
    if hasattr(app.state, "proxy_service"):
        for tool in selected_tools:
            app.state.proxy_service.provision_tool(tool.id)

    return ToolProvisionResponse(
        tools=tool_defs,
        metadata={
            "total_tokens": sum(t.token_count for t in tool_defs),
            "gating_applied": True,
        },
    )


@router.post("/register")
async def register_tool(
    tool: Tool,
    tool_repo: Any = Depends(get_tool_repository),  # noqa: B008
) -> dict[str, str]:
    """Register a new tool in the system."""
    await tool_repo.add_tool(tool)
    return {"status": "success", "tool_id": tool.id}


@router.delete("/clear")
async def clear_tools(
    tool_repo: Any = Depends(get_tool_repository),  # noqa: B008
) -> dict[str, str]:
    """Clear all tools from the repository."""
    tool_repo._tools.clear()
    return {"status": "success", "message": "All tools cleared"}


# Note: Tool execution proxy endpoint removed
# The tool gating system's responsibility is to provide tool definitions,
# not to execute them. LLMs should execute tools directly with MCP servers.
