"""MCP Client Manager using named pipe for stdout/stderr redirection.

This approach is inspired by stdout-mcp-server and provides a clean solution
to the stdout pollution problem by redirecting all non-protocol output to
a named pipe that can be monitored separately.
"""

import asyncio
import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)


class PipedMCPClient:
    """MCP client that uses named pipes to redirect console output."""
    
    # Named pipe paths
    PIPE_PATH_UNIX = "/tmp/mcp_stdout_pipe"
    PIPE_PATH_WINDOWS = r"\\.\pipe\mcp_stdout_pipe"
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.server_tools: Dict[str, List[Any]] = {}
        self._stdio_contexts: Dict[str, Any] = {}
        
        # Determine pipe path based on OS
        self.pipe_path = self.PIPE_PATH_WINDOWS if platform.system() == "Windows" else self.PIPE_PATH_UNIX
        
        # Ensure pipe exists (Unix only, Windows creates on first use)
        if platform.system() != "Windows":
            self._ensure_pipe_exists()
    
    def _ensure_pipe_exists(self):
        """Ensure the log file exists (Unix/Mac only)."""
        # Use a regular file instead of FIFO to avoid blocking issues
        # A real implementation would use stdout-mcp-server with proper FIFO handling
        if not os.path.exists(self.pipe_path):
            Path(self.pipe_path).touch()
            logger.info(f"Created log file at {self.pipe_path}")
    
    def _get_redirected_stdio_params(self, config: dict) -> StdioServerParameters:
        """Create STDIO parameters with stderr redirected to named pipe.
        
        This prevents banner text from corrupting the JSON-RPC protocol
        by sending all stderr output to a separate pipe.
        """
        command = config.get("command", "")
        args = config.get("args", [])
        env = dict(config.get("env", {}))
        
        # Add banner suppression env vars (best effort)
        env.update({
            "PYTHONUNBUFFERED": "1",
            "FASTMCP_NO_BANNER": "1",
            "FASTMCP_DISABLE_BANNER": "1",
            "NO_COLOR": "1",
            "CI": "1",
        })
        
        # Resolve command path if needed
        if not os.path.isabs(command):
            resolved = shutil.which(command)
            if resolved:
                command = resolved
        
        # Option 1: Direct approach - let MCP SDK handle stdio
        # This works if the server respects env vars
        if os.getenv("DISABLE_PIPE_REDIRECT"):
            return StdioServerParameters(
                command=command,
                args=args,
                env=env,
                stderr="ignore"  # Critical: ignore stderr to prevent corruption
            )
        
        # Option 2: Shell wrapper with redirect (more robust)
        if platform.system() == "Windows":
            # Windows: use cmd.exe with redirect
            shell_command = f'"{command}" {" ".join(args)} 2>"{self.pipe_path}"'
            return StdioServerParameters(
                command="cmd.exe",
                args=["/c", shell_command],
                env=env
            )
        else:
            # Unix/Mac: use sh with redirect
            # Build escaped command
            escaped_args = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in args)
            shell_command = f'{command} {escaped_args} 2>{self.pipe_path}'
            
            return StdioServerParameters(
                command="sh",
                args=["-c", shell_command],
                env=env
            )
    
    async def connect_stdio_server(self, name: str, config: dict) -> Dict[str, Any]:
        """Connect to a STDIO server with pipe redirection."""
        try:
            logger.info(f"Connecting to STDIO server {name} with pipe redirect to {self.pipe_path}")
            
            # Get parameters with redirect
            server_params = self._get_redirected_stdio_params(config)
            
            # Connect using standard stdio_client
            context = stdio_client(server_params)
            self._stdio_contexts[name] = context
            
            # Enter context
            read_stream, write_stream = await asyncio.wait_for(
                context.__aenter__(),
                timeout=30
            )
            
            # Create session
            session = ClientSession(read_stream, write_stream)
            
            # Initialize session
            await asyncio.wait_for(session.initialize(), timeout=30)
            
            # Store session
            self.sessions[name] = session
            
            # Discover tools
            await self._discover_tools(name, session)
            
            logger.info(f"Successfully connected to {name} with {len(self.server_tools.get(name, []))} tools")
            
            return {
                "status": "success",
                "message": f"Connected to {name}",
                "tools_count": len(self.server_tools.get(name, [])),
                "pipe_redirect": True,
                "pipe_path": self.pipe_path
            }
            
        except Exception as e:
            logger.error(f"Failed to connect to {name}: {e}")
            await self._cleanup_stdio(name)
            return {
                "status": "error",
                "message": str(e),
                "tools_count": 0
            }
    
    async def connect_sse_server(self, name: str, config: dict) -> Dict[str, Any]:
        """Connect to an SSE server (no pipe redirect needed)."""
        try:
            url = config.get("url")
            headers = config.get("headers", {})
            
            logger.info(f"Connecting to SSE server {name} at {url}")
            
            # Create SSE connection
            if headers:
                context = sse_client(url, headers=headers)
            else:
                context = sse_client(url)
            
            # Connect
            read_stream, write_stream = await asyncio.wait_for(
                context.__aenter__(),
                timeout=30
            )
            
            # Create session
            session = ClientSession(read_stream, write_stream)
            
            # Initialize
            await asyncio.wait_for(session.initialize(), timeout=30)
            
            # Store
            self.sessions[name] = session
            
            # Discover tools
            await self._discover_tools(name, session)
            
            return {
                "status": "success",
                "message": f"Connected to {name}",
                "tools_count": len(self.server_tools.get(name, []))
            }
            
        except Exception as e:
            logger.error(f"Failed to connect to SSE server {name}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "tools_count": 0
            }
    
    async def _discover_tools(self, name: str, session: ClientSession):
        """Discover tools from a connected session."""
        try:
            response = await asyncio.wait_for(
                session.list_tools(),
                timeout=10
            )
            tools = response.tools if hasattr(response, 'tools') else []
            self.server_tools[name] = tools
            logger.info(f"Discovered {len(tools)} tools from {name}")
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
                        timeout=5
                    )
                except:
                    pass
                del self._stdio_contexts[name]
            if name in self.sessions:
                del self.sessions[name]
        except Exception as e:
            logger.debug(f"Cleanup error for {name}: {e}")
    
    async def execute_tool(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        """Execute a tool on a server."""
        session = self.sessions.get(server_name)
        if not session:
            raise ValueError(f"Server {server_name} not connected")
        
        try:
            result = await session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name} on {server_name}: {e}")
            raise
    
    async def disconnect_all(self):
        """Disconnect all servers."""
        for name in list(self.sessions.keys()):
            await self._cleanup_stdio(name)
    
    def read_pipe_logs(self, lines: int = 50) -> List[str]:
        """Read recent logs from the named pipe (for debugging).
        
        Note: This is a simple implementation. In production, use
        stdout-mcp-server for proper log management.
        """
        if not os.path.exists(self.pipe_path):
            return []
        
        try:
            with open(self.pipe_path, 'r') as f:
                all_lines = f.readlines()
                return all_lines[-lines:]
        except Exception as e:
            logger.error(f"Error reading pipe logs: {e}")
            return []
