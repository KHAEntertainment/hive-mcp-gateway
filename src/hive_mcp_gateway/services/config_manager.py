"""Configuration manager for Hive MCP Gateway configuration system."""

import json
import yaml
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
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
    
    def __init__(self, config_path: str = "tool_gating_config.json", credential_manager=None):
        """Initialize config manager with path to configuration file."""
        self.config_path = Path(config_path)
        self._config: Optional[ToolGatingConfig] = None
        self._last_modified: Optional[float] = None
        self.credential_manager = credential_manager
        
        # Create credential manager if none provided
        if self.credential_manager is None:
            # Import here to avoid circular imports
            from ..services.credential_manager import CredentialManager
            self.credential_manager = CredentialManager()
        
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
            
            # DEBUG: Log the parsed config data
            logger.debug(f"Raw config data keys: {list(config_data.keys())}")
            backend_servers_raw = config_data.get('backendMcpServers', {})
            logger.debug(f"Raw backend servers count: {len(backend_servers_raw)}")
            for name, server_data in backend_servers_raw.items():
                logger.debug(f"  Raw server {name}: {server_data}")
            
            # Validate and create config object
            config = ToolGatingConfig(**config_data)

            # Autonomy migration: ensure managed proxy is enabled and stdio uses proxy
            try:
                changed = False
                # Force manageProxy true by default
                if getattr(config.tool_gating, 'manage_proxy', False) is False:
                    config.tool_gating.manage_proxy = True
                    changed = True
                # Flip stdio servers to via: proxy unless explicitly set
                for name, srv in list(config.backend_mcp_servers.items()):
                    if getattr(srv, 'type', 'stdio') == 'stdio' and getattr(srv, 'via', 'proxy') != 'proxy':
                        srv.via = 'proxy'
                        config.backend_mcp_servers[name] = srv
                        changed = True
                if changed:
                    # Persist sanitized config
                    self.save_config(config, format='auto')
            except Exception as _e:
                logger.warning(f"Autonomy config migration skipped: {_e}")
            
            # DEBUG: Log the parsed config object
            logger.debug(f"Parsed backend servers count: {len(config.backend_mcp_servers)}")
            for name, server_config in config.backend_mcp_servers.items():
                logger.debug(f"  Parsed server {name}: type={server_config.type}, command={server_config.command}, enabled={server_config.enabled}")
            
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


    def set_port(self, port: int) -> bool:
        """Set the port in the configuration."""
        current_config = self.load_config()
        current_config.tool_gating.port = port
        self.save_config(current_config)
        logger.info(f"Set port to: {port}")
        return True

    def set_manage_proxy(self, enabled: bool) -> bool:
        """Enable/disable managed MCP Proxy orchestration."""
        current_config = self.load_config()
        current_config.tool_gating.manage_proxy = enabled
        self.save_config(current_config)
        logger.info(f"Set manageProxy to: {enabled}")
        return True

    def set_auto_proxy_stdio(self, enabled: bool) -> bool:
        """Enable/disable automatic stdio routing through proxy when available."""
        current_config = self.load_config()
        current_config.tool_gating.auto_proxy_stdio = enabled
        self.save_config(current_config)
        logger.info(f"Set autoProxyStdio to: {enabled}")
        return True
    
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
        
        # Convert mcp-proxy format to Hive MCP Gateway format
        config = self._convert_mcp_proxy_to_hive_format(server_config_data)
        
        # Check if server already exists
        current_config = self.load_config()
        action = "updated" if server_name in current_config.backend_mcp_servers else "added"
        
        # Process credentials from the configuration
        processed_credentials = self.extract_and_process_credentials(server_name, config)
        
        # Add/update server
        self.add_backend_server(server_name, BackendServerConfig(**config))
        
        result = ProcessResult(
            success=True,
            server_name=server_name,
            action=action,
            message=f"Successfully {action} server '{server_name}'"
        )
        
        # Add credentials info if any were processed
        if processed_credentials:
            result.message += f" with {len(processed_credentials)} credential(s)"
        
        return result
    
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
            
            # Process credentials from the configuration
            processed_credentials = self.extract_and_process_credentials(server_name, snippet_data)
            
            # Add/update server
            self.add_backend_server(server_name, config)
            
            result = ProcessResult(
                success=True,
                server_name=server_name,
                action=action,
                message=f"Successfully {action} server '{server_name}'"
            )
            
            # Add credentials info if any were processed
            if processed_credentials:
                result.message += f" with {len(processed_credentials)} credential(s)"
            
            return result
            
        except ValidationError as e:
            return ProcessResult(
                success=False,
                message=f"Invalid server configuration: {e}",
                errors=[str(err) for err in e.errors()]
            )
    
    def _convert_mcp_proxy_to_hive_format(self, server_config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert mcp-proxy server configuration to Hive MCP Gateway format."""
        # Extract basic fields
        config_data = {
            "type": "stdio",  # mcp-proxy typically uses stdio
            "command": server_config.get("command"),
            "args": server_config.get("args", []),
            "env": server_config.get("env", {}),
            "enabled": True
        }
        
        # Handle URL-based configs
        if "url" in server_config:
            config_data["type"] = "sse"  # Assume SSE for URL-based configs
            config_data["url"] = server_config["url"]
            config_data.pop("command", None)
            config_data.pop("args", None)
        
        # Handle options
        if "options" in server_config:
            config_data["options"] = server_config["options"]
        
        return config_data
    
    def extract_and_process_credentials(self, server_name: str, config_data: Dict[str, Any]) -> List[str]:
        """
        Extract credentials from server configuration and store them.
        
        Args:
            server_name: The name of the server
            config_data: The server configuration data
            
        Returns:
            List of processed credential keys
        """
        processed_keys = []
        
        # Skip if no credential manager
        if not self.credential_manager:
            logger.warning("No credential manager available, skipping credential extraction")
            return processed_keys
        
        # Process environment variables if present
        env_vars = config_data.get("env", {})
        for key, value in env_vars.items():
            # Check if this is a placeholder (${VAR_NAME})
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                # Extract actual variable name
                var_name = value[2:-1]
                
                # Check if this credential already exists
                existing_cred = self.credential_manager.get_credential(var_name)
                
                if existing_cred:
                    # Update server association for existing credential
                    if self.credential_manager:
                        # Get current servers or initialize empty set
                        current_servers = existing_cred.server_ids or set()
                        # Add current server
                        current_servers.add(server_name)
                        self.credential_manager.update_server_association(var_name, current_servers)
                    processed_keys.append(var_name)
                else:
                    # Create new credential as a placeholder (user will need to set actual value)
                    # Using empty value as placeholder
                    self.credential_manager.set_credential(
                        var_name, 
                        "", 
                        # Auto-detect type based on key name
                        description=f"Automatically detected from server '{server_name}'",
                        server_ids={server_name}
                    )
                    processed_keys.append(var_name)
                    logger.info(f"Created placeholder credential '{var_name}' for server '{server_name}'")
        
        return processed_keys
