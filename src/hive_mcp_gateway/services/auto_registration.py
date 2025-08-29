"""Automatic registration system for MCP servers with multi-stage pipeline and fallback mechanisms."""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..models.config import BackendServerConfig, ToolGatingConfig
from .mcp_client_manager import MCPClientManager
from .mcp_registry import MCPServerRegistry
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


class AutoRegistrationService:
    """Service for automatically registering MCP servers with fallback mechanisms."""
    
    def __init__(
        self,
        config_manager: ConfigManager,
        client_manager: MCPClientManager,
        registry: MCPServerRegistry
    ):
        self.config_manager = config_manager
        self.client_manager = client_manager
        self.registry = registry
        self.registration_attempts: Dict[str, int] = {}
        self.max_registration_attempts = 3
        
    async def register_all_servers(self, config: ToolGatingConfig) -> Dict[str, Any]:
        """Register all servers from configuration with multi-stage pipeline."""
        results = {
            "successful": [],
            "failed": [],
            "skipped": []
        }
        
        backend_servers = config.backend_mcp_servers
        
        # Stage 1: Register enabled servers
        logger.info(f"Stage 1: Registering {len(backend_servers)} servers from configuration")
        for server_name, server_config in backend_servers.items():
            if not server_config.enabled:
                results["skipped"].append(server_name)
                logger.info(f"Skipping disabled server: {server_name}")
                continue
                
            result = await self._register_server_with_fallback(server_name, server_config)
            if result["status"] == "success":
                results["successful"].append(server_name)
            else:
                results["failed"].append({"server": server_name, "error": result["message"]})
        
        # Stage 2: Health check all registered servers
        logger.info("Stage 2: Performing health checks on registered servers")
        await self._perform_health_checks(results["successful"])
        
        # Stage 3: Retry failed registrations
        if results["failed"]:
            logger.info(f"Stage 3: Retrying {len(results['failed'])} failed registrations")
            await self._retry_failed_registrations(results)
        
        return results
    
    async def _register_server_with_fallback(self, name: str, config: BackendServerConfig) -> Dict[str, Any]:
        """Register a server with fallback mechanisms."""
        try:
            # Primary registration method
            logger.info(f"Attempting primary registration for {name}")
            result = await self._primary_registration(name, config)
            
            if result["status"] == "success":
                logger.info(f"✓ Primary registration successful for {name}")
                return result
            
            # Fallback registration method
            logger.warning(f"Primary registration failed for {name}, trying fallback method")
            fallback_result = await self._fallback_registration(name, config)
            
            if fallback_result["status"] == "success":
                logger.info(f"✓ Fallback registration successful for {name}")
                return fallback_result
            else:
                logger.error(f"✗ Both primary and fallback registration failed for {name}")
                return fallback_result
                
        except Exception as e:
            logger.error(f"Exception during registration of {name}: {e}")
            return {
                "status": "error",
                "message": f"Registration failed with exception: {str(e)}",
                "server_name": name
            }
    
    async def _primary_registration(self, name: str, config: BackendServerConfig) -> Dict[str, Any]:
        """Primary registration method using direct connection."""
        try:
            # Convert BackendServerConfig to dict format for client manager
            server_dict = {
                "type": config.type,
                "command": config.command,
                "args": config.args or [],
                "env": config.env or {},
                "url": config.url,
                "headers": config.headers or {},
                "description": config.description or f"MCP server: {name}"
            }
            
            # Attempt to connect to the server
            connect_result = await self.client_manager.connect_server(name, server_dict)
            
            if connect_result["status"] != "success":
                return {
                    "status": "error",
                    "message": f"Server connection failed: {connect_result['message']}",
                    "server_name": name
                }
            
            # Register in the registry
            registry_result = await self.registry.register_server_from_config(name, config)
            
            if registry_result["status"] == "success":
                return {
                    "status": "success",
                    "message": f"Server {name} registered successfully",
                    "server_name": name
                }
            else:
                return {
                    "status": "error",
                    "message": f"Registry registration failed: {registry_result['message']}",
                    "server_name": name
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Primary registration failed: {str(e)}",
                "server_name": name
            }
    
    async def _fallback_registration(self, name: str, config: BackendServerConfig) -> Dict[str, Any]:
        """Fallback registration method using mock registration."""
        try:
            # For fallback, we'll register in the registry without connecting
            registry_result = await self.registry.register_server_from_config(name, config)
            
            if registry_result["status"] == "success":
                # Mark server as disconnected in status
                self.registry.set_server_connected(name, False)
                return {
                    "status": "success",
                    "message": f"Server {name} registered in fallback mode",
                    "server_name": name,
                    "fallback": True
                }
            else:
                return {
                    "status": "error",
                    "message": f"Fallback registration failed: {registry_result['message']}",
                    "server_name": name
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Fallback registration failed: {str(e)}",
                "server_name": name
            }
    
    async def _perform_health_checks(self, server_names: List[str]) -> None:
        """Perform health checks on all registered servers."""
        for server_name in server_names:
            try:
                health_result = await self.client_manager.health_check(server_name)
                logger.info(f"Health check for {server_name}: {health_result['status']}")
                
                # Update registry with health status
                self.registry.update_server_health_status(
                    server_name,
                    health_result["status"],
                    health_result.get("message", "")
                )
                
            except Exception as e:
                logger.error(f"Health check failed for {server_name}: {e}")
                self.registry.update_server_health_status(server_name, "error", str(e))
    
    async def _retry_failed_registrations(self, results: Dict[str, Any]) -> None:
        """Retry failed registrations with exponential backoff."""
        failed_servers = results["failed"]
        
        for failed_entry in failed_servers:
            server_name = failed_entry["server"]
            
            # Track registration attempts
            if server_name not in self.registration_attempts:
                self.registration_attempts[server_name] = 0
            
            if self.registration_attempts[server_name] < self.max_registration_attempts:
                self.registration_attempts[server_name] += 1
                
                # Get server config from original configuration
                try:
                    config = self.config_manager.load_config()
                    if server_name in config.backend_mcp_servers:
                        server_config = config.backend_mcp_servers[server_name]
                        
                        # Wait before retry (exponential backoff)
                        wait_time = 2 ** self.registration_attempts[server_name]
                        logger.info(f"Retrying registration for {server_name} in {wait_time} seconds")
                        await asyncio.sleep(wait_time)
                        
                        # Attempt registration again
                        result = await self._register_server_with_fallback(server_name, server_config)
                        if result["status"] == "success":
                            # Move from failed to successful
                            results["failed"] = [f for f in results["failed"] if f["server"] != server_name]
                            results["successful"].append(server_name)
                            logger.info(f"✓ Retry successful for {server_name}")
                        else:
                            logger.error(f"✗ Retry failed for {server_name}: {result['message']}")
                            
                except Exception as e:
                    logger.error(f"Failed to retry registration for {server_name}: {e}")
    
    async def register_new_server(self, name: str, config: BackendServerConfig) -> Dict[str, Any]:
        """Register a new server that was not in the original configuration."""
        try:
            # Add to configuration
            self.config_manager.add_backend_server(name, config)
            
            # Register with pipeline
            result = await self._register_server_with_fallback(name, config)
            
            if result["status"] == "success":
                logger.info(f"✓ New server {name} registered successfully")
                return {
                    "status": "success",
                    "message": f"New server {name} registered successfully",
                    "server_name": name
                }
            else:
                logger.error(f"✗ Failed to register new server {name}: {result['message']}")
                return {
                    "status": "error",
                    "message": f"Failed to register new server {name}: {result['message']}",
                    "server_name": name
                }
                
        except Exception as e:
            logger.error(f"Exception during new server registration for {name}: {e}")
            return {
                "status": "error",
                "message": f"New server registration failed with exception: {str(e)}",
                "server_name": name
            }
    
    async def unregister_server(self, name: str) -> Dict[str, Any]:
        """Unregister a server and clean up resources."""
        try:
            # Remove from registry
            registry_result = await self.registry.unregister_server(name)
            
            if registry_result["status"] == "success":
                # Disconnect server
                disconnect_result = await self.client_manager.disconnect_server(name)
                if disconnect_result["status"] != "success":
                    logger.warning(f"Failed to disconnect server {name}: {disconnect_result['message']}")
                
                logger.info(f"✓ Server {name} unregistered successfully")
                return {
                    "status": "success",
                    "message": f"Server {name} unregistered successfully"
                }
            else:
                logger.error(f"✗ Failed to unregister server {name}: {registry_result['message']}")
                return {
                    "status": "error",
                    "message": f"Failed to unregister server {name}: {registry_result['message']}"
                }
                
        except Exception as e:
            logger.error(f"Exception during server unregistration for {name}: {e}")
            return {
                "status": "error",
                "message": f"Server unregistration failed with exception: {str(e)}",
                "server_name": name
            }