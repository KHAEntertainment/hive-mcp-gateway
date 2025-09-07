# Universal HTTP/SSE Wrapper Architecture

## Problem Statement
STDIO MCP servers are fundamentally unreliable because:
- They print banners/logs to stdout, corrupting JSON-RPC
- Process lifecycle management is complex
- Different servers have different startup behaviors
- No standard way to suppress output

## Proposed Solution: Universal HTTP/SSE Wrapper

### Core Concept
Instead of managing STDIO servers directly or relying on external proxies, we create lightweight HTTP/SSE wrappers for each STDIO server. This gives us:

1. **Uniform Interface**: All servers (STDIO, HTTP, SSE) exposed via HTTP endpoints
2. **Process Isolation**: Each wrapper manages its own STDIO subprocess
3. **Banner Filtering**: Wrappers can filter non-JSON content before forwarding
4. **Better Error Handling**: HTTP status codes, proper timeouts, clean restarts

### Architecture

```
┌─────────────────────────────────────────────┐
│           Hive MCP Gateway (8001)          │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │     MCP Client Manager              │   │
│  │                                     │   │
│  │  - Connects to HTTP/SSE endpoints  │   │
│  │  - No direct STDIO handling        │   │
│  └──────────┬──────────────────────────┘   │
│             │                               │
│      HTTP/SSE Connections Only              │
│             │                               │
└─────────────┼───────────────────────────────┘
              │
     ┌────────┴────────┬────────────┬────────────┐
     │                 │            │            │
┌────▼─────┐  ┌────────▼───┐  ┌────▼───┐  ┌────▼────┐
│ Wrapper  │  │  Wrapper   │  │  HTTP  │  │  SSE    │
│  :8010   │  │   :8011    │  │  :8012 │  │  :8013  │
└────┬─────┘  └──────┬─────┘  └────────┘  └─────────┘
     │               │
┌────▼─────┐  ┌──────▼─────┐
│  STDIO   │  │   STDIO    │
│ Server 1 │  │  Server 2  │
└──────────┘  └────────────┘
```

### Implementation Plan

#### Phase 1: Create STDIO Wrapper Service
```python
# stdio_wrapper.py
class StdioWrapper:
    def __init__(self, name: str, command: str, args: list, port: int):
        self.process = None
        self.session = None
        self.app = FastAPI()
        
    async def start_stdio_server(self):
        # Start subprocess with CLEAN environment
        # Capture both stdout and stderr
        # Filter non-JSON content
        
    @app.get("/sse")
    async def sse_endpoint(self):
        # Expose clean SSE stream
        
    @app.post("/rpc")
    async def rpc_endpoint(self, request: dict):
        # Handle JSON-RPC requests
```

#### Phase 2: Wrapper Manager
```python
class WrapperManager:
    def __init__(self):
        self.wrappers = {}
        self.port_pool = range(8010, 8100)
        
    async def spawn_wrapper(self, server_config):
        port = self.allocate_port()
        wrapper = StdioWrapper(
            name=config.name,
            command=config.command,
            args=config.args,
            port=port
        )
        # Start wrapper process
        # Return HTTP endpoint URL
```

#### Phase 3: Update Client Manager
- Remove all direct STDIO handling
- Connect only to HTTP/SSE endpoints
- Wrappers handle all STDIO complexity

### Benefits

1. **Reliability**: No more STDIO corruption issues
2. **Uniformity**: All servers accessed the same way
3. **Flexibility**: Easy to add filtering, logging, retries
4. **Scalability**: Each wrapper is independent
5. **Debugging**: Clean HTTP interface for testing

### Migration Path

1. Keep existing code as fallback
2. Implement wrapper for one server (basic_memory)
3. Test thoroughly
4. Roll out to all STDIO servers
5. Remove direct STDIO code

### Alternative: Fix Current Architecture

If we don't want to rebuild, we could:

1. **Add Stream Filter**: Insert a filter between stdio subprocess and MCP client that strips non-JSON lines
2. **Use Anthropic's MCP proxy**: The Python one we were avoiding might actually handle banners better
3. **Force Banner Suppression**: Find environment variables that work for each server type

## Decision Needed

1. **Full Rebuild** with HTTP/SSE wrappers (recommended)
2. **Patch Current** with stream filtering
3. **Try Different Proxy** (Anthropic's Python one)

The wrapper approach is more work upfront but solves the problem permanently and gives us full control.
