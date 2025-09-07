"""Universal MCP Client Manager - Handles STDIO, SSE, and HTTP transports uniformly.

Inspired by Meta-MCP's approach to handling different transport types.
Key features:
- Proper STDIO stderr handling to prevent banner corruption
- Retry logic for all connection types
- Centralized session management
- Clean error handling and recovery
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client
import aiohttp

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """MCP transport types."""
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"
    STREAMABLE_HTTP = "streamable-http"


class StderrMode(Enum):
    """How to handle stderr from STDIO servers."""
    IGNORE = "ignore"  # Default - prevents banner corruption
    PIPE = "pipe"      # Capture and log
    INHERIT = "inherit"  # Pass through (dangerous - can corrupt protocol)


@dataclass
class ServerConfig:
    """Configuration for an MCP server."""
    name: str
    type: TransportType
    # STDIO config
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    stderr: StderrMode = StderrMode.IGNORE
    # HTTP/SSE config
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    # Common
    enabled: bool = True
    retry_count: int = 3
    retry_delay: float = 2.5
    timeout: float = 30.0


@dataclass
class ConnectedClient:
    """A connected MCP client with cleanup capability."""
    name: str
    client: ClientSession
    transport: Any
    cleanup_func: Optional[Any] = None
    
    async def cleanup(self):
        """Clean up the client connection."""
        try:
            if self.cleanup_func:
                await self.cleanup_func()
            elif hasattr(self.transport, 'close'):
                await self.transport.close()
        except Exception as e:
            logger.debug(f"Cleanup error for {self.name}: {e}")


class UniversalMCPClient:
    """Universal MCP client that handles all transport types properly."""
    
    def __init__(self):
        self.sessions: Dict[str, ConnectedClient] = {}
        self.server_tools: Dict[str, List[Any]] = {}
        self._stdio_contexts: Dict[str, Any] = {}
        
    async def connect_server(self, config: ServerConfig) -> Dict[str, Any]:
        """Connect to an MCP server using the appropriate transport.
        
        Returns:
            dict with status, message, tools_count, and connection details
        """
        # Check if already connected
        if config.name in self.sessions:
            existing = self.sessions[config.name]
            return {
                "status": "success",
                "message": f"Already connected to {config.name}",
                "tools_count": len(self.server_tools.get(config.name, [])),
                "transport": config.type.value
            }
        
        # Try to connect with retries
        for attempt in range(config.retry_count):
            try:
                if config.type == TransportType.STDIO:
                    result = await self._connect_stdio(config)
                elif config.type in [TransportType.SSE, TransportType.STREAMABLE_HTTP]:
                    result = await self._connect_sse(config)
                elif config.type == TransportType.HTTP:
                    result = await self._connect_http(config)
                else:
                    return {
                        "status": "error",
                        "message": f"Unsupported transport type: {config.type}",
                        "tools_count": 0
                    }
                
                if result["status"] == "success":
                    return result
                    
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1}/{config.retry_count} failed for {config.name}: {e}")
                if attempt < config.retry_count - 1:
                    await asyncio.sleep(config.retry_delay)
                else:
                    return {
                        "status": "error",
                        "message": f"Failed after {config.retry_count} attempts: {str(e)}",
                        "tools_count": 0
                    }
        
        return {
            "status": "error",
            "message": "Connection failed",
            "tools_count": 0
        }
    
    async def _connect_stdio(self, config: ServerConfig) -> Dict[str, Any]:
        """Connect to a STDIO MCP server with proper stderr handling."""
        try:
            logger.info(f"Connecting to STDIO server {config.name} with stderr={config.stderr.value}")
            
            # Build environment with banner suppression
            env = dict(config.env or {})
            env.update({
                # Python/FastMCP banner suppression
                "FASTMCP_NO_BANNER": "1",
                "FASTMCP_DISABLE_BANNER": "1",
                "FASTMCP_QUIET": "1",
                "PYTHONUNBUFFERED": "1",
                "PYTHONWARNINGS": "ignore",
                "NO_COLOR": "1",
                # Node.js banner suppression
                "NODE_NO_WARNINGS": "1",
                "DISABLE_BANNER": "1",
                "QUIET": "1",
                # Generic
                "SILENT": "1",
                "CI": "1",  # Many tools detect CI and suppress output
            })
            
            # Map stderr mode to MCP SDK parameter
            # Meta-MCP uses "ignore" by default which is the key to preventing corruption
            stderr_param = {
                StderrMode.IGNORE: "ignore",
                StderrMode.PIPE: "pipe", 
                StderrMode.INHERIT: "inherit"
            }.get(config.stderr, "ignore")
            
            server_params = StdioServerParameters(
                command=config.command,
                args=config.args or [],
                env=env,
                stderr=stderr_param  # Critical: Set to "ignore" to prevent banner corruption
            )
            
            # Create and connect
            context = stdio_client(server_params)
            self._stdio_contexts[config.name] = context
            
            # Enter context with timeout
            read_stream, write_stream = await asyncio.wait_for(
                context.__aenter__(),
                timeout=config.timeout
            )
            
            # Create session
            session = ClientSession(read_stream, write_stream)
            
            # Initialize with timeout
            await asyncio.wait_for(session.initialize(), timeout=config.timeout)
            
            # Store connected client
            connected = ConnectedClient(
                name=config.name,
                client=session,
                transport=context,
                cleanup_func=lambda: context.__aexit__(None, None, None)
            )
            self.sessions[config.name] = connected
            
            # Discover tools in background
            asyncio.create_task(self._discover_tools(config.name, session))
            
            logger.info(f"Successfully connected to STDIO server {config.name}")
            return {
                "status": "success",
                "message": f"Connected to {config.name}",
                "tools_count": 0,  # Will be updated async
                "transport": "stdio"
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout connecting to STDIO server {config.name}")
            await self._cleanup_stdio(config.name)
            raise
        except Exception as e:
            logger.error(f"Error connecting to STDIO server {config.name}: {e}")
            await self._cleanup_stdio(config.name)
            raise
    
    async def _connect_sse(self, config: ServerConfig) -> Dict[str, Any]:
        """Connect to an SSE MCP server."""
        try:
            logger.info(f"Connecting to SSE server {config.name} at {config.url}")
            
            # Transform localhost URLs if running in Docker
            url = config.url
            if os.getenv("USE_DOCKER_HOST") == "true":
                url = url.replace("localhost", "host.docker.internal")
                url = url.replace("127.0.0.1", "host.docker.internal")
            
            # Create SSE connection with headers if provided
            if config.headers:
                context = sse_client(url, headers=config.headers)
            else:
                context = sse_client(url)
            
            # Connect with timeout
            read_stream, write_stream = await asyncio.wait_for(
                context.__aenter__(),
                timeout=config.timeout
            )
            
            # Create session
            session = ClientSession(read_stream, write_stream)
            
            # Initialize
            await asyncio.wait_for(session.initialize(), timeout=config.timeout)
            
            # Store connected client
            connected = ConnectedClient(
                name=config.name,
                client=session,
                transport=context,
                cleanup_func=lambda: context.__aexit__(None, None, None)
            )
            self.sessions[config.name] = connected
            
            # Discover tools in background
            asyncio.create_task(self._discover_tools(config.name, session))
            
            logger.info(f"Successfully connected to SSE server {config.name}")
            return {
                "status": "success",
                "message": f"Connected to {config.name}",
                "tools_count": 0,
                "transport": "sse"
            }
            
        except Exception as e:
            logger.error(f"Error connecting to SSE server {config.name}: {e}")
            raise
    
    async def _connect_http(self, config: ServerConfig) -> Dict[str, Any]:
        """Connect to HTTP MCP server (mock for now)."""
        # For pure HTTP servers without SSE, we need a different approach
        # This is a placeholder that returns mock tools
        logger.info(f"Mock connection to HTTP server {config.name}")
        
        mock_tools = [
            type('MockTool', (), {
                'name': f'{config.name}_tool',
                'description': f'Mock tool for {config.name}',
                'inputSchema': {'type': 'object', 'properties': {}}
            })()
        ]
        
        self.server_tools[config.name] = mock_tools
        
        return {
            "status": "success",
            "message": f"Connected to HTTP server {config.name} (mock)",
            "tools_count": len(mock_tools),
            "transport": "http"
        }
    
    async def _discover_tools(self, name: str, session: ClientSession):
        """Discover tools from a connected session."""
        try:
            response = await asyncio.wait_for(
                session.list_tools(),
                timeout=30.0
            )
            tools = response.tools if hasattr(response, 'tools') else []
            self.server_tools[name] = tools
            logger.info(f"Discovered {len(tools)} tools from {name}")
            
            # Update registry if available
            try:
                from ..main import app
                registry = getattr(app.state, "registry", None)
                if registry:
                    registry.update_server_tool_count(name, len(tools))
            except:
                pass
                
        except Exception as e:
            logger.error(f"Error discovering tools from {name}: {e}")
            self.server_tools[name] = []
    
    async def _cleanup_stdio(self, name: str):
        """Clean up STDIO connection."""
        try:
            if name in self._stdio_contexts:
                context = self._stdio_contexts[name]
                try:
                    await asyncio.wait_for(
                        context.__aexit__(None, None, None),
                        timeout=5.0
                    )
                except:
                    pass
                del self._stdio_contexts[name]
            if name in self.sessions:
                del self.sessions[name]
        except Exception as e:
            logger.debug(f"Cleanup error for {name}: {e}")
    
    async def disconnect_server(self, name: str):
        """Disconnect from a server."""
        if name in self.sessions:
            client = self.sessions[name]
            await client.cleanup()
            del self.sessions[name]
        if name in self.server_tools:
            del self.server_tools[name]
        if name in self._stdio_contexts:
            del self._stdio_contexts[name]
    
    async def disconnect_all(self):
        """Disconnect from all servers."""
        names = list(self.sessions.keys())
        for name in names:
            await self.disconnect_server(name)
    
    def get_server_tools(self, name: str) -> List[Any]:
        """Get tools for a server."""
        return self.server_tools.get(name, [])
