"""Simplified MCP Client that delegates ALL STDIO servers to mcp-proxy.

This approach eliminates the complexity of managing STDIO connections directly.
All STDIO servers are accessed via mcp-proxy's HTTP/SSE endpoints.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
import aiohttp
from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)


class SimplifiedMCPClient:
    """A simplified MCP client that uses HTTP/SSE for everything.
    
    Key principle: We NEVER spawn STDIO processes directly. 
    All STDIO servers are managed by mcp-proxy and accessed via HTTP/SSE.
    """
    
    def __init__(self, proxy_base_url: str = "http://127.0.0.1:9090"):
        self.proxy_base_url = proxy_base_url.rstrip('/')
        self.sessions: Dict[str, ClientSession] = {}
        self.server_tools: Dict[str, List[Any]] = {}
        self._server_info: Dict[str, Dict[str, Any]] = {}
        self._sse_contexts: Dict[str, Any] = {}
    
    async def connect_server(self, name: str, config: dict) -> Dict[str, Any]:
        """Connect to a server via HTTP/SSE endpoint.
        
        For STDIO servers configured with 'via: proxy', we connect to the 
        mcp-proxy endpoint. For direct HTTP/SSE servers, we connect directly.
        """
        try:
            server_type = config.get("type", "stdio")
            via = config.get("via", "direct")
            
            # Determine endpoint URL
            if server_type == "stdio" and via == "proxy":
                # STDIO via proxy - use proxy's SSE endpoint
                endpoint_url = f"{self.proxy_base_url}/{name}/sse"
                connection_type = "proxy-sse"
            elif server_type in ["sse", "streamable-http"]:
                # Direct HTTP/SSE server
                endpoint_url = config.get("url")
                if not endpoint_url:
                    return {
                        "status": "error",
                        "message": "No URL configured for HTTP/SSE server",
                        "connection_path": "unknown"
                    }
                connection_type = "direct-sse"
            else:
                return {
                    "status": "error", 
                    "message": f"Unsupported configuration: type={server_type}, via={via}",
                    "connection_path": "unknown"
                }
            
            logger.info(f"Connecting to {name} via {connection_type} at {endpoint_url}")
            
            # Connect via SSE client
            headers = config.get("headers", {})
            
            # Create SSE connection
            context = sse_client(endpoint_url, headers=headers)
            self._sse_contexts[name] = context
            
            # Enter context and initialize session
            read_stream, write_stream = await asyncio.wait_for(
                context.__aenter__(), 
                timeout=30
            )
            
            session = ClientSession(read_stream, write_stream)
            self.sessions[name] = session
            
            # Initialize with retries
            max_retries = 3
            for retry in range(max_retries):
                try:
                    await asyncio.wait_for(session.initialize(), timeout=10)
                    break
                except asyncio.TimeoutError:
                    if retry < max_retries - 1:
                        logger.warning(f"Init timeout for {name}, retry {retry+1}/{max_retries}")
                        await asyncio.sleep(1.0)
                    else:
                        raise
            
            # Discover tools
            try:
                tools_response = await asyncio.wait_for(session.list_tools(), timeout=30)
                tools = tools_response.tools if hasattr(tools_response, 'tools') else []
                self.server_tools[name] = tools
                logger.info(f"Discovered {len(tools)} tools from {name}")
                
                # Log tool names for debugging
                for tool in tools[:5]:  # First 5 for brevity
                    tool_name = getattr(tool, "name", "unknown")
                    logger.debug(f"  - {tool_name}")
                if len(tools) > 5:
                    logger.debug(f"  ... and {len(tools)-5} more")
                    
            except Exception as e:
                logger.warning(f"Tool discovery failed for {name}: {e}")
                self.server_tools[name] = []
            
            # Store server info
            self._server_info[name] = {
                "config": config,
                "connected": True,
                "endpoint": endpoint_url,
                "connection_type": connection_type,
                "tools_count": len(self.server_tools[name])
            }
            
            return {
                "status": "success",
                "message": f"Connected to {name}",
                "tools_count": len(self.server_tools[name]),
                "connection_path": connection_type
            }
            
        except Exception as e:
            logger.error(f"Failed to connect to {name}: {e}")
            
            # Cleanup on error
            if name in self._sse_contexts:
                try:
                    await self._sse_contexts[name].__aexit__(None, None, None)
                except:
                    pass
                del self._sse_contexts[name]
            
            if name in self.sessions:
                del self.sessions[name]
            
            self._server_info[name] = {
                "config": config,
                "connected": False,
                "error": str(e)
            }
            self.server_tools[name] = []
            
            return {
                "status": "error",
                "message": str(e),
                "tools_count": 0,
                "connection_path": "failed"
            }
    
    async def disconnect_server(self, name: str) -> None:
        """Disconnect from a server."""
        # Close SSE context if exists
        if name in self._sse_contexts:
            try:
                await self._sse_contexts[name].__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing SSE connection for {name}: {e}")
            finally:
                del self._sse_contexts[name]
        
        # Remove session
        if name in self.sessions:
            del self.sessions[name]
        
        # Update server info
        if name in self._server_info:
            self._server_info[name]["connected"] = False
    
    async def check_proxy_health(self) -> bool:
        """Check if mcp-proxy is running and responsive."""
        try:
            async with aiohttp.ClientSession() as session:
                # Try multiple possible health endpoints
                for endpoint in ['/health', '/status', '/', '/servers']:
                    try:
                        url = f"{self.proxy_base_url}{endpoint}"
                        async with session.get(url, timeout=2) as resp:
                            if resp.status in [200, 404, 501]:
                                return True
                    except:
                        continue
            return False
        except:
            return False
    
    async def wait_for_proxy(self, timeout: int = 30) -> bool:
        """Wait for mcp-proxy to become available."""
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < timeout:
            if await self.check_proxy_health():
                logger.info("MCP Proxy is ready")
                return True
            await asyncio.sleep(0.5)
        logger.error(f"MCP Proxy not available after {timeout}s")
        return False
    
    async def execute_tool(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        """Execute a tool on a connected server."""
        if server_name not in self.sessions:
            raise RuntimeError(f"Server {server_name} not connected")
        
        session = self.sessions[server_name]
        try:
            result = await session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            raise
