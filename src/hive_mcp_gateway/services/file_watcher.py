"""File watcher service for dynamic configuration reloading."""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable
from watchfiles import awatch

from .config_manager import ConfigManager
from .mcp_registry import MCPServerRegistry

logger = logging.getLogger(__name__)


class FileWatcherService:
    """Watches configuration files for changes and triggers dynamic reloading."""
    
    def __init__(self, config_manager: ConfigManager, registry: MCPServerRegistry):
        """Initialize file watcher with config manager and MCP registry."""
        self.config_manager = config_manager
        self.registry = registry
        self._watch_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._change_callbacks: list[Callable[[], Awaitable[None]]] = []
        
    def add_change_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Add a callback to be called when configuration changes."""
        self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Remove a change callback."""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
    
    async def start_watching(self, config_path: Optional[str] = None) -> None:
        """Start watching the configuration file for changes."""
        if self._watch_task and not self._watch_task.done():
            logger.warning("File watcher is already running")
            return
        
        if config_path:
            self.config_manager.config_path = Path(config_path)
        
        watch_path = self.config_manager.config_path
        
        # Create parent directory if it doesn't exist
        watch_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create config file if it doesn't exist
        if not watch_path.exists():
            self.config_manager.save_config(self.config_manager.load_config())
        
        logger.info(f"Starting file watcher for {watch_path}")
        
        self._stop_event.clear()
        self._watch_task = asyncio.create_task(self._watch_file(watch_path))
    
    async def stop_watching(self) -> None:
        """Stop watching the configuration file."""
        if self._watch_task and not self._watch_task.done():
            logger.info("Stopping file watcher")
            self._stop_event.set()
            
            try:
                await asyncio.wait_for(self._watch_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("File watcher shutdown timed out, cancelling task")
                self._watch_task.cancel()
                try:
                    await self._watch_task
                except asyncio.CancelledError:
                    pass
            
            self._watch_task = None
            logger.info("File watcher stopped")
    
    async def _watch_file(self, config_path: Path) -> None:
        """Internal method to watch the configuration file."""
        try:
            # Watch the parent directory since some editors create temporary files
            watch_dir = config_path.parent
            
            async for changes in awatch(watch_dir, stop_event=self._stop_event):
                # Filter changes to only our config file
                config_changes = [
                    change for change in changes 
                    if Path(change[1]).name == config_path.name
                ]
                
                if config_changes:
                    logger.info(f"Configuration file changed: {config_changes}")
                    await self.on_config_changed()
                    
                    # Small delay to handle multiple rapid changes
                    await asyncio.sleep(0.5)
                    
        except asyncio.CancelledError:
            logger.info("File watcher cancelled")
            raise
        except Exception as e:
            logger.error(f"File watcher error: {e}")
            raise
    
    async def on_config_changed(self) -> None:
        """Handle configuration file changes."""
        try:
            logger.info("Configuration file changed, reloading...")
            
            # Force reload of configuration
            self.config_manager._config = None
            self.config_manager._last_modified = None
            
            # Load new configuration
            new_config = self.config_manager.load_config()
            
            # Reload servers with new configuration
            await self.reload_servers()
            
            # Call registered callbacks
            for callback in self._change_callbacks:
                try:
                    await callback()
                except Exception as e:
                    logger.error(f"Error in change callback: {e}")
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
    
    async def reload_servers(self) -> None:
        """Reload all MCP servers based on current configuration."""
        try:
            # Get current server configurations
            backend_servers = self.config_manager.get_backend_servers()
            
            # Get currently registered servers
            current_servers = set(self.registry.list_active_servers())
            new_servers = set(backend_servers.keys())
            
            # Determine which servers to add, remove, or update
            servers_to_remove = current_servers - new_servers
            servers_to_add = new_servers - current_servers
            servers_to_check = current_servers & new_servers
            
            # Remove servers that are no longer in config
            for server_name in servers_to_remove:
                logger.info(f"Removing server: {server_name}")
                await self.registry.unregister_server(server_name)
            
            # Add new servers
            for server_name in servers_to_add:
                if backend_servers[server_name].enabled:
                    logger.info(f"Adding server: {server_name}")
                    await self.registry.register_server_from_config(
                        server_name, 
                        backend_servers[server_name]
                    )
            
            # Check existing servers for configuration changes
            for server_name in servers_to_check:
                server_config = backend_servers[server_name]
                
                if not server_config.enabled:
                    # Server was disabled, remove it
                    logger.info(f"Disabling server: {server_name}")
                    await self.registry.unregister_server(server_name)
                else:
                    # Server still enabled, update configuration
                    logger.info(f"Updating server: {server_name}")
                    await self.registry.update_server_config(server_name, server_config)
            
            logger.info("Server reload completed")
            
        except Exception as e:
            logger.error(f"Failed to reload servers: {e}")
            raise
    
    async def force_reload(self) -> None:
        """Force a reload of the configuration without waiting for file changes."""
        logger.info("Forcing configuration reload")
        await self.on_config_changed()
    
    def is_watching(self) -> bool:
        """Check if the file watcher is currently active."""
        return self._watch_task is not None and not self._watch_task.done()
    
    async def get_watch_status(self) -> dict:
        """Get the current status of the file watcher."""
        return {
            "watching": self.is_watching(),
            "config_path": str(self.config_manager.config_path),
            "config_exists": self.config_manager.config_path.exists(),
            "last_modified": (
                self.config_manager.config_path.stat().st_mtime 
                if self.config_manager.config_path.exists() 
                else None
            ),
            "active_servers": self.registry.list_active_servers(),
        }


class ConfigurationUpdateNotifier:
    """Helper class to notify components of configuration updates."""
    
    def __init__(self):
        """Initialize the notifier."""
        self._subscribers: list[Callable[[str], Awaitable[None]]] = []
    
    def subscribe(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Subscribe to configuration update notifications."""
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Unsubscribe from configuration update notifications."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    async def notify(self, change_type: str) -> None:
        """Notify all subscribers of a configuration change."""
        for callback in self._subscribers:
            try:
                await callback(change_type)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")


# Global notifier instance
config_notifier = ConfigurationUpdateNotifier()