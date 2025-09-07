"""Filtered STDIO transport that removes non-JSON content from stdout.

This solves the critical issue where MCP servers print banners to stdout,
corrupting the JSON-RPC protocol. By filtering at the subprocess level,
we ensure only valid JSON-RPC messages reach the MCP client.
"""

import asyncio
import json
import logging
import subprocess
from typing import Optional, List, Dict, Any, AsyncIterator
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FilteredStdioServerParameters:
    """Parameters for filtered STDIO server."""
    command: str
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None


class StdioFilter:
    """Filters non-JSON content from STDIO streams."""
    
    def __init__(self, name: str):
        self.name = name
        self.buffer = ""
        self.in_json = False
        self.brace_count = 0
        
    def process_chunk(self, data: bytes) -> List[bytes]:
        """Process a chunk of data and extract JSON-RPC messages.
        
        Returns list of complete JSON messages as bytes.
        """
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            # Non-UTF8 data, definitely not JSON
            return []
        
        messages = []
        current_msg = ""
        
        for char in text:
            if not self.in_json:
                # Looking for start of JSON
                if char == '{':
                    self.in_json = True
                    self.brace_count = 1
                    current_msg = '{'
                # Ignore non-JSON characters (banner text)
            else:
                # Inside JSON
                current_msg += char
                if char == '{':
                    self.brace_count += 1
                elif char == '}':
                    self.brace_count -= 1
                    if self.brace_count == 0:
                        # Complete JSON message
                        try:
                            # Validate it's actual JSON-RPC
                            msg = json.loads(current_msg)
                            if 'jsonrpc' in msg or 'method' in msg or 'id' in msg:
                                messages.append(current_msg.encode('utf-8'))
                                messages.append(b'\n')  # MCP expects newline-delimited
                        except json.JSONDecodeError:
                            logger.debug(f"Filtered invalid JSON from {self.name}: {current_msg[:50]}...")
                        finally:
                            self.in_json = False
                            current_msg = ""
        
        # Save incomplete message for next chunk
        if self.in_json:
            self.buffer = current_msg
        
        return messages


class FilteredStdioTransport:
    """STDIO transport with banner filtering."""
    
    def __init__(self, params: FilteredStdioServerParameters):
        self.params = params
        self.process: Optional[subprocess.Popen] = None
        self.read_queue: asyncio.Queue = asyncio.Queue()
        self.write_queue: asyncio.Queue = asyncio.Queue()
        self.filter = StdioFilter(params.command)
        self._tasks = []
        
    async def start(self) -> tuple:
        """Start the subprocess and filtering tasks."""
        # Prepare environment with banner suppression
        env = dict(self.params.env or {})
        env.update({
            "PYTHONUNBUFFERED": "1",
            "FASTMCP_NO_BANNER": "1",
            "FASTMCP_DISABLE_BANNER": "1",
            "FASTMCP_QUIET": "1",
            "NO_COLOR": "1",
            "CI": "1",
        })
        
        # Start subprocess with pipes
        self.process = await asyncio.create_subprocess_exec(
            self.params.command,
            *self.params.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,  # Ignore stderr completely
            env=env
        )
        
        # Start filter tasks
        self._tasks = [
            asyncio.create_task(self._filter_stdout()),
            asyncio.create_task(self._handle_stdin())
        ]
        
        # Return read/write streams compatible with MCP ClientSession
        return self, self
    
    async def _filter_stdout(self):
        """Filter stdout from subprocess, extracting only JSON-RPC messages."""
        while self.process and self.process.stdout:
            try:
                # Read chunks from process stdout
                chunk = await self.process.stdout.read(1024)
                if not chunk:
                    break
                
                # Filter out non-JSON content
                messages = self.filter.process_chunk(chunk)
                
                # Queue valid messages for MCP client
                for msg in messages:
                    await self.read_queue.put(msg)
                    
            except Exception as e:
                logger.error(f"Error filtering stdout: {e}")
                break
    
    async def _handle_stdin(self):
        """Forward messages from MCP client to subprocess stdin."""
        while self.process and self.process.stdin:
            try:
                data = await self.write_queue.get()
                if data is None:
                    break
                    
                self.process.stdin.write(data)
                await self.process.stdin.drain()
                
            except Exception as e:
                logger.error(f"Error writing to stdin: {e}")
                break
    
    async def read(self, n: int = -1) -> bytes:
        """Read filtered data (MCP SDK compatibility)."""
        data = await self.read_queue.get()
        return data if data else b''
    
    async def write(self, data: bytes):
        """Write data to subprocess (MCP SDK compatibility)."""
        await self.write_queue.put(data)
    
    async def receive(self) -> bytes:
        """Receive data from subprocess (MCP SDK StreamReader compatibility)."""
        data = await self.read_queue.get()
        return data if data else b''
    
    async def send(self, data: Any):
        """Send data to subprocess (MCP SDK StreamWriter compatibility)."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        elif not isinstance(data, bytes):
            data = json.dumps(data).encode('utf-8')
        await self.write_queue.put(data)
    
    async def close(self):
        """Clean up subprocess and tasks."""
        # Signal tasks to stop
        await self.write_queue.put(None)
        
        # Terminate process
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except:
                self.process.kill()
        
        # Cancel tasks
        for task in self._tasks:
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)


from contextlib import asynccontextmanager

@asynccontextmanager
async def filtered_stdio_client(params: FilteredStdioServerParameters):
    """Create a filtered STDIO client that removes banner text.
    
    This is a drop-in replacement for mcp.client.stdio.stdio_client
    that filters out non-JSON content from stdout.
    """
    transport = FilteredStdioTransport(params)
    read_stream, write_stream = await transport.start()
    
    try:
        yield read_stream, write_stream
    finally:
        await transport.close()
