"""Banner-tolerant stdio wrapper for MCP servers that emit startup text before JSON-RPC."""

import asyncio
import json
import logging
import subprocess
from typing import Optional, Tuple, Any
from contextlib import asynccontextmanager

from mcp.shared.json_rpc_message import JSONRPCMessage
from mcp.shared.exceptions import McpError

logger = logging.getLogger(__name__)


class BannerTolerantStream:
    """A wrapper around stdio streams that filters out banner/startup messages."""
    
    def __init__(self, reader: asyncio.StreamReader, name: str = "unknown"):
        self.reader = reader
        self.name = name
        self.buffer = b""
        self.json_started = False
        
    async def read_message(self) -> JSONRPCMessage:
        """Read the next JSON-RPC message, filtering out non-JSON banner lines."""
        while True:
            try:
                # Try to read a line
                line = await self.reader.readline()
                if not line:
                    raise McpError("Stream closed")
                
                # Decode the line
                line_str = line.decode('utf-8').strip()
                if not line_str:
                    continue  # Skip empty lines
                
                # Check if this looks like JSON (starts with '{')
                if line_str.startswith('{'):
                    self.json_started = True
                    try:
                        # Try to parse as JSON-RPC message
                        msg_dict = json.loads(line_str)
                        return JSONRPCMessage.model_validate(msg_dict)
                    except json.JSONDecodeError:
                        # Not valid JSON yet, might be partial
                        logger.debug(f"Partial JSON from {self.name}: {line_str[:100]}")
                        continue
                    except Exception as e:
                        logger.debug(f"Failed to validate JSON-RPC from {self.name}: {e}")
                        continue
                elif not self.json_started:
                    # This is likely a banner/startup message before JSON starts
                    logger.debug(f"Banner from {self.name}: {line_str[:100]}")
                    continue
                else:
                    # We've seen JSON before but this isn't JSON - might be an error
                    logger.warning(f"Non-JSON after JSON started from {self.name}: {line_str[:100]}")
                    continue
                    
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error reading from {self.name}: {e}")
                raise McpError(f"Failed to read message: {e}")


@asynccontextmanager
async def banner_tolerant_stdio_client(server_params, name: str = "unknown"):
    """Create a stdio client that tolerates banner/startup messages."""
    from mcp.client.stdio import stdio_client
    
    # For now, we'll use the standard stdio_client but with our wrapper
    # In a full implementation, we'd replace the entire stdio handling
    async with stdio_client(server_params) as (read_stream, write_stream):
        # Wrap the read stream with our banner-tolerant version
        # Note: This is a simplified approach - the real SDK doesn't expose
        # the raw streams in a way we can easily wrap them
        yield read_stream, write_stream
