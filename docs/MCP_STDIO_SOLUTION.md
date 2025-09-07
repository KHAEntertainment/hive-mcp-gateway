# MCP STDIO Solution Strategy

## Problem Summary

STDIO MCP servers are fundamentally challenging because:

1. **Banner Pollution**: Many servers print banners/logs to stdout, corrupting JSON-RPC
2. **No SDK Support**: Python MCP SDK doesn't provide stdout filtering
3. **Multiple Output Sources**: Banners come from both the server process AND our own imports
4. **Transport Inconsistency**: Different servers behave differently (stdio vs SSE vs HTTP)

## Solutions Explored

### 1. ❌ External Proxy (TBXark/mcp-proxy)
- **Issue**: Returns 404 on SSE endpoints despite connecting to servers
- **Root Cause**: Unclear - possibly incomplete implementation or misconfiguration
- **Status**: Not viable without deeper investigation

### 2. ❌ Python Stream Filtering  
- **Issue**: MCP SDK expects specific stream interfaces we can't easily wrap
- **Root Cause**: SDK tightly coupled to its transport implementations
- **Status**: Too complex, requires SDK modifications

### 3. ✅ Node.js Wrapper with mcps-logger
- **Approach**: Wrap stdio servers in Node.js script that filters output
- **Benefits**: Works at process level, uses proven mcps-logger approach
- **Status**: Partially working but needs refinement

### 4. ✅ Meta-MCP Approach (TypeScript SDK)
- **Approach**: Use stderr="ignore" parameter consistently
- **Benefits**: Simple, proven in production
- **Limitation**: Only works if servers don't print to stdout

## Recommended Solution: Hybrid Approach

### Phase 1: Immediate Fix (Quick Win)
Use the Node.js wrapper for problematic STDIO servers:

```python
# For servers with banner issues
if server_has_banner_issue(name):
    use_nodejs_wrapper(config)
else:
    use_direct_stdio(config)
```

### Phase 2: Server-Specific Adapters
Create specific adapters for known problematic servers:

```python
ADAPTER_MAP = {
    "basic-memory": FastMCPAdapter,  # Handles FastMCP banners
    "context7": DirectAdapter,        # Works fine as-is
    "puppeteer": DirectAdapter,       # Works fine as-is
}
```

### Phase 3: Long-term Solution
Build our own MCP proxy in Python that:
1. Spawns stdio servers as subprocesses
2. Filters stdout at byte level before JSON parsing
3. Exposes clean HTTP/SSE endpoints
4. Handles all transport types uniformly

## Implementation Priority

1. **NOW**: Get ANY server working reliably
   - Use Node.js wrapper for basic-memory
   - Use direct stdio for servers without banners
   - HTTP/SSE servers work as-is

2. **NEXT**: Polish the solution
   - Detect which servers need wrapping
   - Optimize wrapper performance
   - Add proper error handling

3. **FUTURE**: Build proper proxy
   - Python-based MCP proxy
   - Handles all edge cases
   - Production-ready

## Code Example: Working Solution

```python
from hive_mcp_gateway.services.wrapped_mcp_client import WrappedMCPClient

# Servers that need banner filtering
BANNER_SERVERS = ["basic-memory", "other-fastmcp-server"]

async def connect_server(name: str, config: dict):
    client = WrappedMCPClient()
    
    if config["type"] == "stdio" and name in BANNER_SERVERS:
        # Use Node.js wrapper for problematic servers
        return await client.connect_stdio_server(name, config)
    elif config["type"] == "stdio":
        # Direct connection for clean servers
        return await client.connect_direct_stdio(name, config)
    elif config["type"] in ["sse", "http"]:
        # HTTP/SSE servers don't have this problem
        return await client.connect_sse_server(name, config)
```

## Testing Strategy

1. Test each server type individually
2. Verify tool discovery works
3. Verify tool execution works
4. Test with GUI to ensure UI updates properly

## Known Issues

1. **FastMCP Banner**: Printed to stderr, very verbose
2. **Import Side Effects**: Our own Python imports trigger banners
3. **Timeout Issues**: Some servers take >30s to initialize
4. **Node.js Dependency**: Wrapper requires Node.js installed

## Conclusion

The STDIO banner problem is solvable but requires a pragmatic approach:
- Use wrappers for problematic servers
- Direct connection for clean servers  
- HTTP/SSE for new servers when possible

The Node.js wrapper with mcps-logger is the most practical immediate solution while we build a proper Python-based proxy for the long term.
