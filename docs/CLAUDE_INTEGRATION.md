# Hive MCP Gateway and Claude Integration

## Overview

Hive MCP Gateway is designed to work with **any MCP-compatible client**, including Claude Desktop, Claude Code, Gemini CLI, Kiro, and other agentic coding systems. While it works exceptionally well with Claude products, it's important to understand that it's a universal solution that can benefit any MCP-compatible client.

Note on transport: Hive MCP Gateway exposes an HTTP MCP endpoint at `/mcp`. If your client supports HTTP MCP, you can connect directly. Use `mcp-proxy` only when your client requires stdio bridging.

## Special Benefits for Claude Code

Claude Code in particular suffers from major context window bloat as you add numerous MCPs to its configuration. With Hive MCP Gateway, you can:

1. **Reduce Context Bloat**: Instead of loading 50+ tools that consume thousands of tokens, load only the 3-5 tools you actually need
2. **Improve Performance**: Faster startup times and more responsive interactions
3. **Better Resource Management**: Less memory usage and reduced computational overhead
4. **Dynamic Tool Loading**: Load different tools for different coding tasks without reconfiguring your client

## Universal MCP Compatibility

Hive MCP Gateway works with **any MCP-compatible client**, not just Claude products. This includes:
- Claude Desktop
- Claude Code
- Gemini CLI
- Kiro
- Other agentic coding systems

### Benefits for All MCP Clients

- **Context Optimization**: Reduces token usage by 50-90% by loading only relevant tools
- **Cross-Server Intelligence**: Seamlessly combines tools from multiple MCP servers
- **Dynamic Discovery**: Find tools using natural language queries
- **Flexible Integration**: Works with stdio, SSE, and HTTP-based MCP servers

## Integration with Claude Products

### For Claude Desktop

1. **Start Hive MCP Gateway**:
   ```bash
   hive-mcp-gateway
   ```

2. **Configure Claude Desktop**:
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

3. **Use Natural Language Discovery**:
   - "I need to search for research papers" → Finds academic search tools
   - "Help me automate browser tasks" → Discovers Puppeteer tools
   - "I want to work with documentation" → Locates Context7 tools

### For Claude Code

Claude Code benefits significantly from Hive MCP Gateway due to its context window limitations:

1. **Reduced Configuration Complexity**: Instead of configuring dozens of individual MCP servers, configure only Hive MCP Gateway
2. **Optimal Context Usage**: Load only the tools needed for each specific coding task
3. **Improved Performance**: Faster startup times and more responsive interactions
4. **Dynamic Tool Loading**: Load different tools for different coding tasks without reconfiguring your client

## Setup Instructions

### Prerequisites

1. Install Hive MCP Gateway:
   ```bash
   pip install hive-mcp-gateway
   ```

2. Install mcp-proxy:
   ```bash
   uv tool install mcp-proxy
   ```

### Configuration

1. **Start Hive MCP Gateway**:
   ```bash
   hive-mcp-gateway
   ```

2. **Configure Your Claude Client**:
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

3. **Restart Your Claude Client**

## Usage Examples

### Example 1: Web Research Task
Instead of loading 100+ tools from various MCP servers, Hive MCP Gateway allows you to:
- Use natural language: "I need to search the web and take screenshots"
- Automatically discover relevant tools
- Load only the necessary tools (3-4 instead of 100+)

### Example 2: Code Analysis Task
For code analysis tasks:
- Use natural language: "I need to analyze Python code and write tests"
- Discover relevant code analysis and testing tools
- Load only the tools needed for this specific task

### Example 3: Documentation Task
For documentation tasks:
- Use natural language: "I want to search documentation and create a summary"
- Discover documentation search and file writing tools
- Load only the necessary tools while maintaining optimal context

## Best Practices

1. **Use Natural Language Queries**: 
   - Be specific about what you need
   - Use descriptive queries like "search academic papers" rather than generic terms

2. **Leverage Dynamic Provisioning**:
   - Load tools as needed rather than all at once
   - Provision different tools for different phases of your work

3. **Take Advantage of Cross-Server Intelligence**:
   - Hive MCP Gateway can find and combine tools from multiple servers
   - This enables more powerful workflows than single-server solutions

## Troubleshooting

### Common Issues

1. **Tools Not Appearing**:
   - Ensure Hive MCP Gateway is running: `curl http://localhost:8001/health`
   - Check that mcp-proxy is installed: `which mcp-proxy`
   - Verify Claude client configuration

2. **Connection Issues**:
   - Check that the correct port is being used (8001 by default)
   - Ensure no firewall is blocking the connection
   - Verify that Hive MCP Gateway is properly started

3. **Performance Issues**:
   - For Claude Code, ensure you're using dynamic tool loading
   - Check that you're not provisioning too many tools at once
   - Monitor token usage to stay within context limits

## Advanced Configuration

### Customizing Token Budgets

You can adjust token budgets for tool provisioning:

```json
{
  "toolGating": {
    "maxTokensPerRequest": 1500,
    "maxToolsPerRequest": 8
  }
}
```

### Adding New MCP Servers

Hive MCP Gateway makes it easy to add new MCP servers:

```bash
# Register a new server via API
curl -X POST http://localhost:8001/api/mcp/servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github-tools",
    "config": {
      "command": "mcp-github",
      "args": ["--token", "ghp_xxx"]
    }
  }'
```

## Conclusion

Hive MCP Gateway provides powerful tool management capabilities for **any MCP-compatible client**, with special benefits for Claude Code due to its context window limitations. By dynamically discovering and provisioning only the tools you need, you can maintain optimal performance while accessing the full power of the MCP ecosystem.
