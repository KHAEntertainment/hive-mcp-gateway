"""MCP Server Registry Service with enhanced configuration support"""

import json
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

import aiofiles

from ..models.mcp_config import (
    MCPServerConfig,
    MCPServerRegistration,
    MCPToolSchema,
)
from ..models.config import (
    BackendServerConfig,
    ServerStatus,
)

logger = logging.getLogger(__name__)


class MCPServerRegistry:
    """Manages MCP server configurations with support for enhanced features"""

    def __init__(self, config_path: str = "config/tool_gating_config.yaml"):
        # Use provided path as-is (absolute or relative to CWD)
        self.config_path = Path(config_path)
        logger.info(f"Attempting to load MCP server configuration from: {self.config_path}")
        self._servers: Dict[str, MCPServerConfig] = {}
        self._server_status: Dict[str, ServerStatus] = {}
        self._connected_servers: set[str] = set()
        self.load_servers()

    def load_servers(self):
        try:
            with open(self.config_path, "r") as f:
                config_data = yaml.safe_load(f)
                
                # Correctly iterate over the dictionary items
                server_configs_raw = config_data.get("backendMcpServers", {})
                server_configs = {name: BackendServerConfig(**data) for name, data in server_configs_raw.items()}
                
                self._servers.clear()
                self._server_status.clear()

                for name, config in server_configs.items():
                    mcp_config = self._convert_backend_config_to_mcp(config)
                    self._servers[name] = mcp_config
                    
                    server_status = ServerStatus(
                        name=name,
                        enabled=config.enabled,
                        connected=False,
                        health_status="unknown",
                        tool_count=0
                    )
                    if config.metadata:
                        if config.metadata.tags:
                            server_status.tags = config.metadata.tags
                    self._server_status[name] = server_status

                logger.info(f"Successfully loaded {len(self._servers)} MCP servers.")
                logger.info(f"Loaded server names: {list(self._servers.keys())}")

        except FileNotFoundError:
            logger.error(f"MCP server configuration file not found at: {self.config_path}")
            self._servers = {}
            self._server_status = {}
        except Exception as e:
            logger.error(f"Error loading MCP server configuration: {e}")
            self._servers = {}
            self._server_status = {}

    def get_server(self, server_name: str) -> Optional[MCPServerConfig]:
        """Get a server configuration by name"""
        return self._servers.get(server_name)

    async def list_servers(self) -> list[str]:
        """List all registered server names"""
        return list(self._servers.keys())

    async def remove_server(self, name: str) -> dict[str, str]:
        """Remove a server from the registry"""
        if name not in self._servers:
            return {"status": "error", "message": f"Server '{name}' not found"}

        del self._servers[name]
        if name in self._server_status:
            del self._server_status[name]
        self._connected_servers.discard(name)
        
        return {"status": "success", "message": f"Server '{name}' removed successfully"}

    async def update_server(self, name: str, config: MCPServerConfig) -> dict[str, str]:
        """Update an existing server configuration"""
        if name not in self._servers:
            return {"status": "error", "message": f"Server '{name}' not found"}

        self._servers[name] = config
        
        return {"status": "success", "message": f"Server '{name}' updated successfully"}

    # Enhanced methods for dynamic configuration management with health checks
    
    async def register_server_from_config(self, name: str, config: BackendServerConfig) -> dict[str, Any]:
        """Register a server from BackendServerConfig format with enhanced status tracking."""
        try:
            # Convert BackendServerConfig to MCPServerConfig
            mcp_config = self._convert_backend_config_to_mcp(config)
            
            # Register the server
            self._servers[name] = mcp_config
            
            # Update status with enhanced information
            server_status = ServerStatus(
                name=name,
                enabled=config.enabled,
                connected=False,
                health_status="unknown", # Ensure this is one of the literal values
                tool_count=0
            )
            
            # Add metadata if available
            if config.metadata:
                if config.metadata.tags:
                    server_status.tags = config.metadata.tags
            
            self._server_status[name] = server_status
            
            logger.info(f"Registered server from config: {name}")
            
            return {
                "status": "success",
                "message": f"Server '{name}' registered successfully",
                "server_name": name
            }
            
        except Exception as e:
            logger.error(f"Failed to register server {name}: {e}")
            return {
                "status": "error",
                "message": f"Failed to register server '{name}': {str(e)}",
                "server_name": name
            }
    
    async def unregister_server(self, name: str) -> dict[str, Any]:
        """Unregister a server and remove from active connections."""
        try:
            if name in self._servers:
                del self._servers[name]
            if name in self._server_status:
                del self._server_status[name]
            self._connected_servers.discard(name)
                
            return {
                "status": "success",
                "message": f"Server '{name}' unregistered successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to unregister server {name}: {e}")
            return {
                "status": "error",
                "message": f"Failed to unregister server '{name}': {str(e)}"
            }
    
    async def update_server_config(self, name: str, config: BackendServerConfig) -> dict[str, Any]:
        """Update server configuration from BackendServerConfig with enhanced status tracking."""
        try:
            if name not in self._servers:
                return {
                    "status": "error",
                    "message": f"Server '{name}' not found"
                }

            # Convert and update
            mcp_config = self._convert_backend_config_to_mcp(config)
            self._servers[name] = mcp_config
            
            # Update status with enhanced information
            if name in self._server_status:
                server_status = self._server_status[name]
                server_status.enabled = config.enabled
                
                # Update metadata if available
                if config.metadata:
                    if config.metadata.tags:
                        server_status.tags = config.metadata.tags
            else:
                # Create new status if it doesn't exist
                server_status = ServerStatus(
                    name=name,
                    enabled=config.enabled,
                    connected=False,
                    health_status="unknown", # Ensure this is one of the literal values
                    tool_count=0
                )
                
                # Add metadata if available
                if config.metadata:
                    if config.metadata.tags:
                        server_status.tags = config.metadata.tags
                
                self._server_status[name] = server_status
            
            logger.info(f"Updated server config: {name}")
            
            return {
                "status": "success",
                "message": f"Server '{name}' updated successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to update server {name}: {e}")
            return {
                "status": "error",
                "message": f"Failed to update server '{name}': {str(e)}"
            }
    
    async def reload_all_servers(self, server_configs: Dict[str, BackendServerConfig]) -> dict[str, Any]:
        """Reload all servers from new configuration with enhanced status tracking."""
        try:
            # Clear existing servers
            self._servers.clear()
            self._server_status.clear()
            self._connected_servers.clear()
            
            # Register all servers from new config
            registered_count = 0
            errors = []
            
            for name, config in server_configs.items():
                result = await self.register_server_from_config(name, config)
                if result["status"] == "success":
                    registered_count += 1
                else:
                    errors.append(result["message"])
            
            logger.info(f"Reloaded {registered_count} servers from new configuration")
            
            return {
                "status": "success",
                "message": f"Reloaded {registered_count} servers",
                "servers_registered": registered_count,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Failed to reload servers: {e}")
            return {
                "status": "error",
                "message": f"Failed to reload servers: {str(e)}",
                "servers_registered": 0,
                "errors": [str(e)]
            }
    
    def get_server_status(self, name: str) -> Optional[ServerStatus]:
        """Get status information for a server."""
        return self._server_status.get(name)
    
    def list_active_servers(self) -> List[str]:
        """List all currently registered server names."""
        return list(self._servers.keys())
    
    def set_server_connected(self, name: str, connected: bool) -> None:
        """Set the connection status of a server."""
        if name in self._server_status:
            self._server_status[name].connected = connected
            if connected:
                self._connected_servers.add(name)
            else:
                self._connected_servers.discard(name)
    
    def update_server_tool_count(self, name: str, tool_count: int) -> None:
        """Update the tool count for a server."""
        if name in self._server_status:
            self._server_status[name].tool_count = tool_count
    
    def set_server_error(self, name: str, error_message: Optional[str]) -> None:
        """Set an error message for a server."""
        if name in self._server_status:
            self._server_status[name].error_message = error_message
    
    def set_connection_state(self, name: str, state: str, path: Optional[str] = None) -> None:
        """Set the connection state and path for a server."""
        if name in self._server_status:
            self._server_status[name].connection_state = state
            if path:
                self._server_status[name].connection_path = path
    
    def set_discovery_state(self, name: str, state: str, started_at: Optional[str] = None, finished_at: Optional[str] = None) -> None:
        """Set the discovery state for a server."""
        if name in self._server_status:
            self._server_status[name].discovery_state = state
            if started_at:
                self._server_status[name].discovery_started_at = started_at
            if finished_at:
                self._server_status[name].discovery_finished_at = finished_at
    
    def set_last_discovery_error(self, name: str, error: Optional[str], when: Optional[str] = None) -> None:
        """Set the last discovery error for a server."""
        if name in self._server_status:
            self._server_status[name].last_discovery_error = error
            if when:
                self._server_status[name].last_discovery_error_at = when
    
    def clear_last_error(self, name: str) -> None:
        """Clear all error messages for a server."""
        if name in self._server_status:
            self._server_status[name].error_message = None
            self._server_status[name].last_discovery_error = None
            self._server_status[name].last_discovery_error_at = None
    
    def update_server_health_status(self, name: str, health_status: Literal["healthy", "unhealthy", "unknown"], last_check: Optional[str] = None) -> None:
        """Update the health status of a server."""
        if name in self._server_status:
            self._server_status[name].health_status = health_status
            if last_check:
                self._server_status[name].last_health_check = last_check
    
    def _convert_backend_config_to_mcp(self, config: BackendServerConfig) -> MCPServerConfig:
        """Convert BackendServerConfig to MCPServerConfig format."""
        
        # MCPServerConfig does not have a description parameter, remove this variable
        # description = ""
        # if config.metadata and config.metadata.description:
        #     description = config.metadata.description

        if config.type == "stdio":
            return MCPServerConfig(
                command=config.command or "",
                args=config.args or [],
                env=config.env or {},
                # description=description # Remove this line
            )
        else:
            # For HTTP-based servers, we'll need to handle them differently
            # For now, create a placeholder command that indicates the type
            return MCPServerConfig(
                command=f"http-{config.type}",
                args=[config.url or ""],
                env=config.headers or {},
                # description=description # Remove this line
            )


class MCPDiscoveryService:
    """Service for discovering tools from MCP servers with enhanced metadata support"""

    def __init__(self, tool_repo: Any):
        self.tool_repo = tool_repo

    async def discover_and_register_tools(
        self, server_name: str, tools: list[MCPToolSchema], auto_register: bool = True
    ) -> dict[str, Any]:
        """Discover and optionally register tools from an MCP server"""

        discovered_tools = []

        for mcp_tool in tools:
            tool_data = mcp_tool.to_internal_tool(server_name)
            discovered_tools.append(tool_data)

            if auto_register:
                # Add tool to repository
                from ..models.tool import Tool

                tool = Tool(**tool_data)
                await self.tool_repo.add_tool(tool)

        return {
            "status": "success",
            "server": server_name,
            "tools_discovered": len(discovered_tools),
            "tools": discovered_tools if not auto_register else None,
            "auto_registered": auto_register,
        }

    async def analyze_mcp_config(
        self,
        config: MCPServerConfig,
        sample_tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Analyze an MCP server configuration to extract metadata"""

        # Extract server type from command
        command = config.command.lower()
        server_type = "unknown"

        if "slack" in command:
            server_type = "slack"
        elif "github" in command:
            server_type = "github"
        elif "database" in command or "postgres" in command or "mysql" in command:
            server_type = "database"
        elif "file" in command or "fs" in command:
            server_type = "filesystem"
        elif "api" in command or "rest" in command:
            server_type = "api"

        # Estimate capabilities from args and env
        capabilities = []
        if any("read" in arg.lower() for arg in config.args):
            capabilities.append("read")
        if any("write" in arg.lower() for arg in config.args):
            capabilities.append("write")
        if any(
            "token" in key.lower() or "key" in key.lower() for key in config.env.keys()
        ):
            capabilities.append("authenticated")

        # If sample tools provided, analyze them
        tool_categories = set()
        if sample_tools:
            for tool in sample_tools:
                desc = tool.get("description", "").lower()
                if "search" in desc:
                    tool_categories.add("search")
                if "create" in desc or "add" in desc:
                    tool_categories.add("create")
                if "update" in desc or "edit" in desc:
                    tool_categories.add("update")
                if "delete" in desc or "remove" in desc:
                    tool_categories.add("delete")
                if "list" in desc or "get" in desc:
                    tool_categories.add("read")

        return {
            "server_type": server_type,
            "capabilities": capabilities,
            "tool_categories": list(tool_categories),
            "has_authentication": "authenticated" in capabilities, # This was already correct
            "estimated_complexity": len(config.args) + len(config.env),
        }

    async def perform_health_check(self, server_name: str, server_config: BackendServerConfig) -> dict[str, Any]:
        """Perform a health check on a server based on its configuration."""
        try:
            # Check if health checks are enabled
            if not server_config.health_check or not server_config.health_check.enabled:
                return {
                    "status": "skipped",
                    "message": "Health checks disabled for this server"
                }
            
            # Perform health check based on server type
            if server_config.type == "stdio":
                # For stdio servers, check if the command exists
                import os
                import shutil
                command = server_config.command or ""
                if os.path.exists(command) or shutil.which(command):
                    return {
                        "status": "healthy",
                        "message": "Command executable found"
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "message": "Command executable not found"
                    }
            elif server_config.type in ["sse", "streamable-http"]:
                # For HTTP servers, we would perform an actual HTTP check
                # This is a simplified implementation - in a real system, we would make an HTTP request
                url = server_config.url or ""
                if url:
                    return {
                        "status": "healthy",
                        "message": f"HTTP server configured at {url}"
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "message": "No URL configured for HTTP server"
                    }
            else:
                return {
                    "status": "unknown",
                    "message": f"Unsupported server type: {server_config.type}"
                }
                
        except Exception as e:
            logger.error(f"Health check failed for server {server_name}: {e}")
            return {
                "status": "error",
                "message": f"Health check failed: {str(e)}"
            }
