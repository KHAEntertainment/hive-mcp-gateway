# Tool Gating MCP Usage Guide for AI Assistants

## Overview

The Tool Gating MCP system helps you work efficiently with hundreds of MCP tools by intelligently selecting only the most relevant ones for each task. This prevents context window bloat and improves performance.

## How It Works

Instead of loading all available MCP tools (which could be 100+ tools across multiple servers), the Tool Gating system:
1. **Discovers** relevant tools based on your query
2. **Ranks** them by semantic similarity and tags
3. **Provisions** only the most relevant tools within a token budget

## Key Benefits

- **Context Efficiency**: Use 3-5 relevant tools instead of 100+ 
- **Better Performance**: Reduced token usage = more room for actual work
- **Cross-Server Intelligence**: Seamlessly combines tools from multiple MCP servers
- **Semantic Understanding**: Natural language queries find the right tools

## Usage Pattern

### 1. Discover Tools Based on Task

```python
# Instead of loading all tools, describe what you need
response = discover_tools({
    "query": "I need to search the web and take screenshots of results",
    "tags": ["search", "browser"],  # Optional tag filtering
    "limit": 10
})
```

### 2. Provision Selected Tools

```python
# Get only the tools you need with a token budget
response = provision_tools({
    "tool_ids": [/* selected tool IDs */],
    "context_tokens": 500  # Stay within budget
})
```

## Real-World Examples

### Example 1: Web Research Task
**Without Tool Gating**: Load 100+ tools (Puppeteer, Exa, GitHub, Slack, etc.)
**With Tool Gating**: Load only 3-4 tools (web_search, navigate, screenshot)

### Example 2: Code Analysis Task  
**Without Tool Gating**: Load all filesystem, GitHub, database tools
**With Tool Gating**: Load only relevant code analysis and file reading tools

### Example 3: Documentation Task
**Without Tool Gating**: Load every available tool
**With Tool Gating**: Load only documentation search and file writing tools

## Best Practices for AI Assistants

1. **Be Specific in Queries**: 
   - ❌ "Give me all tools"
   - ✅ "I need tools to analyze Python code and write tests"

2. **Use Tags for Precision**:
   - Common tags: `search`, `browser`, `file`, `code`, `api`, `database`
   - Combine with queries for better results

3. **Respect Token Budgets**:
   - Small tasks: 200-300 tokens
   - Medium tasks: 500-700 tokens  
   - Complex tasks: 1000+ tokens

4. **Iterate When Needed**:
   - Start with core tools
   - Discover additional tools as the task evolves

## API Endpoints

### Tool Discovery
```
POST /api/v1/tools/discover
{
    "query": "natural language description of what you need",
    "tags": ["optional", "filtering", "tags"],
    "limit": 10
}
```

### Tool Provisioning
```
POST /api/v1/tools/provision
{
    "tool_ids": ["tool1", "tool2", "tool3"],
    "context_tokens": 500
}
```

### MCP Server Management
```
GET /api/v1/mcp/servers          # List all servers
POST /api/v1/mcp/servers/register # Register new server
```

## Semantic Search Tips

The system uses advanced semantic search to understand intent:

- **"work with GitHub"** → finds GitHub API tools
- **"automate browser"** → finds Puppeteer tools  
- **"search and analyze"** → finds search + analysis tools
- **"read and modify files"** → finds filesystem tools

## Token Optimization

The system automatically:
- Estimates token usage for each tool
- Prioritizes high-value tools within budget
- Excludes redundant or low-relevance tools
- Maintains diversity across different servers

## Integration with Claude

When using this system:
1. You don't need to manually manage which MCP servers to connect to
2. The system handles tool discovery across all registered servers
3. You get exactly the tools you need for the current task
4. Your context window stays clean and focused

This allows you to work with virtually unlimited MCP tools while maintaining peak efficiency!