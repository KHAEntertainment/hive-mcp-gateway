# Native MCP Usage Guide

## Overview

Hive MCP Gateway is now a native MCP server that exposes all its API endpoints as MCP tools. When you run the server, it automatically provides an MCP endpoint at `/mcp` that works with any MCP-compatible client, including Claude Desktop, Claude Code, Gemini CLI, Kiro, and other agentic coding systems.

## Universal MCP Client Support

Hive MCP Gateway works with **any MCP-compatible client**, including but not limited to:
- Claude Desktop
- Claude Code
- Gemini CLI
- Kiro
- Other agentic coding systems

### Special Benefits for Claude Code

Claude Code in particular suffers from major context window bloat as you add numerous MCPs to its configuration. With Hive MCP Gateway, you can:

1. **Reduce Context Bloat**: Instead of loading 50+ tools that consume thousands of tokens, load only the 3-5 tools you actually need
2. **Improve Performance**: Faster startup times and more responsive interactions
3. **Better Resource Management**: Less memory usage and reduced computational overhead
4. **Dynamic Tool Loading**: Load different tools for different coding tasks without reconfiguring your client

## Two Ways to Use Hive MCP Gateway as MCP

### Option 1: HTTP/SSE Mode (Built-in)

When you run the Hive MCP Gateway server normally, it automatically exposes an MCP endpoint:

```bash
# Start the server
hive-mcp-gateway

# MCP endpoint is now available at:
# http://localhost:8001/mcp
```

This can be used with MCP clients that support HTTP/SSE transport.

### Option 2: stdio Mode for Any MCP Client

Many MCP clients, including Claude Desktop and Claude Code, require stdio transport. You have two options:

#### Using mcp-proxy (Recommended)

1. Install mcp-proxy:
```bash
uv tool install mcp-proxy
```

2. Add to your MCP client configuration:

For Claude Desktop, edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
For other clients, refer to their specific configuration methods:

```json
{
  "mcpServers": {
    "hive-gateway": {
      "command": "/Users/YOUR_USERNAME/.local/bin/mcp-proxy",
      "args": ["http://localhost:8001/mcp"]
    }
  }
}
```

3. Make sure Hive MCP Gateway server is running:
```bash
hive-mcp-gateway
```

4. Restart your MCP client

Note: Replace `YOUR_USERNAME` with your actual username. The full path is required because many MCP clients may not have access to your shell's PATH.

## Available MCP Tools

When connected as an MCP server, Hive MCP Gateway provides these tools:

### Core Tools

#### 1. `discover_tools`
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

#### 2. `provision_tools`
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

### MCP Server Management

#### 3. `register_mcp_server`
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

#### 4. `list_mcp_servers`
List all registered MCP servers.

**Parameters:** None

#### 5. `ai_register_mcp_server`
Streamlined endpoint for AI assistants to register an MCP server with all its tools.

**Parameters:**
- `server_name` (string, required): Unique server name
- `config` (object, required): Server configuration
- `tools` (array, required): List of discovered tools

### Tool Management

#### 6. `register_tool`
Register an individual tool.

**Parameters:**
- `id` (string, required): Unique tool ID
- `name` (string, required): Tool name
- `description` (string, required): Tool description
- `parameters` (object, required): Tool parameter schema
- `tags` (array, optional): Tool tags
- `server` (string, optional): Source server name

## Usage Workflow

### Step 1: Start with Hive MCP Gateway
When your MCP client starts, it automatically connects to Hive MCP Gateway.

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
2. **Automatic Tool Discovery**: Your MCP client sees Hive MCP Gateway tools immediately
3. **Seamless Integration**: Works like any other MCP server
4. **Meta-Tool Management**: Use MCP tools to manage other MCP tools

## Advanced Configuration

### Testing the Integration

1. **Verify server is running**:
   ```bash
   curl http://localhost:8001/health
   ```

2. **Check MCP endpoint**:
   ```bash
   curl -H "Accept: text/event-stream" http://localhost:8001/mcp
   ```

3. **Test with the provided script**:
   ```bash
   python scripts/test_mcp_tools.py
   ```

## Troubleshooting

### Tools Not Appearing in Your MCP Client

1. **Check mcp-proxy path**: Many MCP clients need the full path to mcp-proxy
   ```bash
   which mcp-proxy
   # Should show: /Users/YOUR_USERNAME/.local/bin/mcp-proxy
   ```

2. **Verify server is running**:
   ```bash
   curl http://localhost:8001/health
   ```

3. **Check your MCP client logs**:
   - Refer to your client's documentation for accessing logs
   - Look for MCP connection errors

### Common Issues

1. **"spawn mcp-proxy ENOENT" error**: 
   - Solution: Use full path to mcp-proxy in config
   
2. **"Address already in use" error**:
   - Solution: Kill existing process: `pkill -f hive-mcp-gateway`
   
3. **Tools have verbose names**:
   - This has been fixed! Tools now have clean names like `discover_tools`

## Integration with Other MCP Servers

Hive MCP Gateway is designed to work alongside other MCP servers:

1. **Initial Setup**: Only Hive MCP Gateway is loaded in your MCP client
2. **Dynamic Discovery**: Use Hive MCP Gateway to find relevant tools across all registered servers
3. **Selective Loading**: Provision only the tools you need for the current task
4. **Context Optimization**: Stay within token budgets while maximizing capability

### Example Workflow

1. User: "I need to search for research papers and save them"
2. Use `discover_tools` → Finds: `exa_research_paper_search`, `file_write`
3. Use `provision_tools` → Loads only these 2 tools (400 tokens vs 8000 for all)
4. Execute tasks with optimal context

This creates a dynamic, efficient tool ecosystem that adapts to your current task across any MCP-compatible client!