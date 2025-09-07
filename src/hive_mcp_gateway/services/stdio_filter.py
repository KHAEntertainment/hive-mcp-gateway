"""STDIO stream filter to remove banner text and non-JSON content."""

import asyncio
import json
import logging
from typing import Optional, AsyncIterator

logger = logging.getLogger(__name__)


class StdioStreamFilter:
    """Filters non-JSON content from STDIO streams to prevent protocol corruption."""
    
    def __init__(self, name: str):
        self.name = name
        self.buffer = ""
        self.in_json = False
        self.brace_count = 0
        
    async def filter_stream(self, read_stream, write_stream):
        """
        Create filtered streams that remove banner text and only pass valid JSON-RPC.
        
        This wraps the raw STDIO streams and filters out any non-JSON content
        like banners, warnings, or debug output that would corrupt the MCP protocol.
        """
        # Create new streams for the filtered content
        filtered_read, filtered_write = asyncio.Queue(), asyncio.Queue()
        
        async def filter_input():
            """Filter incoming data from the STDIO server."""
            try:
                async for chunk in self._read_chunks(read_stream):
                    # Look for JSON-RPC messages (start with '{')
                    filtered = self._filter_chunk(chunk)
                    if filtered:
                        await filtered_write.put(filtered)
            except Exception as e:
                logger.error(f"Error filtering input for {self.name}: {e}")
                
        async def forward_output():
            """Forward output to the STDIO server unchanged."""
            try:
                while True:
                    data = await filtered_read.get()
                    await write_stream.send(data)
            except Exception as e:
                logger.error(f"Error forwarding output for {self.name}: {e}")
                
        # Start filter tasks
        asyncio.create_task(filter_input())
        asyncio.create_task(forward_output())
        
        return filtered_read, filtered_write
        
    def _filter_chunk(self, chunk: str) -> Optional[str]:
        """
        Filter a chunk of text to extract only valid JSON-RPC messages.
        
        This handles cases where:
        - Banners are printed before JSON
        - Multiple JSON messages are in one chunk
        - JSON messages are split across chunks
        """
        result = []
        
        for char in chunk:
            if char == '{':
                self.in_json = True
                self.brace_count = 1
                self.buffer = '{'
            elif self.in_json:
                self.buffer += char
                if char == '{':
                    self.brace_count += 1
                elif char == '}':
                    self.brace_count -= 1
                    if self.brace_count == 0:
                        # Complete JSON object found
                        try:
                            # Validate it's actual JSON
                            json.loads(self.buffer)
                            result.append(self.buffer)
                        except json.JSONDecodeError:
                            logger.debug(f"Invalid JSON filtered from {self.name}: {self.buffer[:100]}")
                        finally:
                            self.in_json = False
                            self.buffer = ""
                            
        return ''.join(result) if result else None
        
    async def _read_chunks(self, stream) -> AsyncIterator[str]:
        """Read chunks from a stream."""
        while True:
            try:
                chunk = await stream.receive()
                if chunk:
                    yield chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
            except Exception as e:
                logger.error(f"Error reading from {self.name}: {e}")
                break


class FilteredStdioClient:
    """Drop-in replacement for stdio_client that filters banner text."""
    
    @staticmethod
    async def create(server_params, name: str = "server"):
        """
        Create a filtered STDIO client connection.
        
        This wraps the standard stdio_client and adds filtering to remove
        any non-JSON content that would corrupt the protocol.
        """
        from mcp.client.stdio import stdio_client
        
        # Create the raw STDIO connection
        async with stdio_client(server_params) as (raw_read, raw_write):
            # Create and apply filter
            filter = StdioStreamFilter(name)
            filtered_read, filtered_write = await filter.filter_stream(raw_read, raw_write)
            
            yield filtered_read, filtered_write
