# Native MCP Usage Guide

## Overview

Tool Gating MCP now includes a built-in MCP server endpoint that exposes all FastAPI endpoints as MCP tools. The server runs at `/mcp` when the FastAPI app is running.

## Two Ways to Use Tool Gating as MCP

### Option 1: HTTP/SSE Mode (Built-in)

When you run the Tool Gating server normally, it automatically exposes an MCP endpoint:

```bash
# Start the server
tool-gating-mcp

# MCP endpoint is now available at:
# http://localhost:8000/mcp
```

This can be used with MCP clients that support HTTP/SSE transport.

### Option 2: stdio Mode for Claude Desktop

Claude Desktop requires stdio transport. You have two options:

#### Using mcp-proxy (Recommended)

1. Install mcp-proxy:
```bash
uv tool install mcp-proxy
```

2. Add to Claude Desktop configuration:

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tool-gating": {
      "command": "mcp-proxy",
      "args": ["http://localhost:8000/mcp"]
    }
  }
}
```

3. Make sure Tool Gating server is running:
```bash
tool-gating-mcp
```

4. Restart Claude Desktop

#### Direct stdio Mode (Alternative)

Add to Claude Desktop configuration:

```json
{
  "mcpServers": {
    "tool-gating": {
      "command": "tool-gating-mcp",
      "args": ["--mcp"],
      "env": {}
    }
  }
}
```

This will start the server and use mcp-proxy internally to bridge to stdio.

## Available MCP Tools

When connected as an MCP server, Tool Gating provides these tools:

### 1. `discover_tools`
Discover relevant tools based on natural language queries.

**Parameters:**
- `query` (string, required): Natural language description of what you need
- `tags` (array, optional): Filter by specific tags
- `limit` (integer, optional): Maximum results to return (default: 10)

**Example:**
```json
{
  "query": "I need to search the web and take screenshots",
  "tags": ["search", "browser"],
  "limit": 5
}
```

### 2. `provision_tools`
Select and provision tools within a token budget.

**Parameters:**
- `tool_ids` (array, required): List of tool IDs to provision
- `context_tokens` (integer, optional): Token budget limit
- `max_tools` (integer, optional): Maximum number of tools

**Example:**
```json
{
  "tool_ids": ["puppeteer_screenshot", "exa_web_search"],
  "context_tokens": 500
}
```

### 3. `register_mcp_server`
Register a new MCP server with the system.

**Parameters:**
- `name` (string, required): Unique server name
- `config` (object, required): Server configuration
  - `command` (string): Command to run the server
  - `args` (array): Command arguments
  - `env` (object): Environment variables
- `description` (string, optional): Server description

**Example:**
```json
{
  "name": "github-tools",
  "config": {
    "command": "mcp-github",
    "args": ["--token", "ghp_xxx"],
    "env": {}
  },
  "description": "GitHub API integration"
}
```

### 4. `list_mcp_servers`
List all registered MCP servers.

**Parameters:** None

### 5. `register_tool`
Register an individual tool.

**Parameters:**
- `id` (string, required): Unique tool ID
- `name` (string, required): Tool name
- `description` (string, required): Tool description
- `parameters` (object, required): Tool parameter schema
- `tags` (array, optional): Tool tags
- `server` (string, optional): Source server name

## Usage Workflow

### Step 1: Start with Tool Gating
When Claude Desktop starts, it automatically connects to Tool Gating MCP.

### Step 2: Discover What You Need
Use `discover_tools` to find relevant tools:
```
"I need to analyze code and create documentation"
```

### Step 3: Provision Optimal Tools
Use `provision_tools` to load only what you need:
```
Provision the top 3 tools within 500 tokens
```

### Step 4: Register Additional Servers
As needed, register new MCP servers:
```
Register the "code-analysis" MCP server
```

## Benefits of Native MCP Integration

1. **Direct Protocol Access**: No HTTP overhead, direct MCP communication
2. **Automatic Tool Discovery**: Claude sees Tool Gating tools immediately
3. **Seamless Integration**: Works like any other MCP server
4. **Meta-Tool Management**: Use MCP tools to manage other MCP tools

## Advanced Configuration

### Custom Token Limits

Set default token budgets via environment:

```json
{
  "mcpServers": {
    "tool-gating": {
      "command": "tool-gating-mcp",
      "args": ["--mcp"],
      "env": {
        "DEFAULT_TOKEN_BUDGET": "1000",
        "MAX_TOOLS": "5"
      }
    }
  }
}
```

### Development Mode

For testing with HTTP transport:

```bash
# Run as HTTP MCP server
tool-gating-mcp --mcp --http

# Access at http://localhost:8000/mcp
```

## Troubleshooting

### Tools Not Appearing
1. Check Claude Desktop logs
2. Verify installation: `which tool-gating-mcp`
3. Test standalone: `tool-gating-mcp --mcp --test`

### Connection Issues
1. Ensure no other process is using the stdio transport
2. Check file permissions on the executable
3. Verify Python environment is activated

## Integration with Other MCP Servers

Tool Gating MCP is designed to work alongside other MCP servers:

1. **Initial Setup**: Only Tool Gating is loaded
2. **On Demand**: Use Tool Gating to discover and load other servers
3. **Optimal Context**: Only relevant tools are active at any time

This creates a dynamic, efficient tool ecosystem that adapts to your current task!