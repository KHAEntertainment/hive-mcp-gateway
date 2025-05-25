# Tool Gating MCP

An intelligent tool gating system for Model Context Protocol (MCP) that dynamically limits the number of tools exposed to LLMs. This system reduces token usage and improves response quality through semantic search and context-aware tool selection.

## 🚀 Features

- **Semantic Tool Discovery**: Uses sentence transformers to find relevant tools based on natural language queries
- **Token Budget Management**: Enforces token limits to optimize LLM context usage
- **Smart Tool Selection**: Intelligently gates tools based on relevance scores and token budgets
- **Tag-Based Filtering**: Support for hierarchical tool categorization
- **MCP Protocol Compatible**: Outputs tools in MCP format for LLM consumption
- **RESTful API**: Easy integration with existing systems

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
│           ├── proxy.py         # MCP proxy
│           └── repository.py    # Tool storage
├── tests/
│   ├── test_*.py               # Test files
│   └── test_integration.py     # Integration tests
├── demo.py                     # Interactive demo
├── test_server.py              # Manual testing script
└── pyproject.toml              # Project configuration
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