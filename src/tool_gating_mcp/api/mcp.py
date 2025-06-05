"""MCP Server Management API endpoints"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..models.mcp_config import (
    AnthropicMCPConfig,
    MCPServerConfig,
    MCPServerRegistration,
    MCPToolDiscoveryRequest,
)
from ..services.mcp_connector import LocalMCPConnector, MCPConnector
from ..services.mcp_registry import MCPDiscoveryService, MCPServerRegistry
from .tools import get_tool_repository

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

# Singleton registry instance
_mcp_registry: MCPServerRegistry | None = None


def get_mcp_registry() -> MCPServerRegistry:
    """Get or create MCP registry instance"""
    global _mcp_registry
    if _mcp_registry is None:
        _mcp_registry = MCPServerRegistry()
    return _mcp_registry


async def get_discovery_service() -> MCPDiscoveryService:
    """Get discovery service instance"""
    repo = await get_tool_repository()
    return MCPDiscoveryService(tool_repo=repo)


@router.post("/servers/register", operation_id="register_server")
async def register_mcp_server(
    registration: MCPServerRegistration,
    registry: MCPServerRegistry = Depends(get_mcp_registry),  # noqa: B008
) -> dict[str, str]:
    """
    Register a new MCP server configuration.

    This endpoint allows AI assistants or users to easily add new MCP servers
    to the system by providing the configuration.
    """
    return await registry.register_server(registration)


@router.get("/servers", response_model=list[str], operation_id="list_servers")
async def list_mcp_servers(
    registry: MCPServerRegistry = Depends(get_mcp_registry),  # noqa: B008
) -> list[str]:
    """List all registered MCP servers"""
    return await registry.list_servers()


@router.get("/servers/{server_name}", operation_id="get_server")
async def get_mcp_server(
    server_name: str,
    registry: MCPServerRegistry = Depends(get_mcp_registry)  # noqa: B008
) -> dict[str, Any]:
    """Get configuration for a specific MCP server"""
    config = await registry.get_server(server_name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")

    return {"name": server_name, "config": config.model_dump()}


@router.delete("/servers/{server_name}", operation_id="remove_server")
async def remove_mcp_server(
    server_name: str,
    registry: MCPServerRegistry = Depends(get_mcp_registry)  # noqa: B008
) -> dict[str, str]:
    """Remove an MCP server from the registry"""
    return await registry.remove_server(server_name)


@router.post("/discover", operation_id="discover_mcp_tools")
async def discover_mcp_tools(
    request: MCPToolDiscoveryRequest,
    discovery: MCPDiscoveryService = Depends(get_discovery_service),  # noqa: B008
    registry: MCPServerRegistry = Depends(get_mcp_registry),  # noqa: B008
) -> dict[str, Any]:
    """
    Discover tools from an MCP server configuration.

    For AI assistants with MCP support: Follow the instructions to connect
    and discover tools, then register them.

    For API-based discovery: Uses Anthropic API if configured.
    """

    # Check if this is being called by an AI with MCP support
    user_agent = (
        request.headers.get("user-agent", "").lower()
        if hasattr(request, "headers")
        else ""
    )
    is_ai_assistant = any(ai in user_agent for ai in ["claude", "cursor", "copilot"])

    if is_ai_assistant:
        # Return instructions for the AI to follow
        return {
            "instructions": LocalMCPConnector.get_discovery_instructions(),
            "server_name": request.server_name,
            "config": request.config.model_dump(),
            "next_steps": [
                "1. Connect to the MCP server using the config",
                "2. Get the tool list",
                "3. Register each tool with POST /api/tools/register",
                "4. Include all tool details and appropriate metadata",
            ],
        }

    # Otherwise, try to use Anthropic API if available
    if settings.has_anthropic_key:
        connector = MCPConnector()
        try:
            mcp_tools = await connector.discover_via_anthropic_api(
                request.server_name, request.config
            )

            # Register the server config
            await registry.register_server(
                MCPServerRegistration(
                    name=request.server_name,
                    config=request.config,
                    description=f"MCP server: {request.server_name}",
                    estimated_tools=10
                )
            )

            # Discover and register tools
            result = await discovery.discover_and_register_tools(
                server_name=request.server_name,
                tools=mcp_tools,
                auto_register=request.auto_register,
            )

            return result

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to discover tools via API: {str(e)}",
                "suggestion": "Ensure Anthropic API key is configured in .env",
            }

    # No method available
    return {
        "status": "manual",
        "message": (
            "Tool discovery requires either an AI assistant with MCP "
            "support or Anthropic API key"
        ),
        "options": [
            "1. Use Claude Desktop or Cursor to discover tools",
            "2. Configure ANTHROPIC_API_KEY in .env file",
            "3. Manually register tools with POST /api/tools/register",
        ],
    }


@router.post("/analyze", operation_id="analyze_config")
async def analyze_mcp_config(
    config: dict[str, Any],
    discovery: MCPDiscoveryService = Depends(get_discovery_service),  # noqa: B008
) -> dict[str, Any]:
    """
    Analyze an MCP server configuration to understand its capabilities.

    This helps AI assistants understand what kind of tools a server might provide.
    """
    mcp_config = MCPServerConfig(**config)
    analysis = await discovery.analyze_mcp_config(mcp_config)

    return {"analysis": analysis, "recommendation": _generate_recommendation(analysis)}


@router.post("/ai/register-server", operation_id="ai_register_server")
async def ai_register_mcp_server(
    server_name: str,
    config: MCPServerConfig,
    tools: list[dict[str, Any]],
    registry: MCPServerRegistry = Depends(get_mcp_registry),  # noqa: B008
    discovery: MCPDiscoveryService = Depends(get_discovery_service),  # noqa: B008
) -> dict[str, Any]:
    """
    Streamlined endpoint for AI assistants to register an MCP server with all its tools.

    The AI should:
    1. Connect to the MCP server
    2. Get all available tools
    3. Call this endpoint with the complete information
    """

    # Register the server configuration
    registration = MCPServerRegistration(
        name=server_name,
        config=config,
        description=f"MCP server: {server_name}",
        estimated_tools=len(tools)
    )

    server_result = await registry.register_server(registration)

    if server_result["status"] != "success":
        return server_result

    # Convert and register all tools
    registered_tools = []
    for tool_data in tools:
        try:
            # Ensure tool has all required fields
            tool = {
                "id": f"{server_name}_{tool_data['name']}",
                "name": tool_data["name"],
                "description": tool_data["description"],
                "parameters": tool_data.get(
                    "inputSchema", tool_data.get("parameters", {})
                ),
                "server": server_name,
                "tags": tool_data.get("tags", []),
                "estimated_tokens": tool_data.get("estimated_tokens", 100),
            }

            # Add to repository
            from ..models.tool import Tool

            tool_model = Tool(**tool)
            await discovery.tool_repo.add_tool(tool_model)
            registered_tools.append(tool["name"])

        except Exception:
            # Log error but continue with other tools
            pass

    return {
        "status": "success",
        "message": f"Registered {server_name} with {len(registered_tools)} tools",
        "server": server_name,
        "tools_registered": registered_tools,
        "total_tools": len(registered_tools),
    }


@router.post("/anthropic/provision", operation_id="anthropic_provision")
async def provision_via_anthropic_api(config: AnthropicMCPConfig) -> dict[str, Any]:
    """
    Provision MCP servers directly via Anthropic API.

    This uses the new mcp_servers parameter in the Anthropic API
    to connect MCP servers without local installation.
    """

    # Construct the API request
    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    # Example request showing how to use MCP servers with Anthropic API
    example_body = {
        "model": "claude-3-opus-20240229",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": "List available tools from the connected MCP servers",
            }
        ],
        "mcp_servers": config.mcp_servers,
    }

    return {
        "status": "example",
        "message": "This shows how to use MCP servers with Anthropic API",
        "api_request_format": {
            "url": "https://api.anthropic.com/v1/messages",
            "headers": headers,
            "body": example_body,
        },
        "note": "The mcp_servers parameter allows direct MCP server connection via API",
    }


def _generate_sample_tools(server_name: str) -> list[dict[str, Any]]:
    """Generate sample tools based on server name (for demonstration)"""

    if "slack" in server_name.lower():
        return [
            {
                "name": "send_message",
                "description": "Send a message to Slack",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["channel", "text"],
                },
            },
            {
                "name": "list_channels",
                "description": "List Slack channels",
                "parameters": {"type": "object", "properties": {}},
            },
        ]
    elif "github" in server_name.lower():
        return [
            {
                "name": "create_issue",
                "description": "Create a GitHub issue",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string"},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["repo", "title"],
                },
            },
            {
                "name": "list_repos",
                "description": "List GitHub repositories",
                "parameters": {"type": "object", "properties": {}},
            },
        ]
    else:
        return [
            {
                "name": "example_tool",
                "description": f"Example tool from {server_name}",
                "parameters": {"type": "object", "properties": {}},
            }
        ]


def _generate_recommendation(analysis: dict[str, Any]) -> str:
    """Generate a recommendation based on analysis"""

    server_type = analysis.get("server_type", "unknown")
    capabilities = analysis.get("capabilities", [])

    if server_type == "slack":
        return (
            "This appears to be a Slack integration. "
            "Consider adding messaging and collaboration tags."
        )
    elif server_type == "database":
        return (
            "This appears to be a database integration. "
            "Consider adding data access and query tags."
        )
    elif server_type == "github":
        return (
            "This appears to be a GitHub integration. "
            "Consider adding version control and development tags."
        )
    else:
        return f"Server type: {server_type}. Capabilities: {', '.join(capabilities)}"
