# Tool Gating MCP Architecture

## Overview

The Tool Gating MCP system is designed to intelligently limit the number of tools exposed to LLMs, reducing token usage while maintaining functionality through semantic search and context-aware tool selection.

## Core Responsibilities

### What This System Does ✅

1. **Tool Discovery**: Find relevant tools based on natural language queries
2. **Semantic Search**: Use embeddings to match tools to user intent
3. **Token Budget Enforcement**: Select tools within token constraints
4. **Tool Formatting**: Provide tools in MCP-compatible format

### What This System Does NOT Do ❌

1. **Tool Execution**: LLMs execute tools directly with MCP servers
2. **Result Processing**: No proxy or middleware for tool results
3. **Authentication**: Does not handle MCP server authentication

## Architecture Diagram

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│     LLM     │────▶│ Tool Gating MCP  │────▶│  Tool Defs  │
└─────────────┘     └──────────────────┘     └─────────────┘
      │                                              │
      │                                              │
      └──────────────────────────────────────────────┘
                           │
                           ▼
                   ┌───────────────┐
                   │  MCP Servers  │
                   └───────────────┘
```

## Key Components

### 1. Discovery Service
- **Purpose**: Find relevant tools using semantic search
- **Technology**: Sentence transformers (all-MiniLM-L6-v2)
- **Features**:
  - Cosine similarity scoring
  - Tag-based filtering
  - Context-aware search

### 2. Gating Service
- **Purpose**: Select tools within constraints
- **Features**:
  - Token budget enforcement (default 2000)
  - Tool count limits (default 10)
  - Priority-based selection

### 3. Tool Repository
- **Purpose**: Store and manage tool definitions
- **Implementation**: In-memory (demo) or database
- **Features**:
  - CRUD operations
  - Usage tracking
  - Popular tools ranking

## API Flow

### 1. Discovery Flow
```
POST /api/v1/tools/discover
{
  "query": "I need to calculate things",
  "tags": ["math"],
  "limit": 5
}
↓
Semantic Search → Score Tools → Return Matches
```

### 2. Provisioning Flow
```
POST /api/v1/tools/provision
{
  "tool_ids": ["calc", "converter"],
  "max_tools": 3
}
↓
Apply Gating → Format for MCP → Return Tools
```

## Token Optimization

### Before Tool Gating
- All tools included: ~10,000 tokens
- Limited context for conversation
- Higher costs and slower responses

### After Tool Gating
- Only relevant tools: ~500-2000 tokens
- More context for actual work
- 50-90% token reduction

## Integration Guide

### For LLM Developers

1. **Discover Tools**
   ```python
   # Find tools based on user intent
   tools = await discover_tools(query="user needs...")
   ```

2. **Provision Tools**
   ```python
   # Get MCP-formatted tools
   mcp_tools = await provision_tools(tool_ids=[...])
   ```

3. **Execute Directly**
   ```python
   # LLM executes with MCP server directly
   result = await mcp_server.execute(tool_name, params)
   ```

### For MCP Server Developers

No changes needed! The gating system is transparent to MCP servers.

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