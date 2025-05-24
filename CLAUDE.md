# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Tool Gating MCP is a FastAPI-based web service in early development (v0.1.0) that will implement tool gating functionality for MCP (Model Context Protocol or similar). Currently provides a minimal API skeleton with health check and welcome endpoints.

## Development Commands

```bash
# Environment setup
uv venv
source .venv/bin/activate
uv sync
uv pip install -e .

# Run the application
tool-gating-mcp  # Runs on http://localhost:8000

# Run tests
pytest  # All tests
pytest tests/test_main.py::test_health_endpoint  # Single test

# Code quality
black .         # Format code
ruff check .    # Lint
mypy .          # Type check
```

## Architecture

The project follows a clean FastAPI structure:

- **`src/tool_gating_mcp/main.py`**: FastAPI application and route definitions
- **`src/tool_gating_mcp/__init__.py`**: CLI entry point using uvicorn
- **`tests/test_main.py`**: Comprehensive endpoint tests using TestClient

Key patterns:
- Async/await for all endpoints
- Pydantic models for response validation (e.g., HealthResponse)
- Type hints throughout codebase
- Strict mypy configuration enforced

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing Approach

Tests use FastAPI's TestClient for synchronous testing of async endpoints. All new endpoints should have corresponding tests that verify both response content and schema validation.