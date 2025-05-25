from datetime import datetime

import pytest
from pydantic import ValidationError

from tool_gating_mcp.api.models import (
    MCPToolDefinition,
    ToolDiscoveryRequest,
    ToolDiscoveryResponse,
    ToolMatchResponse,
    ToolProvisionRequest,
    ToolProvisionResponse,
)


class TestToolDiscoveryModels:
    def test_discovery_request_valid(self):
        request = ToolDiscoveryRequest(
            query="Find me a calculator tool",
            context="User wants to perform mathematical operations",
            tags=["math", "calculation"],
            limit=15,
        )

        assert request.query == "Find me a calculator tool"
        assert request.context == "User wants to perform mathematical operations"
        assert request.tags == ["math", "calculation"]
        assert request.limit == 15

    def test_discovery_request_minimal(self):
        request = ToolDiscoveryRequest(query="search tools")

        assert request.query == "search tools"
        assert request.context is None
        assert request.tags is None
        assert request.limit == 10  # default

    def test_discovery_request_invalid_limit(self):
        with pytest.raises(ValidationError) as exc_info:
            ToolDiscoveryRequest(query="test", limit=0)
        assert "greater than or equal to 1" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            ToolDiscoveryRequest(query="test", limit=51)
        assert "less than or equal to 50" in str(exc_info.value)

    def test_discovery_response(self):
        tools = [
            ToolMatchResponse(
                tool_id="calc-1",
                name="Calculator",
                description="Basic calculator",
                score=0.95,
                matched_tags=["math"],
                estimated_tokens=50,
            )
        ]

        response = ToolDiscoveryResponse(
            tools=tools, query_id="query-123", timestamp=datetime.now()
        )

        assert len(response.tools) == 1
        assert response.tools[0].tool_id == "calc-1"
        assert response.query_id == "query-123"
        assert isinstance(response.timestamp, datetime)


class TestToolProvisionModels:
    def test_provision_request_with_tool_ids(self):
        request = ToolProvisionRequest(
            tool_ids=["tool-1", "tool-2", "tool-3"], max_tools=5
        )

        assert request.tool_ids == ["tool-1", "tool-2", "tool-3"]
        assert request.max_tools == 5
        assert request.context_tokens is None

    def test_provision_request_with_context_tokens(self):
        request = ToolProvisionRequest(context_tokens=2000, max_tools=10)

        assert request.tool_ids is None
        assert request.context_tokens == 2000
        assert request.max_tools == 10

    def test_provision_request_empty(self):
        request = ToolProvisionRequest()

        assert request.tool_ids is None
        assert request.max_tools is None
        assert request.context_tokens is None

    def test_provision_response(self):
        tools = [
            MCPToolDefinition(
                name="Calculator",
                description="Perform calculations",
                parameters={"type": "object", "properties": {}},
                token_count=75,
            )
        ]

        response = ToolProvisionResponse(
            tools=tools,
            metadata={"total_tokens": 75, "gating_applied": True, "tools_filtered": 2},
        )

        assert len(response.tools) == 1
        assert response.tools[0].name == "Calculator"
        assert response.metadata["total_tokens"] == 75
        assert response.metadata["gating_applied"] is True


# Note: Tool execution tests removed
# The tool gating system only provides tool definitions
# LLMs should execute tools directly with MCP servers


class TestSharedModels:
    def test_tool_match_validation(self):
        # Valid score
        match = ToolMatchResponse(
            tool_id="test",
            name="Test Tool",
            description="A test tool",
            score=0.5,
            matched_tags=[],
            estimated_tokens=100,
        )
        assert match.score == 0.5

        # Score at boundaries
        match1 = ToolMatchResponse(
            tool_id="test1",
            name="Test",
            description="Test",
            score=0.0,
            matched_tags=[],
            estimated_tokens=50,
        )
        assert match1.score == 0.0

        match2 = ToolMatchResponse(
            tool_id="test2",
            name="Test",
            description="Test",
            score=1.0,
            matched_tags=[],
            estimated_tokens=50,
        )
        assert match2.score == 1.0

        # Invalid scores
        with pytest.raises(ValidationError):
            ToolMatchResponse(
                tool_id="test",
                name="Test",
                description="Test",
                score=-0.1,
                matched_tags=[],
                estimated_tokens=50,
            )

        with pytest.raises(ValidationError):
            ToolMatchResponse(
                tool_id="test",
                name="Test",
                description="Test",
                score=1.1,
                matched_tags=[],
                estimated_tokens=50,
            )

    def test_mcp_tool_definition(self):
        tool = MCPToolDefinition(
            name="web_search",
            description="Search the web for information",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {
                        "type": "integer",
                        "description": "Number of results",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
            token_count=150,
        )

        assert tool.name == "web_search"
        assert tool.description == "Search the web for information"
        assert tool.parameters["properties"]["query"]["type"] == "string"
        assert tool.parameters["required"] == ["query"]
        assert tool.token_count == 150
