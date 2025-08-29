"""Configuration manager for Hive MCP Gateway configuration system."""

import json
import yaml
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from string import Template

from pydantic import ValidationError

from ..models.config import (
    ToolGatingConfig,
    BackendServerConfig,
    ToolGatingSettings,
    ValidationResult,
    ProcessResult,
    DEFAULT_CONFIG
)

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration for Hive MCP Gateway with validation and environment variable substitution."""
    
    def __init__(self, config_path: str = "tool_gating_config.json"):
        """Initialize config manager with path to configuration file."""
        self.config_path = Path(config_path)
        self._config: Optional[ToolGatingConfig] = None
        self._last_modified: Optional[float] = None
        
    def load_config(self) -> ToolGatingConfig:
        """Load configuration from file with environment variable substitution."""
        try:
            if not self.config_path.exists():
                logger.info(f"Configuration file {self.config_path} not found, creating default config")
                self.save_config(DEFAULT_CONFIG)
                return DEFAULT_CONFIG
            
            # Check if file has been modified
            current_modified = self.config_path.stat().st_mtime
            if self._config is not None and self._last_modified == current_modified:
                return self._config
            
            # Read and parse configuration based on file extension
            raw_content = self.config_path.read_text(encoding='utf-8')
            
            # Substitute environment variables
            substituted_content = self._substitute_env_vars(raw_content)
            
            # Parse based on file extension
            if self.config_path.suffix.lower() == '.yaml' or self.config_path.suffix.lower() == '.yml':
                config_data = yaml.safe_load(substituted_content)
            else:
                # Default to JSON
                config_data = json.loads(substituted_content)
            
            # Validate and create config object
            config = ToolGatingConfig(**config_data)
            
            # Cache config and modification time
            self._config = config
            self._last_modified = current_modified
            
            logger.info(f"Configuration loaded successfully from {self.config_path}")
            return config
            
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ValueError(f"Invalid configuration: {e}")
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            logger.error(f"Configuration parsing failed: {e}")
            raise ValueError(f"Invalid configuration format: {e}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def save_config(self, config: ToolGatingConfig, format: str = "json") -> None:
        """Save configuration to file in specified format (json or yaml)."""
        try:
            # Create directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to dict
            config_dict = config.dict(by_alias=True, exclude_unset=False)
            
            # Format based on specified format or file extension
            if format.lower() == "yaml" or (format.lower() == "auto" and
                (self.config_path.suffix.lower() == '.yaml' or self.config_path.suffix.lower() == '.yml')):
                formatted_content = yaml.dump(config_dict, default_flow_style=False, indent=2, allow_unicode=True)
            else:
                # Default to JSON
                formatted_content = json.dumps(config_dict, indent=2, ensure_ascii=False)
            
            # Write to file
            self.config_path.write_text(formatted_content, encoding='utf-8')
            
            # Update cache
            self._config = config
            self._last_modified = self.config_path.stat().st_mtime
            
            logger.info(f"Configuration saved to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
    
    def validate_config(self, config_data: Dict[str, Any]) -> ValidationResult:
        """Validate configuration data and return validation result."""
        errors = []
        warnings = []
        
        try:
            # Attempt to parse with Pydantic
            ToolGatingConfig(**config_data)
            
            # Additional custom validations
            tool_gating = config_data.get('toolGating', {})
            backend_servers = config_data.get('backendMcpServers', {})
            
            # Check port conflicts
            port = tool_gating.get('port', 8001)
            if port == 8000:
                warnings.append("Port 8000 may conflict with existing installation")
            
            # Check server configurations
            for server_name, server_config in backend_servers.items():
                if not server_config.get('enabled', True):
                    continue
                    
                server_type = server_config.get('type', 'stdio')
                
                if server_type == 'stdio':
                    if not server_config.get('command'):
                        errors.append(f"Server '{server_name}': command required for stdio type")
                        
                elif server_type in ['sse', 'streamable-http']:
                    if not server_config.get('url'):
                        errors.append(f"Server '{server_name}': url required for {server_type} type")
            
            # Check for duplicate descriptions
            descriptions = [
                s.get('description') for s in backend_servers.values() 
                if s.get('description')
            ]
            if len(descriptions) != len(set(descriptions)):
                warnings.append("Duplicate server descriptions found")
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings
            )
            
        except ValidationError as e:
            errors.extend([str(err) for err in e.errors()])
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        except Exception as e:
            return ValidationResult(is_valid=False, errors=[str(e)], warnings=warnings)
    
    def get_tool_gating_settings(self) -> ToolGatingSettings:
        """Get Tool Gating application settings."""
        config = self.load_config()
        return config.tool_gating
    
    def get_backend_servers(self) -> Dict[str, BackendServerConfig]:
        """Get backend MCP servers configuration."""
        config = self.load_config()
        return config.backend_mcp_servers
    
    def add_backend_server(self, name: str, config: BackendServerConfig) -> None:
        """Add a new backend MCP server configuration."""
        current_config = self.load_config()
        current_config.backend_mcp_servers[name] = config
        self.save_config(current_config)
        logger.info(f"Added backend server: {name}")
    
    def remove_backend_server(self, name: str) -> bool:
        """Remove a backend MCP server configuration."""
        current_config = self.load_config()
        if name in current_config.backend_mcp_servers:
            del current_config.backend_mcp_servers[name]
            self.save_config(current_config)
            logger.info(f"Removed backend server: {name}")
            return True
        return False
    
    def update_backend_server(self, name: str, config: BackendServerConfig) -> bool:
        """Update an existing backend MCP server configuration."""
        current_config = self.load_config()
        if name in current_config.backend_mcp_servers:
            current_config.backend_mcp_servers[name] = config
            self.save_config(current_config)
            logger.info(f"Updated backend server: {name}")
            return True
        return False
    
    def enable_server(self, name: str, enabled: bool = True) -> bool:
        """Enable or disable a backend MCP server."""
        current_config = self.load_config()
        if name in current_config.backend_mcp_servers:
            current_config.backend_mcp_servers[name].enabled = enabled
            self.save_config(current_config)
            logger.info(f"{'Enabled' if enabled else 'Disabled'} server: {name}")
            return True
        return False
    
    def process_mcp_snippet(self, json_text: str, server_name: Optional[str] = None) -> ProcessResult:
        """Process MCP JSON snippet and add/update server configuration."""
        try:
            # Parse JSON snippet
            snippet_data = json.loads(json_text)
            
            # Handle different formats
            if 'mcpServers' in snippet_data:
                # mcp-proxy format
                return self._process_mcp_proxy_format(snippet_data, server_name)
            else:
                # Direct server config format
                return self._process_direct_format(snippet_data, server_name)
                
        except json.JSONDecodeError as e:
            return ProcessResult(
                success=False,
                message=f"Invalid JSON format: {e}",
                errors=[str(e)]
            )
        except Exception as e:
            return ProcessResult(
                success=False,
                message=f"Failed to process snippet: {e}",
                errors=[str(e)]
            )
    
    def backup_config(self, backup_path: Optional[Path] = None) -> Path:
        """Create a backup of the current configuration."""
        if backup_path is None:
            timestamp = int(os.path.getctime(self.config_path))
            backup_path = self.config_path.with_suffix(f'.backup.{timestamp}.json')
        
        if self.config_path.exists():
            backup_path.write_text(self.config_path.read_text())
            logger.info(f"Configuration backed up to {backup_path}")
        
        return backup_path
    
    def _substitute_env_vars(self, content: str) -> str:
        """Substitute environment variables in configuration content."""
        try:
            template = Template(content)
            # Get all environment variables
            env_vars = dict(os.environ)
            
            # Perform substitution with safe_substitute to handle missing vars
            return template.safe_substitute(env_vars)
        except Exception as e:
            logger.warning(f"Environment variable substitution failed: {e}")
            return content
    
    def _process_mcp_proxy_format(self, snippet_data: Dict[str, Any], server_name: Optional[str]) -> ProcessResult:
        """Process mcp-proxy format configuration snippet."""
        mcp_servers = snippet_data.get('mcpServers', {})
        
        if not mcp_servers:
            return ProcessResult(
                success=False,
                message="No MCP servers found in snippet",
                errors=["mcpServers section is empty or missing"]
            )
        
        # If server_name not provided, use first server name from snippet
        if server_name is None:
            server_name = next(iter(mcp_servers.keys()))
        
        server_config_data = mcp_servers[server_name]
        
        # Convert mcp-proxy format to tool-gating-mcp format
        config = self._convert_mcp_proxy_config(server_config_data)
        
        # Check if server already exists
        current_config = self.load_config()
        action = "updated" if server_name in current_config.backend_mcp_servers else "added"
        
        # Add/update server
        self.add_backend_server(server_name, config)
        
        return ProcessResult(
            success=True,
            server_name=server_name,
            action=action,
            message=f"Successfully {action} server '{server_name}'"
        )
    
    def _process_direct_format(self, snippet_data: Dict[str, Any], server_name: Optional[str]) -> ProcessResult:
        """Process direct server configuration format."""
        if server_name is None:
            return ProcessResult(
                success=False,
                message="Server name required for direct format",
                errors=["Server name must be provided"]
            )
        
        try:
            config = BackendServerConfig(**snippet_data)
            
            # Check if server already exists
            current_config = self.load_config()
            action = "updated" if server_name in current_config.backend_mcp_servers else "added"
            
            # Add/update server
            self.add_backend_server(server_name, config)
            
            return ProcessResult(
                success=True,
                server_name=server_name,
                action=action,
                message=f"Successfully {action} server '{server_name}'"
            )
            
        except ValidationError as e:
            return ProcessResult(
                success=False,
                message=f"Invalid server configuration: {e}",
                errors=[str(err) for err in e.errors()]
            )
    
    def _convert_mcp_proxy_config(self, mcp_proxy_config: Dict[str, Any]) -> BackendServerConfig:
        """Convert mcp-proxy server configuration to tool-gating-mcp format."""
        # Extract basic fields
        config_data = {
            "type": "stdio",  # mcp-proxy typically uses stdio
            "command": mcp_proxy_config.get("command"),
            "args": mcp_proxy_config.get("args", []),
            "env": mcp_proxy_config.get("env", {}),
            "enabled": True
        }
        
        # Handle URL-based configs
        if "url" in mcp_proxy_config:
            config_data["type"] = "sse"  # Assume SSE for URL-based configs
            config_data["url"] = mcp_proxy_config["url"]
            config_data.pop("command", None)
            config_data.pop("args", None)
        
        # Handle options
        if "options" in mcp_proxy_config:
            config_data["options"] = mcp_proxy_config["options"]
        
        return BackendServerConfig(**config_data)