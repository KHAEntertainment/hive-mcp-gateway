# Hive MCP Gateway Architecture

## Overview

Hive MCP Gateway is an intelligent gateway that manages MCP tools to prevent context bloat. It acts as a single MCP server that any MCP-compatible client connects to, while internally managing connections to multiple backend MCP servers. The system discovers, ranks, and provisions only the most relevant tools for each task.

## Core Responsibilities

### What This System Does ✅

1. **Tool Discovery**: Find relevant tools across multiple MCP servers using semantic search
2. **Intelligent Selection**: Choose optimal tools within token budgets
3. **Proxy Execution**: Route tool calls to appropriate backend MCP servers
4. **Connection Management**: Maintain persistent connections to multiple MCP servers
5. **Native MCP Server**: Expose all functionality as MCP tools for any MCP-compatible client

### What This System Does NOT Do ❌

1. **Direct Tool Implementation**: Delegates actual tool execution to backend servers
2. **Authentication Storage**: Currently supports only no-auth servers (Phase 1)
3. **Result Transformation**: Passes through results unmodified

## Architecture Diagram

```
┌─────────────────┐
│  Any MCP Client │
│ (Claude Desktop,│
│  Claude Code,   │
│   Gemini CLI,   │
│     etc.)       │
└────────┬────────┘
         │ MCP Protocol (SSE/stdio)
         │
┌────────▼────────────────────────┐
│      Hive MCP Gateway           │
├─────────────────────────────────┤
│ • discover_tools                │
│ • provision_tools               │
│ • execute_tool ← Key Addition   │
│ • register_mcp_server           │
└────────┬───────┬────────┬──────┘
         │       │        │ stdio connections
    ┌────▼──┐ ┌──▼──┐ ┌──▼──┐
    │Puppet-│ │Con- │ │ Exa │
    │ eer   │ │text7│ │     │
    └───────┘ └─────┘ └─────┘
    Backend MCP Servers
```

## Key Components

### LLM Integration Status
- Optional integration for external LLM providers (OpenAI, Anthropic, Gemini) exists for future sampling/re-ranking.
- It is currently disabled by default and not used in the tool-gating loop.
- You can re-enable the UI configurator by launching with `HMG_ENABLE_LLM_UI=1`.
- Gating today is algorithmic: semantic discovery + deterministic limits; no LLM is consulted for selection or exposure.

### 1. MCP Client Manager (NEW)
- **Purpose**: Manage connections to backend MCP servers
- **Technology**: MCP Python SDK with stdio transport
- **Features**:
  - Persistent server connections
  - Tool discovery on connect
  - Connection lifecycle management
  - Error recovery

### 2. Proxy Service (NEW)
- **Purpose**: Route tool execution to backend servers
- **Features**:
  - Tool ID parsing (server_toolname format)
  - Provisioning state management
  - Request routing
  - Error propagation

### 3. Discovery Service
- **Purpose**: Find relevant tools using semantic search
- **Technology**: Sentence transformers (all-MiniLM-L6-v2)
- **Features**:
  - Cosine similarity scoring
  - Tag-based filtering
  - Cross-server search

### 4. Gating Service
- **Purpose**: Select tools within constraints
- **Features**:
  - Token budget enforcement (default 2000)
  - Tool count limits (default 10)
  - Priority-based selection
  - Note: No LLM involvement in selection by default

### 5. Tool Repository
- **Purpose**: Store tool definitions from all servers
- **Implementation**: In-memory storage
- **Features**:
  - Unified tool registry
  - Server attribution
  - Usage tracking

## API Flow

### 1. Startup Flow (NEW)
```
Application Start
↓
Connect to Backend MCP Servers (puppeteer, context7, etc.)
↓
Discover All Available Tools
↓
Index in Tool Repository with server attribution
↓
Ready for Client Connections
```

### 2. Discovery Flow
```
MCP Tool: discover_tools
{
  "query": "I need to take screenshots",
  "tags": ["browser"],
  "limit": 5
}
↓
Semantic Search Across All Servers → Score Tools → Return Matches
```

### 3. Provisioning Flow
```
MCP Tool: provision_tools
{
  "tool_ids": ["puppeteer_screenshot", "puppeteer_navigate"],
  "max_tools": 3
}
↓
Apply Gating → Update Provisioned Set → Return Tool Definitions
```

### 4. Execution Flow (NEW)
```
MCP Tool: execute_tool
{
  "tool_id": "puppeteer_screenshot",
  "arguments": {"name": "homepage"}
}
↓
Parse Server Name → Route to Backend → Execute → Return Result
```

## Token Optimization

### Before Hive MCP Gateway
- All tools included: ~10,000 tokens
- Limited context for conversation
- Higher costs and slower responses

### After Hive MCP Gateway
- Only relevant tools: ~500-2000 tokens
- More context for actual work
- 50-90% token reduction

## Integration Guide

### For Any MCP-Compatible Client (Including Claude Code, Claude Desktop, Gemini CLI, etc.)

1. **Configure Hive MCP Gateway Only**
   ```json
   {
     "mcpServers": {
       "hive-gateway": {
         "command": "mcp-proxy",
         "args": ["http://localhost:8001/mcp"]
       }
     }
   }
   ```

2. **Use Natural Language**
   - "I need to search the web" → discovers web search tools
   - "Help me take screenshots" → finds browser automation tools
   - "I want to analyze code" → locates code analysis tools

3. **Execute Through Gateway**
   - All tool execution automatically routes through Hive MCP Gateway
   - No need to know which backend server has which tool

### Special Benefits for Claude Code

Claude Code in particular suffers from major context window bloat as you add numerous MCPs to its configuration. With Hive MCP Gateway, you can:

- **Reduce Context Bloat**: Load only 3-5 tools instead of 50+ tools
- **Maintain Optimal Performance**: Keep more context space for your actual code
- **Dynamic Tool Loading**: Load different tools for different coding tasks
- **Faster Startup**: Connect to one endpoint instead of configuring dozens

### For Developers Adding New MCP Servers

1. **Register Your Server**
   ```python
   POST /api/mcp/servers
   {
     "name": "my-server",
     "config": {
       "command": "my-mcp-server",
       "args": []
     }
   }
   ```

2. **Tools Auto-Discovered**
   - Hive MCP Gateway connects and indexes all tools
   - Tools available immediately for discovery

## Configuration

### Environment Variables
```bash
MAX_TOKENS=2000        # Token budget per request
MAX_TOOLS=10          # Maximum tools per request
EMBEDDING_MODEL=all-MiniLM-L6-v2  # Sentence transformer model
```

### Tool Definition
```python
Tool(
    id="unique-id",
    name="Human Name",
    description="For semantic search",
    tags=["category", "function"],
    estimated_tokens=100,
    parameters={...}  # MCP schema
)
```

## Security Considerations

1. **No Execution**: System never executes tools, only provides definitions
2. **Read-Only**: Cannot modify tool behavior or results
3. **Stateless**: No session data or user information stored
4. **Token Limits**: Prevents token exhaustion attacks

## Performance Characteristics

- **Discovery**: ~50-100ms (with caching)
- **Provisioning**: ~10-20ms
- **Memory**: ~500MB (with embeddings loaded)
- **Scalability**: Horizontal scaling supported

## Future Enhancements

1. **Persistent Storage**: Database for tool definitions
2. **Learning**: Track usage patterns to improve selection
3. **Custom Models**: Support for different embedding models
4. **Caching**: Redis for embedding cache
5. **Analytics**: Tool usage and performance metrics
