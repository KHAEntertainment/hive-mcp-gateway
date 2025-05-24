# Test cases for API request/response models
# Tests Pydantic models used in API endpoints

from datetime import datetime

import pytest
from pydantic import ValidationError

from tool_gating_mcp.api.models import (
    MCPToolDefinition,
    ToolDiscoveryRequest,
    ToolDiscoveryResponse,
    ToolProvisionRequest,
    ToolProvisionResponse,
)


def test_tool_discovery_request():
    """Test ToolDiscoveryRequest model."""
    request = ToolDiscoveryRequest(
        query="I need a calculator tool",
        context="User is working on math problems",
        tags=["math", "calculation"],
        limit=5,
    )
    assert request.query == "I need a calculator tool"
    assert request.context == "User is working on math problems"
    assert request.tags == ["math", "calculation"]
    assert request.limit == 5


def test_tool_discovery_request_defaults():
    """Test ToolDiscoveryRequest with defaults."""
    request = ToolDiscoveryRequest(query="Find tools")
    assert request.query == "Find tools"
    assert request.context is None
    assert request.tags is None
    assert request.limit == 10  # Default


def test_tool_discovery_request_validation():
    """Test ToolDiscoveryRequest validation."""
    # Empty query should fail
    with pytest.raises(ValidationError):
        ToolDiscoveryRequest(query="")

    # Invalid limit should fail
    with pytest.raises(ValidationError):
        ToolDiscoveryRequest(query="test", limit=0)

    with pytest.raises(ValidationError):
        ToolDiscoveryRequest(query="test", limit=51)


def test_tool_discovery_response():
    """Test ToolDiscoveryResponse model."""
    response = ToolDiscoveryResponse(
        tools=[
            {
                "tool_id": "calc-1",
                "name": "Calculator",
                "description": "Basic math operations",
                "score": 0.95,
                "matched_tags": ["math"],
                "estimated_tokens": 150,
            }
        ],
        query_id="query-123",
        timestamp=datetime.now(),
    )
    assert len(response.tools) == 1
    assert response.tools[0].tool_id == "calc-1"
    assert response.tools[0].score == 0.95
    assert response.query_id == "query-123"


def test_tool_provision_request():
    """Test ToolProvisionRequest model."""
    request = ToolProvisionRequest(
        tool_ids=["calc-1", "weather-1"], max_tools=5, context_tokens=1000
    )
    assert request.tool_ids == ["calc-1", "weather-1"]
    assert request.max_tools == 5
    assert request.context_tokens == 1000


def test_tool_provision_request_optional():
    """Test ToolProvisionRequest with all optional fields."""
    request = ToolProvisionRequest()
    assert request.tool_ids is None
    assert request.max_tools is None
    assert request.context_tokens is None


def test_mcp_tool_definition():
    """Test MCPToolDefinition model."""
    tool_def = MCPToolDefinition(
        name="calculator",
        description="Perform calculations",
        parameters={
            "type": "object",
            "properties": {
                "operation": {"type": "string"},
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
        },
        token_count=150,
    )
    assert tool_def.name == "calculator"
    assert tool_def.description == "Perform calculations"
    assert tool_def.parameters["type"] == "object"
    assert tool_def.token_count == 150


def test_tool_provision_response():
    """Test ToolProvisionResponse model."""
    response = ToolProvisionResponse(
        tools=[
            MCPToolDefinition(
                name="calc",
                description="Calculator",
                parameters={"type": "object"},
                token_count=100,
            )
        ],
        metadata={"total_tokens": 100, "gating_applied": True},
    )
    assert len(response.tools) == 1
    assert response.metadata["total_tokens"] == 100
    assert response.metadata["gating_applied"] is True
