# Test cases for domain models
# Tests tool, tag, and MCP-related model definitions

import pytest
from pydantic import ValidationError

from tool_gating_mcp.models.tool import MCPTool, Tool, ToolMatch


def test_tool_model_creation():
    """Test creating a basic Tool model."""
    tool = Tool(
        id="test-tool-1",
        name="Calculator",
        description="Performs basic arithmetic operations",
        tags=["math", "calculation"],
        estimated_tokens=150,
    )
    assert tool.id == "test-tool-1"
    assert tool.name == "Calculator"
    assert tool.description == "Performs basic arithmetic operations"
    assert tool.tags == ["math", "calculation"]
    assert tool.estimated_tokens == 150


def test_tool_model_validation():
    """Test Tool model validation."""
    with pytest.raises(ValidationError):
        Tool(
            id="",  # Empty ID should fail
            name="Test",
            description="Test tool",
            tags=[],
            estimated_tokens=-1,  # Negative tokens should fail
        )


def test_tool_match_model():
    """Test ToolMatch model for discovery results."""
    tool = Tool(
        id="calc-1",
        name="Calculator",
        description="Math operations",
        tags=["math"],
        estimated_tokens=100,
    )

    match = ToolMatch(tool=tool, score=0.85, matched_tags=["math"])

    assert match.tool.id == "calc-1"
    assert match.score == 0.85
    assert match.matched_tags == ["math"]


def test_mcp_tool_format():
    """Test MCPTool model for MCP protocol format."""
    mcp_tool = MCPTool(
        name="calculator",
        description="Perform calculations",
        inputSchema={
            "type": "object",
            "properties": {
                "operation": {"type": "string"},
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["operation", "a", "b"],
        },
    )

    assert mcp_tool.name == "calculator"
    assert mcp_tool.description == "Perform calculations"
    assert mcp_tool.inputSchema["type"] == "object"
    assert "operation" in mcp_tool.inputSchema["properties"]
