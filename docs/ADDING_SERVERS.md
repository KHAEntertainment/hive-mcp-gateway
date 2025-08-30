# Adding New MCP Servers

This guide explains how to integrate new MCP servers with the Hive MCP Gateway.

## Overview

The Hive MCP Gateway acts as a registry and intelligent filter for tools from multiple MCP servers. Adding a new server involves:
1. Discovering the server's available tools
2. Registering them with appropriate metadata
3. Testing the integration

## Step-by-Step Process

### 1. Understanding Your MCP Server

First, identify what tools your MCP server provides. For example:
- **Slack MCP**: might expose `send_message`, `list_channels`, `search_messages`
- **GitHub MCP**: might expose `create_issue`, `list_repos`, `create_pr`
- **Database MCP**: might expose `query`, `insert`, `update`, `delete`

### 2. Tool Discovery

In a production system, you would connect to the MCP server and call its `tools/list` method. For now, you'll manually register tools.

### 3. Registering Tools via API

Each tool from your MCP server needs to be registered with the following information:

```bash
POST http://localhost:8001/api/tools/register
Content-Type: application/json

{
  "id": "slack_send_message",           # Unique ID: server_name + tool_name
  "name": "send_message",               # Tool name as exposed by MCP server
  "description": "Send a message to a Slack channel or user",
  "tags": ["messaging", "slack", "communication"],  # Relevant categories
  "estimated_tokens": 150,              # Estimate based on parameter complexity
  "server": "slack",                    # Your MCP server name
  "parameters": {                       # Tool's parameter schema
    "type": "object",
    "properties": {
      "channel": {
        "type": "string",
        "description": "Channel ID or user ID"
      },
      "text": {
        "type": "string", 
        "description": "Message text"
      }
    },
    "required": ["channel", "text"]
  }
}
```

### 4. Batch Registration Script

For multiple tools, create a registration script:

```python
import httpx
import asyncio

async def register_slack_tools():
    """Register all Slack MCP tools"""
    
    slack_tools = [
        {
            "id": "slack_send_message",
            "name": "send_message",
            "description": "Send a message to a Slack channel or user",
            "tags": ["messaging", "slack", "communication"],
            "estimated_tokens": 150,
            "server": "slack",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["channel", "text"]
            }
        },
        {
            "id": "slack_list_channels",
            "name": "list_channels",
            "description": "List all Slack channels in the workspace",
            "tags": ["slack", "channels", "list"],
            "estimated_tokens": 100,
            "server": "slack",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 100}
                }
            }
        },
        {
            "id": "slack_search_messages",
            "name": "search_messages",
            "description": "Search for messages in Slack",
            "tags": ["slack", "search", "messages"],
            "estimated_tokens": 200,
            "server": "slack",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "channel": {"type": "string", "optional": True}
                },
                "required": ["query"]
            }
        }
    ]
    
    async with httpx.AsyncClient() as client:
        # Clear existing tools if needed
        await client.delete("http://localhost:8001/api/tools/clear")
        
        # Register each tool
        for tool in slack_tools:
            response = await client.post(
                "http://localhost:8001/api/tools/register",
                json=tool
            )
            print(f"Registered {tool['name']}: {response.status_code}")

asyncio.run(register_slack_tools())
```

### 5. Estimating Token Counts

Token estimation helps the gating system stay within LLM context limits:

```python
def estimate_tokens(tool):
    """Estimate token count for a tool definition"""
    
    # Base tokens for tool structure
    base_tokens = 50
    
    # Description tokens (rough estimate: 1 token per 4 characters)
    description_tokens = len(tool["description"]) // 4
    
    # Parameter tokens (JSON schema complexity)
    param_json = json.dumps(tool.get("parameters", {}))
    param_tokens = len(param_json) // 4
    
    # Add some overhead for formatting
    overhead = 20
    
    return base_tokens + description_tokens + param_tokens + overhead
```

### 6. Choosing Appropriate Tags

Tags help with discovery and filtering. Use consistent categories:

- **By Function**: `search`, `create`, `update`, `delete`, `list`
- **By Domain**: `messaging`, `database`, `file`, `api`, `web`
- **By Server**: `slack`, `github`, `jira`, `notion`
- **By Type**: `async`, `batch`, `real-time`, `cached`

### 7. Testing Your Integration

After registering your tools, test the integration:

```python
# Test 1: Discover your tools
response = await client.post(
    "http://localhost:8001/api/tools/discover",
    json={"query": "send slack message", "limit": 5}
)
# Should find your slack_send_message tool with high score

# Test 2: Cross-server search
response = await client.post(
    "http://localhost:8001/api/tools/discover",
    json={"query": "search messages in slack and save to file", "limit": 5}
)
# Should find both Slack search and file write tools

# Test 3: Tag filtering
response = await client.post(
    "http://localhost:8001/api/tools/discover",
    json={"query": "communication", "tags": ["slack"], "limit": 5}
)
# Should prioritize Slack tools
```

## Production Integration

In production, you would automate tool discovery:

```python
class MCPServerIntegration:
    """Automatic MCP server integration"""
    
    async def discover_and_register(self, mcp_server_url: str, server_name: str):
```