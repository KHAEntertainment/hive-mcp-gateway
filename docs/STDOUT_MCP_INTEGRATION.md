# stdout-mcp-server Integration Strategy

## Overview

The [stdout-mcp-server](https://github.com/amitdeshmukh/stdout-mcp-server) provides a more elegant solution to the stdout pollution problem by creating a system-wide named pipe that captures all stdout/console output.

## How It Solves Our Problem

### Current Problem
- MCP servers print to stdout, corrupting JSON-RPC protocol
- Each server needs individual wrapping/filtering
- Complex, error-prone, server-specific solutions

### stdout-mcp-server Solution
- Creates a named pipe: `/tmp/stdout_pipe` (Unix/Mac) or `\\.\pipe\stdout_pipe` (Windows)
- ALL processes can redirect output to this pipe
- Clean separation between protocol (stdout) and logging (pipe)
- Can be queried via MCP tools for debugging

## Integration Architecture

```
┌─────────────────────────────────────────┐
│       Hive MCP Gateway (Port 8001)      │
│                                          │
│  ┌────────────────────────────────┐     │
│  │   MCP Client Manager           │     │
│  │                                │     │
│  │  Connects to MCP servers via:  │     │
│  │  - STDIO (with pipe redirect)  │     │
│  │  - SSE                         │     │
│  │  - HTTP                        │     │
│  └────────────────────────────────┘     │
└─────────────────────────────────────────┘
                    │
       ┌────────────┼────────────┐
       ↓            ↓            ↓
   STDIO Server  SSE Server  HTTP Server
       │
       ├── stdout → JSON-RPC Protocol
       └── stderr → /tmp/stdout_pipe (redirected)
                           │
                           ↓
                ┌──────────────────────┐
                │  stdout-mcp-server   │
                │                      │
                │  Captures all logs   │
                │  Provides MCP tools: │
                │  - get-logs          │
                └──────────────────────┘
```

## Implementation Plan

### Phase 1: Setup stdout-mcp-server
1. Install as a system service or Docker container
2. Ensure pipe is created at startup
3. Verify it's accessible from our gateway

### Phase 2: Modify STDIO Connection
Update our client manager to redirect stderr to the pipe:

```python
class MCPClientManager:
    def _get_stdio_params(self, config):
        # Redirect stderr to named pipe
        if platform.system() == "Windows":
            pipe_path = r"\\.\pipe\stdout_pipe"
        else:
            pipe_path = "/tmp/stdout_pipe"
        
        # Modified command to redirect stderr
        if platform.system() == "Windows":
            # Windows: use shell redirect
            wrapped_command = f"cmd /c {config['command']} {' '.join(config['args'])} 2>{pipe_path}"
            return StdioServerParameters(
                command="cmd",
                args=["/c", wrapped_command],
                env=config.get("env", {})
            )
        else:
            # Unix: use shell redirect
            wrapped_command = f"{config['command']} {' '.join(config['args'])} 2>{pipe_path}"
            return StdioServerParameters(
                command="sh",
                args=["-c", wrapped_command],
                env=config.get("env", {})
            )
```

### Phase 3: Global Integration
Option A - Embedded Service:
```python
# Start stdout-mcp-server as part of gateway startup
async def lifespan(app: FastAPI):
    # Start stdout-mcp-server
    stdout_server = await start_stdout_mcp_server()
    
    # Initialize gateway
    await initialize_gateway()
    
    yield
    
    # Cleanup
    await stdout_server.stop()
```

Option B - External Service:
```yaml
# docker-compose.yml
services:
  gateway:
    build: .
    ports:
      - "8001:8001"
    volumes:
      - /tmp/stdout_pipe:/tmp/stdout_pipe
  
  stdout-server:
    image: stdout-mcp-server
    volumes:
      - /tmp/stdout_pipe:/tmp/stdout_pipe
```

## Benefits

1. **Universal Solution**: Works for ALL stdio servers, not just specific ones
2. **Clean Separation**: Protocol stays on stdout, logs go to pipe
3. **Debugging**: Can query logs via MCP tools
4. **No Wrapping**: Direct stdio connection, just with stderr redirect
5. **Performance**: No filtering overhead, native pipe performance

## Testing Strategy

1. Start stdout-mcp-server
2. Verify pipe exists: `ls -la /tmp/stdout_pipe`
3. Test redirect: `echo "test" > /tmp/stdout_pipe`
4. Connect basic-memory with redirect
5. Verify clean JSON-RPC on stdout
6. Query logs via stdout-mcp-server tools

## Fallback Strategy

If stdout-mcp-server is not available:
```python
def get_stdio_params(config):
    if stdout_mcp_available():
        return redirect_to_pipe(config)
    elif server_has_banner(config['command']):
        return use_nodejs_wrapper(config)
    else:
        return direct_stdio(config)
```

## Known Considerations

1. **Dependency**: Requires stdout-mcp-server running
2. **Pipe Permissions**: Must be writable by all MCP servers
3. **Log Volume**: High-volume servers might flood the pipe
4. **Windows Compatibility**: Named pipes work differently on Windows

## Conclusion

stdout-mcp-server provides a production-ready solution to the stdout pollution problem. It's:
- More elegant than per-server wrapping
- Already battle-tested
- Provides additional debugging capabilities
- Maintains clean separation of concerns

This is the right long-term solution for the Hive MCP Gateway.
