# Tool Gating MCP

An intelligent tool gating system for Model Context Protocol (MCP) that dynamically limits which tools from multiple MCP servers are exposed to LLMs. This system solves the context bloat problem by selectively provisioning only the most relevant tools instead of overwhelming LLMs with all available tools from all connected servers.

## 🎯 The Problem

When integrating multiple MCP servers, each exposing numerous tools:
- **Exa server**: 7 search tools (web, research papers, Twitter, companies, etc.)
- **Desktop Commander**: 18+ automation tools
- **Context7**: Multiple documentation tools
- **Basic Memory**: Storage and retrieval tools

Without gating, an LLM would receive **all 40+ tools** in its context, leading to:
- 🚨 **Context bloat**: Reduced quality as LLMs struggle with too many options
- 💸 **Increased costs**: More tokens consumed per request
- 🐌 **Slower responses**: Processing overhead from irrelevant tools
- 🎯 **Poor tool selection**: LLMs may choose suboptimal tools

## 💡 The Solution

Tool Gating MCP acts as an intelligent middleware that:
1. **Discovers** all available tools from connected MCP servers
2. **Understands** what the LLM needs through semantic search
3. **Selects** only the most relevant tools within token budgets
4. **Provisions** a focused subset (e.g., 1 Exa search + 1 file editor)

**Example**: Instead of 40+ tools consuming 8,000 tokens, provision just 2-3 relevant tools using only 500 tokens.

## 🚀 Features

- **Cross-Server Tool Discovery**: Aggregates tools from multiple MCP servers into a unified registry
- **Semantic Search**: Uses sentence transformers to understand tool purpose and match queries
- **Selective Provisioning**: Returns only relevant tools from specific servers (e.g., 1 from Exa, 1 from Desktop Commander)
- **Token Budget Enforcement**: Ensures selected tools fit within LLM context limits
- **Smart Scoring**: Combines semantic similarity with tag matching for accurate tool selection
- **MCP Protocol Compatible**: Outputs tools in standard MCP format for direct LLM consumption
- **RESTful API**: Easy integration with any LLM orchestration system

## 📋 Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

## 🔧 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tool-gating-mcp.git
cd tool-gating-mcp
```

2. Create and activate virtual environment:
```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
# .venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
uv sync
```

4. Install package in development mode:
```bash
uv pip install -e .
```

## 🏃 Running the Server

```bash
# Start the server
tool-gating-mcp

# Or with uvicorn for development
uvicorn tool_gating_mcp.main:app --reload
```

The server will run on `http://localhost:8000`

API documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🔍 API Endpoints

### Tool Discovery
```bash
POST /api/v1/tools/discover
```
Discover relevant tools based on semantic search.

**Request:**
```json
{
  "query": "I need to perform calculations",
  "tags": ["math", "calculation"],
  "limit": 5
}
```

**Response:**
```json
{
  "tools": [
    {
      "tool_id": "calculator",
      "name": "Calculator",
      "description": "Perform mathematical calculations",
      "score": 0.95,
      "matched_tags": ["math", "calculation"],
      "estimated_tokens": 50
    }
  ],
  "query_id": "uuid",
  "timestamp": "2024-01-01T00:00:00"
}
```

### Tool Provisioning
```bash
POST /api/v1/tools/provision
```
Select and format tools for LLM consumption with token budget enforcement.

**Request:**
```json
{
  "tool_ids": ["calculator", "web-search"],
  "max_tools": 3
}
```

**Response:**
```json
{
  "tools": [
    {
      "name": "Calculator",
      "description": "Perform mathematical calculations",
      "parameters": { "type": "object", "properties": {...} },
      "token_count": 50
    }
  ],
  "metadata": {
    "total_tokens": 150,
    "gating_applied": true
  }
}
```


## 🔄 Typical Workflow

1. **MCP Servers Running**: Multiple MCP servers expose their tools
   ```
   exa-server → 7 search tools
   desktop-commander → 18 automation tools
   context7 → 5 documentation tools
   ```

2. **Tool Registration**: Tool Gating MCP discovers and indexes all tools
   ```python
   # System discovers 30+ total tools across servers
   ```

3. **LLM Query**: "I need to search for research papers and save results to a file"

4. **Semantic Discovery**: System finds relevant tools
   ```json
   {
     "exa_research_paper_search": 0.92,  // High relevance
     "desktop_file_write": 0.88,          // High relevance
     "exa_web_search": 0.65,              // Medium relevance
     "desktop_screenshot": 0.12,          // Low relevance
     ...
   }
   ```

5. **Selective Provisioning**: Only top tools within budget
   ```json
   {
     "tools": [
       {"name": "research_paper_search", "server": "exa", "tokens": 250},
       {"name": "file_write", "server": "desktop-commander", "tokens": 150}
     ],
     "total_tokens": 400  // Well within budget!
   }
   ```

## 🎯 Usage Examples

### Running the Demo

```bash
# Make sure the server is running first
tool-gating-mcp

# In another terminal, run the interactive demo
python demo.py
```

### Manual Testing

```bash
# Test the server endpoints
python test_server.py
```

### Example: Finding Math Tools

```python
import httpx
import asyncio

async def find_math_tools():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/tools/discover",
            json={
                "query": "I need to solve equations",
                "tags": ["math"],
                "limit": 3
            }
        )
        tools = response.json()["tools"]
        print(f"Found {len(tools)} relevant tools")
        for tool in tools:
            print(f"- {tool['name']}: {tool['score']:.3f}")

asyncio.run(find_math_tools())
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tool_gating_mcp

# Run specific test files
pytest tests/test_discovery_service.py -v

# Run integration tests
pytest tests/test_integration.py -v
```

## 📊 How It Works

1. **Tool Registration**: Tools are registered with metadata, tags, and token estimates
2. **Semantic Search**: User queries are embedded using sentence transformers
3. **Relevance Scoring**: Tools are scored based on:
   - Cosine similarity between query and tool embeddings
   - Tag matches (adds 0.2 boost per matching tag)
4. **Token Gating**: Tools are selected to fit within token budget constraints
5. **MCP Formatting**: Selected tools are formatted according to MCP protocol

## 🔧 Configuration

The system uses sensible defaults but can be configured:

- **Max Tokens**: Default 2000 tokens per request
- **Max Tools**: Default 10 tools per request
- **Embedding Model**: `all-MiniLM-L6-v2` (384-dimensional embeddings)

## 📖 Documentation

- [Tool Discovery System](docs/DISCOVERY.md) - How semantic search and tags work together
- [Adding New MCP Servers](docs/ADDING_SERVERS.md) - Step-by-step guide to integrate new servers
- [AI Integration Guide](docs/AI_INTEGRATION.md) - How AI assistants can automatically add MCP servers
- [Architecture Overview](ARCHITECTURE.md) - System design and component interactions

## 📁 Project Structure

```
tool-gating-mcp/
├── src/
│   └── tool_gating_mcp/
│       ├── __init__.py
│       ├── main.py              # FastAPI application
│       ├── api/
│       │   ├── models.py        # Pydantic models
│       │   └── v1/
│       │       └── tools.py     # API endpoints
│       ├── models/
│       │   └── tool.py          # Domain models
│       └── services/
│           ├── discovery.py     # Semantic search
│           ├── gating.py        # Tool selection logic
│           └── repository.py    # Tool storage
├── tests/
│   ├── test_*.py               # Test files
│   └── test_integration.py     # Integration tests
├── demo.py                     # Interactive demo
├── test_server.py              # Manual testing script
└── pyproject.toml              # Project configuration
```

## 🔌 Integration with MCP Servers

### Registering Tools from MCP Servers

```python
# 1. Clear existing demo tools
DELETE /api/v1/tools/clear

# 2. Register tools from your MCP servers
POST /api/v1/tools/register
{
  "id": "exa_research_paper_search",
  "name": "research_paper_search",
  "description": "Search across 100M+ research papers with full text access",
  "tags": ["search", "research", "academic"],
  "estimated_tokens": 250,
  "server": "exa",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {"type": "string"},
      "numResults": {"type": "number", "default": 5}
    },
    "required": ["query"]
  }
}
```

### Using with LLM Orchestration

1. **LLM receives user query**: "Find recent papers on quantum computing"
2. **Orchestrator queries tool gating**: 
   ```
   POST /api/v1/tools/discover
   {"query": "find research papers", "limit": 3}
   ```
3. **System returns relevant tools**: Only research tools, not file editors
4. **Orchestrator provisions tools**:
   ```
   POST /api/v1/tools/provision
   {"tool_ids": ["exa_research_paper_search"], "max_tokens": 500}
   ```
5. **LLM executes directly with MCP server**: Using the provisioned tool definition

### AI-Assisted Server Registration

AI assistants can automatically add new MCP servers:

```python
# User: "Add this Slack MCP server to tool gating"
# AI: Connects to server, discovers tools, and registers everything

POST /api/v1/mcp/ai/register-server
{
  "server_name": "slack",
  "config": {
    "command": "npx",
    "args": ["@slack/mcp-server"],
    "env": {"SLACK_TOKEN": "xoxb-..."}
  },
  "tools": [
    // AI provides all discovered tools with metadata
  ]
}

# Result: Slack server + all tools registered and ready for use
```

## 🧑‍💻 Development

### Code Quality

```bash
# Format code
black .

# Run linter
ruff check . --fix

# Type checking
mypy .

# Run all checks
black . && ruff check . --fix && mypy . && pytest
```

### Adding New Tools

Tools can be added to the repository in `services/repository.py`:

```python
Tool(
    id="my-tool",
    name="My Tool",
    description="Description for semantic search",
    tags=["category", "function"],
    estimated_tokens=100,
    parameters={
        "type": "object",
        "properties": {...},
        "required": [...]
    }
)
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes and add tests
4. Run quality checks (`black`, `ruff`, `mypy`, `pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Semantic search powered by [Sentence Transformers](https://www.sbert.net/)
- MCP protocol integration via [fastapi-mcp](https://github.com/tadata-org/fastapi_mcp)
- Demo UI using [Rich](https://github.com/Textualize/rich)