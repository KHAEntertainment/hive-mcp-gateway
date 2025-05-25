
import pytest

from tool_gating_mcp.models.tool import MCPTool, Tool, ToolMatch


class TestToolModel:
    def test_tool_creation(self):
        tool = Tool(
            id="test-tool",
            name="Test Tool",
            description="A test tool for testing",
            tags=["test", "demo"],
            parameters={"type": "object", "properties": {"input": {"type": "string"}}},
            estimated_tokens=50,
        )

        assert tool.id == "test-tool"
        assert tool.name == "Test Tool"
        assert tool.description == "A test tool for testing"
        assert tool.tags == ["test", "demo"]
        assert tool.estimated_tokens == 50
        assert tool.parameters == {
            "type": "object",
            "properties": {"input": {"type": "string"}},
        }

    def test_tool_defaults(self):
        tool = Tool(
            id="minimal-tool",
            name="Minimal Tool",
            description="A minimal tool",
            estimated_tokens=100,
        )

        assert tool.tags == []
        assert tool.parameters is None
        assert tool.estimated_tokens == 100

    def test_tool_validation(self):
        # Test empty ID validation
        with pytest.raises(ValueError):
            Tool(id="", name="Invalid", description="Invalid tool", estimated_tokens=50)

        # Test negative token count
        with pytest.raises(ValueError):
            Tool(id="test", name="Test", description="Test", estimated_tokens=-1)


class TestToolMatch:
    def test_tool_match_creation(self):
        tool = Tool(
            id="search-tool",
            name="Search Tool",
            description="Search functionality",
            tags=["search", "query"],
            estimated_tokens=75,
        )

        match = ToolMatch(tool=tool, score=0.85, matched_tags=["search"])

        assert match.tool == tool
        assert match.score == 0.85
        assert match.matched_tags == ["search"]

    def test_tool_match_score_validation(self):
        tool = Tool(
            id="test-tool", name="Test Tool", description="Test", estimated_tokens=50
        )

        # Test valid scores
        match = ToolMatch(tool=tool, score=0.0)
        assert match.score == 0.0

        match = ToolMatch(tool=tool, score=1.0)
        assert match.score == 1.0

        # Test invalid scores
        with pytest.raises(ValueError):
            ToolMatch(tool=tool, score=-0.1)

        with pytest.raises(ValueError):
            ToolMatch(tool=tool, score=1.1)


class TestMCPTool:
    def test_mcp_tool_creation(self):
        mcp_tool = MCPTool(
            name="mcp-test-tool",
            description="MCP formatted tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        )

        assert mcp_tool.name == "mcp-test-tool"
        assert mcp_tool.description == "MCP formatted tool"
        assert mcp_tool.inputSchema["type"] == "object"
        assert mcp_tool.inputSchema["properties"]["query"]["type"] == "string"

    def test_mcp_tool_to_dict(self):
        mcp_tool = MCPTool(
            name="export-tool",
            description="Tool for export",
            inputSchema={"type": "object"},
        )

        tool_dict = mcp_tool.model_dump()

        assert tool_dict["name"] == "export-tool"
        assert tool_dict["description"] == "Tool for export"
        assert tool_dict["inputSchema"] == {"type": "object"}

    def test_mcp_tool_complex_schema(self):
        complex_schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "filters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                },
            },
            "required": ["query"],
        }

        mcp_tool = MCPTool(
            name="complex-tool",
            description="Tool with complex schema",
            inputSchema=complex_schema,
        )

        assert mcp_tool.inputSchema == complex_schema
        assert (
            mcp_tool.inputSchema["properties"]["filters"]["properties"]["limit"][
                "maximum"
            ]
            == 100
        )
