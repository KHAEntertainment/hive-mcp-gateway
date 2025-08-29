"""MCP Server Registry Service with enhanced configuration support"""

import json
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

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

    def __init__(self, config_path: str = "mcp-servers.json"):
        self.config_path = Path(config_path)
        self._servers: dict[str, MCPServerConfig] = {}
        self._server_status: dict[str, ServerStatus] = {}
        self._connected_servers: set[str] = set()
        self._load_config()

    def _load_config(self) -> None:
        """Load server configurations from file"""
        if self.config_path.exists():
            try:
                # Read file content
                with open(self.config_path, 'r') as f:
                    if self.config_path.suffix.lower() in ['.yaml', '.yml']:
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)
                
                # Process each server configuration
                for name, config in data.items():
                    self._servers[name] = MCPServerConfig(**config)
                    # Initialize status for existing servers
                    self._server_status[name] = ServerStatus(
                        name=name,
                        enabled=True,
                        connected=False
                    )
                    
                logger.info(f"Loaded {len(self._servers)} servers from {self.config_path}")
                
            except Exception as e:
                logger.error(f"Failed to load configuration from {self.config_path}: {e}")
                # Initialize with empty configuration
                self._servers = {}
                self._server_status = {}

    async def save_config(self, format: str = "auto") -> None:
        """Save current configurations to file in specified format"""
        try:
            data = {
                name: config.model_dump(exclude_none=True)
                for name, config in self._servers.items()
            }

            # Determine format based on file extension or parameter
            if format == "auto":
                if self.config_path.suffix.lower() in ['.yaml', '.yml']:
                    format = "yaml"
                else:
                    format = "json"

            # Write to file
            async with aiofiles.open(self.config_path, "w") as f:
                if format == "yaml":
                    yaml_content = yaml.dump(data, default_flow_style=False, indent=2)
                    await f.write(yaml_content)
                else:
                    json_content = json.dumps(data, indent=2)
                    await f.write(json_content)

            logger.info(f"Saved {len(self._servers)} servers to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration to {self.config_path}: {e}")
            raise

    async def register_server(
        self, registration: MCPServerRegistration
    ) -> dict[str, str]:
        """Register a new MCP server"""
        if registration.name in self._servers:
            return {
                "status": "error",
                "message": f"Server '{registration.name}' already exists",
            }

        self._servers[registration.name] = registration.config
        
        # Initialize server status
        self._server_status[registration.name] = ServerStatus(
            name=registration.name,
            enabled=True,
            connected=False,
            health_status="unknown"
        )
        
        await self.save_config()

        return {
            "status": "success",
            "message": f"Server '{registration.name}' registered successfully",
        }

    async def get_server(self, name: str) -> MCPServerConfig | None:
        """Get a server configuration by name"""
        return self._servers.get(name)

    async def list_servers(self) -> list[str]:
        """List all registered server names"""
        return list(self._servers.keys())

    async def remove_server(self, name: str) -> dict[str, str]:
        """Remove a server from the registry"""
        if name not in self._servers:
            return {"status": "error", "message": f"Server '{name}' not found"}

        del self._servers[name]
        
        # Remove server status
        if name in self._server_status:
            del self._server_status[name]
            
        # Remove from connected servers
        if name in self._connected_servers:
            self._connected_servers.discard(name)
        
        await self.save_config()

        return {"status": "success", "message": f"Server '{name}' removed successfully"}

    async def update_server(self, name: str, config: MCPServerConfig) -> dict[str, str]:
        """Update an existing server configuration"""
        if name not in self._servers:
            return {"status": "error", "message": f"Server '{name}' not found"}

        self._servers[name] = config
        await self.save_config()

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
                health_status="unknown",
                tool_count=0
            )
            
            # Add metadata if available
            if config.metadata:
                if config.metadata.description:
                    server_status.description = config.metadata.description
                if config.metadata.tags:
                    server_status.tags = config.metadata.tags
            
            self._server_status[name] = server_status
            
            logger.info(f"Registered server from config: {name}")
            await self.save_config()
            
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
                
            if name in self._connected_servers:
                self._connected_servers.discard(name)
                
            logger.info(f"Unregistered server: {name}")
            await self.save_config()
            
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
                    if config.metadata.description:
                        server_status.description = config.metadata.description
                    if config.metadata.tags:
                        server_status.tags = config.metadata.tags
            else:
                # Create new status if it doesn't exist
                server_status = ServerStatus(
                    name=name,
                    enabled=config.enabled,
                    connected=False,
                    health_status="unknown",
                    tool_count=0
                )
                
                # Add metadata if available
                if config.metadata:
                    if config.metadata.description:
                        server_status.description = config.metadata.description
                    if config.metadata.tags:
                        server_status.tags = config.metadata.tags
                
                self._server_status[name] = server_status
            
            logger.info(f"Updated server config: {name}")
            await self.save_config()
            
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
    
    def update_server_health_status(self, name: str, health_status: str, last_check: Optional[str] = None) -> None:
        """Update the health status of a server."""
        if name in self._server_status:
            self._server_status[name].health_status = health_status
            if last_check:
                self._server_status[name].last_health_check = last_check
    
    def _convert_backend_config_to_mcp(self, config: BackendServerConfig) -> MCPServerConfig:
        """Convert BackendServerConfig to MCPServerConfig format."""
        if config.type == "stdio":
            return MCPServerConfig(
                command=config.command or "",
                args=config.args or [],
                env=config.env or {},
                description=config.description or ""
            )
        else:
            # For HTTP-based servers, we'll need to handle them differently
            # For now, create a placeholder command that indicates the type
            return MCPServerConfig(
                command=f"http-{config.type}",
                args=[config.url or ""],
                env=config.headers or {},
                description=config.description or ""
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
            "has_authentication": any("authenticated" in capabilities),
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
