"""MCP Client that filters out banner text before JSON-RPC starts.

This is a pragmatic solution that:
1. Starts the subprocess
2. Reads and discards non-JSON lines (the banner)
3. Then connects the MCP session once JSON starts
"""

import asyncio
import json
import logging
import subprocess
from typing import Dict, Any, List, Optional

from mcp import ClientSession

logger = logging.getLogger(__name__)


class BannerFilterClient:
    """MCP client that filters out banner text before JSON-RPC communication."""
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.server_tools: Dict[str, List[Any]] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
    
    async def connect_stdio_server(self, name: str, config: dict) -> Dict[str, Any]:
        """Connect to a STDIO server, filtering out initial banner text."""
        import shutil
        
        try:
            # Resolve command
            command = config.get("command", "")
            if not command:
                raise ValueError("No command specified")
                
            # Find command in PATH if needed
            if not "/" in command:
                resolved = shutil.which(command)
                if resolved:
                    command = resolved
                else:
                    raise ValueError(f"Command not found: {command}")
            
            args = config.get("args", [])
            env = dict(config.get("env", {}))
            
            # Add all possible banner suppression env vars
            env.update({
                "PYTHONUNBUFFERED": "1",
                "FASTMCP_NO_BANNER": "1",
                "FASTMCP_DISABLE_BANNER": "1",
                "FASTMCP_QUIET": "1",
                "NO_COLOR": "1",
                "CI": "1",
                "TERM": "dumb",
                "JSON_ONLY": "1",
            })
            
            logger.info(f"Starting subprocess for {name}: {command} {' '.join(args)}")
            
            # Start the subprocess
            proc = await asyncio.create_subprocess_exec(
                command,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.DEVNULL,  # Ignore stderr completely
                env=env
            )
            
            self.processes[name] = proc
            
            # Now we need to skip the banner and find the start of JSON-RPC
            # The first JSON-RPC message should be our initialize response
            logger.info(f"Filtering banner for {name}")
            
            # Send initialize request
            init_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "hive-gateway", "version": "0.1.0"}
                },
                "id": 1
            }
            
            # Write the initialize request
            request_str = json.dumps(init_request) + "\n"
            proc.stdin.write(request_str.encode())
            await proc.stdin.drain()
            
            # Read lines until we find JSON
            first_json = None
            max_lines = 100  # Safety limit
            for _ in range(max_lines):
                try:
                    line = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
                    if not line:
                        break
                    
                    line_str = line.decode('utf-8').strip()
                    if not line_str:
                        continue
                    
                    # Check if this looks like JSON
                    if line_str.startswith('{'):
                        try:
                            # Try to parse it
                            parsed = json.loads(line_str)
                            # Check if it's JSON-RPC
                            if 'jsonrpc' in parsed or 'result' in parsed or 'error' in parsed:
                                first_json = parsed
                                logger.info(f"Found first JSON-RPC message for {name}: {line_str[:100]}")
                                break
                        except json.JSONDecodeError:
                            # Not valid JSON, keep looking
                            pass
                    else:
                        # Banner line, ignore it
                        logger.debug(f"Skipping banner line: {line_str[:50]}")
                        
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for JSON-RPC from {name}")
                    break
            
            if not first_json:
                raise ValueError("No JSON-RPC response received after banner")
            
            # Now we have clean JSON-RPC communication!
            # Create a wrapper for the streams
            wrapper = FilteredStdioWrapper(proc)
            
            # Create MCP session
            session = ClientSession(wrapper, wrapper)
            
            # The first response should be our initialize response
            # Store it so the session can process it
            wrapper.queue_response(first_json)
            
            # Session is already initialized (we did it manually)
            self.sessions[name] = session
            
            # Discover tools
            await self._discover_tools(name, session)
            
            logger.info(f"Successfully connected to {name} with {len(self.server_tools.get(name, []))} tools")
            
            return {
                "status": "success",
                "message": f"Connected to {name}",
                "tools_count": len(self.server_tools.get(name, [])),
                "banner_filtered": True
            }
            
        except Exception as e:
            logger.error(f"Failed to connect to {name}: {e}")
            if name in self.processes:
                proc = self.processes[name]
                try:
                    proc.terminate()
                except:
                    pass
                del self.processes[name]
            return {
                "status": "error",
                "message": str(e),
                "tools_count": 0
            }
    
    async def _discover_tools(self, name: str, session: ClientSession):
        """Discover tools from a connected session."""
        try:
            # Send list_tools request directly
            list_tools_request = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": "list_tools"
            }
            
            proc = self.processes.get(name)
            if proc:
                # Send request
                request_str = json.dumps(list_tools_request) + "\n"
                proc.stdin.write(request_str.encode())
                await proc.stdin.drain()
                
                # Read response
                response_line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
                response = json.loads(response_line.decode('utf-8'))
                
                if 'result' in response and 'tools' in response['result']:
                    tools = response['result']['tools']
                    # Convert to tool objects
                    tool_objects = []
                    for tool in tools:
                        tool_obj = type('Tool', (), {
                            'name': tool.get('name'),
                            'description': tool.get('description', ''),
                            'inputSchema': tool.get('inputSchema', {})
                        })()
                        tool_objects.append(tool_obj)
                    self.server_tools[name] = tool_objects
                    logger.info(f"Discovered {len(tool_objects)} tools from {name}")
                else:
                    logger.warning(f"No tools in response from {name}")
                    self.server_tools[name] = []
        except Exception as e:
            logger.error(f"Error discovering tools from {name}: {e}")
            self.server_tools[name] = []
    
    async def disconnect_all(self):
        """Disconnect all servers."""
        for name, proc in list(self.processes.items()):
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5)
            except:
                try:
                    proc.kill()
                except:
                    pass
        self.processes.clear()
        self.sessions.clear()
        self.server_tools.clear()


class FilteredStdioWrapper:
    """Wrapper that provides MCP-compatible stream interface."""
    
    def __init__(self, proc):
        self.proc = proc
        self.response_queue = asyncio.Queue()
    
    def queue_response(self, response):
        """Queue a response to be read."""
        self.response_queue.put_nowait(response)
    
    async def send(self, data):
        """Send data to the subprocess."""
        if isinstance(data, dict):
            data = json.dumps(data)
        if isinstance(data, str):
            data = data.encode('utf-8')
        if not data.endswith(b'\n'):
            data += b'\n'
        self.proc.stdin.write(data)
        await self.proc.stdin.drain()
    
    async def receive(self):
        """Receive data from the subprocess."""
        # Check if we have a queued response
        try:
            response = self.response_queue.get_nowait()
            if isinstance(response, dict):
                response = json.dumps(response)
            if isinstance(response, str):
                response = response.encode('utf-8')
            return response
        except asyncio.QueueEmpty:
            # Read from subprocess
            line = await self.proc.stdout.readline()
            return line
