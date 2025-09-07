"""Filtered STDIO transport that removes non-JSON content from stdout.

This solves the critical issue where MCP servers print banners to stdout,
corrupting the JSON-RPC protocol. By filtering at the subprocess level,
we ensure only valid JSON-RPC messages reach the MCP client.
"""

import asyncio
import json
import logging
import re
import subprocess
import sys
from typing import Optional, List, Dict, Any, TextIO
from dataclasses import dataclass
from contextlib import asynccontextmanager

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp import types
from mcp.shared.session import SessionMessage
from mcp.client.stdio import get_default_environment

logger = logging.getLogger(__name__)


@dataclass
class FilteredStdioServerParameters:
    """Parameters for filtered STDIO server."""
    command: str
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    encoding: str = "utf-8"
    encoding_error_handler: str = "replace"
    cwd: Optional[str] = None


# Default banner patterns to filter out
DEFAULT_BANNER_PATTERNS = [
    r"^Welcome to.*",
    r"^Starting.*server.*",
    r"^Server listening.*",
    r"^Using.*",
    r"^Loading.*",
    r"^Initializing.*",
    r"^\s*$",  # Empty lines
    r"^[─═━┈┅┄┃│┌┐└┘├┤┬┴┼╔╗╚╝╠╣╦╩╬║╒╓╔╕╖╗╘╙╚╛╜╝]+",  # Box drawing characters
    r"^\s*\*+\s*$",  # Asterisk lines
    r"^\s*-+\s*$",  # Dash lines
]


class BannerFilter:
    """Filters banner text and extracts JSON-RPC messages."""
    
    def __init__(self, name: str, patterns: Optional[List[str]] = None):
        self.name = name
        self.patterns = [re.compile(p) for p in (patterns or DEFAULT_BANNER_PATTERNS)]
        self.buffer = ""
        self.filtered_count = 0
        
    def is_banner_line(self, line: str) -> bool:
        """Check if a line matches banner patterns."""
        for pattern in self.patterns:
            if pattern.match(line):
                return True
        return False
    
    def extract_json_messages(self, text: str) -> List[str]:
        """Extract complete JSON-RPC messages from text.
        
        Returns list of JSON message strings.
        """
        # Add text to buffer
        self.buffer += text
        
        # Split on newlines to get complete lines
        lines = self.buffer.split("\n")
        
        # Keep the last incomplete line in the buffer
        self.buffer = lines[-1]
        
        messages = []
        for line in lines[:-1]:
            line = line.strip()
            if not line:
                continue
                
            # Check if it's a banner line
            if self.is_banner_line(line):
                if self.filtered_count < 100:  # Limit debug logging
                    logger.debug(f"Filtered banner from {self.name}: {line[:80]}")
                self.filtered_count += 1
                continue
            
            # Try to parse as JSON
            if line.startswith('{') and line.endswith('}'):
                try:
                    msg = json.loads(line)
                    # Validate it's a JSON-RPC message
                    if 'jsonrpc' in msg or 'method' in msg or 'id' in msg or 'result' in msg or 'error' in msg:
                        messages.append(line)
                    else:
                        logger.debug(f"Filtered non-JSON-RPC from {self.name}: {line[:80]}")
                except json.JSONDecodeError:
                    logger.debug(f"Filtered invalid JSON from {self.name}: {line[:80]}")
            else:
                # Not JSON, likely banner text
                if self.filtered_count < 100:
                    logger.debug(f"Filtered non-JSON line from {self.name}: {line[:80]}")
                self.filtered_count += 1
        
        return messages


@asynccontextmanager
async def filtered_stdio_client(
    server: FilteredStdioServerParameters, 
    errlog: TextIO = sys.stderr
):
    """Create a filtered STDIO client that removes banner text.
    
    This is a drop-in replacement for mcp.client.stdio.stdio_client
    that filters out non-JSON content from stdout.
    """
    # Create memory streams for communication with ClientSession
    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]
    
    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)
    
    # Prepare environment with banner suppression
    env = dict(server.env or {})
    env.update(get_default_environment())
    env.update({
        "PYTHONUNBUFFERED": "1",
        "FASTMCP_NO_BANNER": "1",
        "FASTMCP_DISABLE_BANNER": "1",
        "FASTMCP_QUIET": "1",
        "NO_COLOR": "1",
        "CI": "1",
    })
    
    # Resolve command path
    import shutil
    command = shutil.which(server.command)
    if not command:
        raise FileNotFoundError(f"Command not found: {server.command}")
    
    # Create subprocess
    process = await asyncio.create_subprocess_exec(
        command,
        *(server.args or []),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=server.cwd
    )
    
    # Create banner filter
    filter = BannerFilter(server.command)
    
    async def stdout_reader():
        """Read from subprocess stdout, filter banners, and forward to ClientSession."""
        assert process.stdout, "Process is missing stdout"
        
        try:
            async with read_stream_writer:
                while True:
                    # Read chunks from stdout
                    chunk = await process.stdout.read(4096)
                    if not chunk:
                        break
                    
                    # Decode and extract JSON messages
                    try:
                        text = chunk.decode(server.encoding, errors=server.encoding_error_handler)
                    except UnicodeDecodeError as e:
                        logger.warning(f"Unicode decode error from {server.command}: {e}")
                        continue
                    
                    # Extract valid JSON-RPC messages
                    messages = filter.extract_json_messages(text)
                    
                    for msg_str in messages:
                        try:
                            # Parse JSON-RPC message
                            message = types.JSONRPCMessage.model_validate_json(msg_str)
                            
                            # Wrap in SessionMessage and send to ClientSession
                            session_msg = SessionMessage(message=message)
                            await read_stream_writer.send(session_msg)
                            
                            # Debug logging
                            if hasattr(message, 'id'):
                                logger.debug(f"Received message {message.id} from {server.command}")
                        except Exception as exc:
                            # Send parsing exceptions to the stream
                            await read_stream_writer.send(exc)
                            logger.warning(f"Error parsing message from {server.command}: {exc}")
        except anyio.ClosedResourceError:
            pass
        except Exception as e:
            logger.error(f"Stdout reader error for {server.command}: {e}")
    
    async def stdin_writer():
        """Write messages from ClientSession to subprocess stdin."""
        assert process.stdin, "Process is missing stdin"
        
        try:
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    # Extract the inner message and serialize it
                    json_str = session_message.message.model_dump_json(
                        by_alias=True, exclude_none=True
                    )
                    
                    # Write to subprocess stdin
                    data = (json_str + "\n").encode(
                        encoding=server.encoding,
                        errors=server.encoding_error_handler
                    )
                    process.stdin.write(data)
                    await process.stdin.drain()
                    
                    # Debug logging
                    if hasattr(session_message.message, 'id'):
                        logger.debug(f"Sent message {session_message.message.id} to {server.command}")
        except anyio.ClosedResourceError:
            pass
        except Exception as e:
            logger.error(f"Stdin writer error for {server.command}: {e}")
    
    async def stderr_reader():
        """Read stderr for logging only."""
        assert process.stderr, "Process is missing stderr"
        
        try:
            while True:
                chunk = await process.stderr.read(4096)
                if not chunk:
                    break
                
                try:
                    text = chunk.decode(server.encoding, errors='replace')
                    for line in text.strip().split('\n'):
                        if line:
                            errlog.write(f"[{server.command}] {line}\n")
                            errlog.flush()
                except Exception:
                    pass
        except Exception:
            pass
    
    # Start all tasks
    async with anyio.create_task_group() as tg:
        tg.start_soon(stdout_reader)
        tg.start_soon(stdin_writer)  
        tg.start_soon(stderr_reader)
        
        try:
            yield read_stream, write_stream
        finally:
            # Clean up process
            if sys.platform == "win32":
                # Windows-specific termination
                process.terminate()
            else:
                process.terminate()
            
            # Wait for process to exit
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
            
            # Close streams
            await read_stream.aclose()
            await write_stream.aclose()
