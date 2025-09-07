"""MCP Client Manager that uses Node.js wrapper for clean STDIO handling.

This uses the stdio_wrapper.js script to prevent banner corruption in STDIO servers.
The wrapper uses mcps-logger or fallback filtering to keep stdout clean for JSON-RPC.
"""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)


class WrappedMCPClient:
    """MCP client that uses Node.js wrapper for STDIO servers."""
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.server_tools: Dict[str, List[Any]] = {}
        self._stdio_contexts: Dict[str, Any] = {}
        
        # Find Node.js
        self.node_path = shutil.which("node")
        if not self.node_path:
            raise RuntimeError("Node.js not found. Please install Node.js.")
        
        # Find wrapper script
        wrapper_dir = Path(__file__).parent
        self.wrapper_path = wrapper_dir / "stdio_wrapper.js"
        if not self.wrapper_path.exists():
            raise RuntimeError(f"Wrapper script not found: {self.wrapper_path}")
    
    async def connect_stdio_server(self, name: str, config: dict) -> Dict[str, Any]:
        """Connect to a STDIO server using the Node.js wrapper.
        
        The wrapper prevents banner text from corrupting the JSON-RPC protocol.
        """
        try:
            logger.info(f"Connecting to STDIO server {name} via wrapper")
            
            # Original command and args
            original_command = config.get("command", "")
            original_args = config.get("args", [])
            
            # Resolve command path if needed
            if not os.path.isabs(original_command):
                resolved = shutil.which(original_command)
                if resolved:
                    original_command = resolved
            
            # New command: node wrapper.js <original_command> <args...>
            wrapped_command = self.node_path
            wrapped_args = [
                str(self.wrapper_path),
                original_command,
                *original_args
            ]
            
            # Build environment
            env = dict(config.get("env", {}))
            env.update({
                "NODE_ENV": "development",  # Enable mcps-logger patches
                "PYTHONUNBUFFERED": "1",
                "FASTMCP_NO_BANNER": "1",
            })
            
            # Create server parameters with wrapped command
            server_params = StdioServerParameters(
                command=wrapped_command,
                args=wrapped_args,
                env=env
            )
            
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
                "wrapped": True
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
        """Connect to an SSE server (no wrapper needed)."""
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
