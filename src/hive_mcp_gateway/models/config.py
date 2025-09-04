"""Configuration models for Hive MCP Gateway configuration system."""

from __future__ import annotations
from typing import Dict, List, Any, Optional, Literal, Union
from pydantic import BaseModel, Field, validator, ConfigDict
from pathlib import Path


class ToolFilterConfig(BaseModel):
    """Configuration for filtering tools from MCP servers."""
    mode: Literal["allow", "deny"] = "allow"
    list: List[str] = Field(default_factory=list)


class ServerOptionsConfig(BaseModel):
    """Options configuration for MCP servers."""
    tool_filter: Optional[ToolFilterConfig] = Field(default=None, alias="toolFilter")
    timeout: Optional[int] = None
    retry_count: Optional[int] = Field(default=3, alias="retryCount")
    batch_size: Optional[int] = Field(default=10, alias="batchSize")

    class Config:
        validate_by_name = True


class NoAuthConfig(BaseModel):
    """No authentication configuration."""
    type: Literal["none"] = "none"


class BearerAuthConfig(BaseModel):
    """Bearer token authentication configuration."""
    type: Literal["bearer"] = "bearer"
    token: str


class BasicAuthConfig(BaseModel):
    """Basic authentication configuration."""
    type: Literal["basic"] = "basic"
    username: str
    password: str


class AuthenticationConfig(BaseModel):
    """Authentication configuration for MCP servers."""
    config: Union[NoAuthConfig, BearerAuthConfig, BasicAuthConfig] = Field(
        default_factory=NoAuthConfig, discriminator="type"
    )

    @validator('config', pre=True)
    def validate_auth_config(cls, v):
        """Validate authentication configuration."""
        if isinstance(v, dict):
            auth_type = v.get("type", "none")
            if auth_type == "none":
                return NoAuthConfig(**v)
            elif auth_type == "bearer":
                return BearerAuthConfig(**v)
            elif auth_type == "basic":
                return BasicAuthConfig(**v)
        return v


class HealthCheckConfig(BaseModel):
    """Health check configuration for MCP servers."""
    enabled: bool = True
    interval: int = 60  # seconds
    endpoint: Optional[str] = None  # For HTTP servers
    timeout: int = 10  # seconds


class ServerMetadata(BaseModel):
    """Metadata for MCP servers."""
    category: Optional[str] = None
    version: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class BackendServerConfig(BaseModel):
    """Configuration for a backend MCP server."""
    type: Literal["stdio", "sse", "streamable-http"] = "stdio"
    # Transport hint: direct stdio (default) or via external proxy supervisor
    via: Literal["direct", "proxy"] = "direct"
    
    # For stdio type
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    
    # For HTTP types (sse, streamable-http)
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    
    # Common options
    description: Optional[str] = None
    enabled: bool = True
    authentication: AuthenticationConfig = Field(default_factory=AuthenticationConfig)
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig, alias="healthCheck")
    metadata: ServerMetadata = Field(default_factory=ServerMetadata)
    options: Optional[ServerOptionsConfig] = None

    @validator('command')
    def validate_stdio_command(cls, v, values):
        """Validate that stdio type has command specified."""
        if values.get('type') == 'stdio' and values.get('via', 'direct') == 'direct' and not v:
            raise ValueError('command is required for stdio type servers')
        return v

    @validator('url')
    def validate_http_url(cls, v, values):
        """Validate that HTTP types have URL specified."""
        server_type = values.get('type')
        if server_type in ['sse', 'streamable-http'] and not v:
            raise ValueError(f'url is required for {server_type} type servers')
        return v


class ToolGatingSettings(BaseModel):
    """Settings for the Hive MCP Gateway application itself."""
    port: int = Field(default=8001, ge=1, le=65535)
    host: str = "0.0.0.0"
    log_level: Literal["debug", "info", "warning", "error"] = Field(default="info", alias="logLevel")
    auto_discover: bool = Field(default=True, alias="autoDiscover")
    max_tokens_per_request: int = Field(default=2000, alias="maxTokensPerRequest")
    max_tools_per_request: int = Field(default=10, alias="maxToolsPerRequest")
    config_watch_enabled: bool = Field(default=True, alias="configWatchEnabled")
    health_check_interval: int = Field(default=30, alias="healthCheckInterval")  # seconds
    connection_timeout: int = Field(default=10, alias="connectionTimeout")  # seconds
    # Gating defaults and optional proxy
    default_policy: Literal["deny", "allow"] = Field(default="deny", alias="defaultPolicy")
    proxy_url: Optional[str] = Field(default=None, alias="proxyUrl")
    manage_proxy: bool = Field(default=False, alias="manageProxy")
    auto_proxy_stdio: bool = Field(default=True, alias="autoProxyStdio")
    
    class Config:
        validate_by_name = True


class ToolGatingConfig(BaseModel):
    """Complete configuration for Hive MCP Gateway."""
    tool_gating: ToolGatingSettings = Field(default_factory=ToolGatingSettings, alias="toolGating")
    backend_mcp_servers: Dict[str, BackendServerConfig] = Field(
        default_factory=dict,
        alias="backendMcpServers"
    )
    
    class Config:
        validate_by_name = True

    @validator('backend_mcp_servers')
    def validate_server_names(cls, v):
        """Validate server names are valid identifiers."""
        for name in v.keys():
            if not name.replace('_', '').replace('-', '').isalnum():
                raise ValueError(f'Server name "{name}" must be alphanumeric with underscores/hyphens only')
        return v


class ServerStatus(BaseModel):
    """Status information for a backend MCP server."""
    model_config = ConfigDict(validate_by_name=True)
    
    name: str
    enabled: bool
    connected: bool
    last_seen: Optional[str] = None
    error_message: Optional[str] = None
    tool_count: int = 0
    health_status: Literal["healthy", "unhealthy", "unknown"] = "unknown"
    last_health_check: Optional[str] = None
    tags: List[str] = Field(default_factory=list)  # Added missing tags field


class MigrationConfig(BaseModel):
    """Configuration for migrating from existing installations."""
    source_path: Path
    backup_existing: bool = True
    merge_strategy: Literal["replace", "merge", "skip_existing"] = "merge"
    preserve_env_vars: bool = True


class ValidationResult(BaseModel):
    """Result of configuration validation."""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ProcessResult(BaseModel):
    """Result of processing MCP configuration snippets."""
    success: bool
    server_name: Optional[str] = None
    action: Literal["added", "updated", "skipped"] = "skipped"
    message: str
    errors: List[str] = Field(default_factory=list)


# Default configuration template
DEFAULT_CONFIG = ToolGatingConfig(
    tool_gating=ToolGatingSettings(
        port=8001,  # Non-interfering with existing installation on 8000
        host="0.0.0.0",
        log_level="info",
        auto_discover=True,
        max_tokens_per_request=2000,
        max_tools_per_request=10,
        config_watch_enabled=True,
        health_check_interval=30,
        connection_timeout=10
    ),
    backend_mcp_servers={}
)


# Alias for backwards compatibility with validation tests
ServerConfig = ToolGatingSettings
