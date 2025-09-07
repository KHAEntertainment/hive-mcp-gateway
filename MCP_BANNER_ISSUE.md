# MCP STDIO Server Banner/Startup Message Handling Issue

## Problem Summary

FastMCP-based MCP servers (like `basic-memory`, `context7`) and other stdio MCP servers emit banner/startup messages before the JSON-RPC protocol begins. These non-JSON messages cause connection failures in our MCP gateway when using the Python MCP SDK's stdio client.

## Current Behavior

1. **Banner Output**: FastMCP servers print elaborate ASCII art banners and startup messages to stderr/stdout before beginning JSON-RPC communication
2. **Connection Process**: 
   - Stdio context enters successfully (`stdio_client.__aenter__()` succeeds)
   - Session initialization times out (`session.initialize()` fails after 30s x 3 retries)
   - Servers never establish successful connection despite being running

## Root Cause Analysis

The Python MCP SDK's `stdio_client` implementation expects clean JSON-RPC messages from the start. When servers output banners or other startup text:

1. The initial handshake may be disrupted
2. The session initialization request may not be properly sent/received
3. The server may be waiting for input while the client is waiting for a response

## Recent Fix Attempts (Partially Successful)

### 1. Fixed Import Error ✅
- **Issue**: Import of non-existent `mcp.shared.json_rpc_message.JSONRPCMessage` was causing ImportError
- **Impact**: Forced fallback to mock tools instead of real MCP connections
- **Solution**: Removed the incorrect import
- **Result**: MCP SDK now properly detected and used

### 2. Environment Variable Suppression ⚠️
- **Attempted**: Set multiple environment variables to suppress banners
  ```python
  FASTMCP_NO_BANNER=1
  FASTMCP_DISABLE_BANNER=1
  FASTMCP_QUIET=1
  NO_COLOR=1
  PYTHONWARNINGS=ignore
  ```
- **Result**: No effect - FastMCP servers still output banners

### 3. Tolerant Message Handler ⚠️
- **Implemented**: Custom message handler to ignore parsing exceptions
  ```python
  async def tolerant_message_handler(message):
      if isinstance(message, Exception):
          logger.info(f"Ignoring banner/parse exception: {message}")
          return
      # Handle normal messages
  ```
- **Result**: Handler not invoked - session initialization fails before message handling begins

### 4. Error Recovery Attempt ❌
- **Attempted**: Catch JSONDecodeError and retry connection
- **Result**: Error doesn't bubble up in expected way

## Code Locations

- **Main connection logic**: `src/hive_mcp_gateway/services/mcp_client_manager.py`
  - `_connect_stdio_server()` method (lines 115-300)
  - Tolerant message handler (lines 206-217)
  - Environment variable setup (lines 160-171)

- **Experimental solutions** (created but not integrated):
  - `src/hive_mcp_gateway/services/banner_tolerant_stdio.py` - Custom stream wrapper
  - `src/hive_mcp_gateway/services/banner_filter_client.py` - Alternative client approach
  - `src/hive_mcp_gateway/services/stdio_wrapper.js` - Node.js wrapper concept

## Test Results

### Working Server
- **exa** (SSE/HTTP type): ✅ Connects successfully

### Failing Servers
- **basic_memory** (stdio, FastMCP): ❌ Session initialization timeout
- **context7** (stdio, npx): ❌ Session initialization timeout  
- **puppeteer** (stdio): ❌ Session initialization timeout

### Manual Test Confirms Server Works
```bash
echo '{"jsonrpc": "2.0", "method": "initialize", "params": {...}, "id": 1}' | uvx basic-memory mcp
# Returns valid JSON-RPC response
```

## Comparison Points for Analysis

### 1. meta-mcp
- How does meta-mcp handle stdio servers with banners?
- Does it use a different connection approach?
- Any pre-processing or stream filtering?

### 2. mcp-proxy (tbxark)
- How does the Go-based proxy handle stdio connections?
- Does it filter or buffer initial output?
- Different timeout strategies?

### 3. MCP SDK Implementations
- TypeScript SDK vs Python SDK differences
- How does Claude Desktop handle these servers?
- Are there known workarounds in other implementations?

## Proposed Solutions

### Option 1: Custom STDIO Client (Recommended)
Create a replacement for `stdio_client` that:
1. Buffers initial output
2. Filters non-JSON lines until first `{` character
3. Only then begins JSON-RPC parsing
4. Maintains compatibility with MCP ClientSession

### Option 2: Pre-warming Strategy
1. Spawn process and wait for banner to complete
2. Send dummy message to trigger JSON-RPC mode
3. Then hand over to standard MCP client

### Option 3: Node.js Bridge
1. Use Node.js wrapper script that filters banners
2. Python communicates with Node wrapper
3. Node wrapper communicates with actual MCP server

### Option 4: Contribute Upstream
1. Submit PR to Python MCP SDK for banner tolerance
2. Add `banner_tolerance` option to stdio_client
3. Wait for upstream acceptance

## Key Questions for Investigation

1. **Protocol Timing**: Is there a specific delay or signal needed between process start and initialization?
2. **Stream Separation**: Are banners on stderr while JSON-RPC is on stdout?
3. **Other Implementations**: How do working implementations (Claude Desktop, mcp-proxy) handle this?
4. **Server-Specific**: Can we detect FastMCP servers and use special handling?

## Success Criteria

- [ ] basic_memory server connects and discovers tools successfully
- [ ] context7 server connects and discovers tools successfully  
- [ ] No timeout errors during session initialization
- [ ] Banner messages logged but don't break connection
- [ ] Solution works for all stdio-based MCP servers

## Reproducible Test Case

```bash
# Start the gateway
uv run hive-mcp-gateway

# Check server status (should show connected=true)
curl http://localhost:8001/api/mcp/servers

# Currently shows:
# basic_memory: connected=false, tools=0
# context7: connected=false, tools=0
```

## References

- Python MCP SDK: https://github.com/anthropics/mcp-python
- FastMCP: https://github.com/[fastmcp-repo]
- Related issue discussion: [Previous conversations about stdio handling]
- mcp-proxy: https://github.com/tbxark/mcp-proxy
- meta-mcp: https://github.com/[meta-mcp-repo]
