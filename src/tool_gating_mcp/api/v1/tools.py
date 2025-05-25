# Tool API endpoints
# Implements discovery, provisioning, and execution endpoints

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...api.models import (
    MCPToolDefinition,
    ToolDiscoveryRequest,
    ToolDiscoveryResponse,
    ToolExecutionRequest,
    ToolExecutionResponse,
    ToolMatchResponse,
    ToolProvisionRequest,
    ToolProvisionResponse,
)
from ...services.discovery import DiscoveryService
from ...services.gating import GatingService
from ...services.proxy import ProxyService

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


# Singleton repository instance
_tool_repository: Any = None


async def get_tool_repository() -> Any:
    """Get or create tool repository instance."""
    global _tool_repository
    if _tool_repository is None:
        from ...services.repository import InMemoryToolRepository

        _tool_repository = InMemoryToolRepository()
        await _tool_repository.populate_demo_tools()
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


def get_proxy_service() -> ProxyService:
    """Get proxy service instance."""
    return ProxyService()


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
    tools = await discovery_service.find_relevant_tools(
        query=request.query,
        context=request.context,
        tags=request.tags,
        limit=request.limit or 10,
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
        )
        for tool in mcp_tools
    ]

    return ToolProvisionResponse(
        tools=tool_defs,
        metadata={
            "total_tokens": sum(t.token_count for t in tool_defs),
            "gating_applied": True,
        },
    )


@router.post("/execute/{tool_id}", response_model=ToolExecutionResponse)
async def execute_tool(
    tool_id: str,
    request: ToolExecutionRequest,
    proxy_service: ProxyService = Depends(get_proxy_service),  # noqa: B008
    user: dict[str, str] = Depends(get_current_user),  # noqa: B008
) -> ToolExecutionResponse:
    """Execute a tool by proxying to the appropriate MCP server."""
    try:
        result = await proxy_service.execute_tool(
            tool_id=tool_id, params=request.parameters, user_context=user
        )
        return ToolExecutionResponse(result=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        return ToolExecutionResponse(result=None, error=str(e))
