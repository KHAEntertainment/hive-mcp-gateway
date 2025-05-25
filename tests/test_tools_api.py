# Test cases for tool API endpoints
# Tests discovery, provisioning, and execution endpoints

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from tool_gating_mcp.main import app
from tool_gating_mcp.models.tool import Tool, ToolMatch


@pytest.fixture
def client():
    """Create test client for API."""
    return TestClient(app)


@pytest.fixture
def mock_discovery_service():
    """Mock discovery service."""
    with patch("tool_gating_mcp.api.v1.tools.DiscoveryService") as mock:
        service = AsyncMock()
        mock.return_value = service
        yield service


@pytest.fixture
def mock_gating_service():
    """Mock gating service."""
    with patch("tool_gating_mcp.api.v1.tools.GatingService") as mock:
        service = AsyncMock()
        mock.return_value = service
        yield service


def test_discover_tools_endpoint(client):
    """Test POST /api/v1/tools/discover endpoint."""
    from tool_gating_mcp.api.v1.tools import get_discovery_service
    
    # Mock discovery service
    mock_discovery_service = AsyncMock()
    mock_tool = Tool(
        id="calc-1",
        name="Calculator",
        description="Math operations",
        tags=["math"],
        estimated_tokens=100,
    )
    mock_discovery_service.search_tools.return_value = [
        ToolMatch(tool=mock_tool, score=0.95, matched_tags=["math"])
    ]
    
    # Override dependency with async function
    async def override_discovery_service():
        return mock_discovery_service
    
    app.dependency_overrides[get_discovery_service] = override_discovery_service

    response = client.post(
        "/api/v1/tools/discover",
        json={"query": "I need a calculator", "tags": ["math"], "limit": 5},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["tools"]) == 1
    assert data["tools"][0]["name"] == "Calculator"
    assert data["tools"][0]["score"] == 0.95
    assert "query_id" in data
    assert "timestamp" in data
    
    # Clean up
    del app.dependency_overrides[get_discovery_service]


def test_discover_tools_validation(client):
    """Test discovery endpoint validation."""
    # Empty query should fail
    response = client.post("/api/v1/tools/discover", json={"query": ""})
    assert response.status_code == 422

    # Invalid limit should fail
    response = client.post("/api/v1/tools/discover", json={"query": "test", "limit": 0})
    assert response.status_code == 422


def test_provision_tools_endpoint(client, mock_gating_service):
    """Test POST /api/v1/tools/provision endpoint."""
    # Mock selected tools
    mock_tools = [
        Tool(
            id="calc-1",
            name="Calculator",
            description="Math operations",
            tags=["math"],
            estimated_tokens=100,
            parameters={"type": "object"},
        )
    ]
    mock_gating_service.select_tools.return_value = mock_tools

    # Mock MCP formatting
    from tool_gating_mcp.models.tool import MCPTool

    mock_mcp_tools = [
        MCPTool(
            name="Calculator",
            description="Math operations",
            inputSchema={"type": "object"},
        )
    ]
    mock_gating_service.format_for_mcp.return_value = mock_mcp_tools

    response = client.post(
        "/api/v1/tools/provision", json={"tool_ids": ["calc-1"], "max_tools": 5}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["tools"]) == 1
    assert data["tools"][0]["name"] == "Calculator"
    assert "metadata" in data
    assert data["metadata"]["gating_applied"] is True


def test_provision_tools_empty_request(client, mock_gating_service):
    """Test provisioning with empty request."""
    mock_gating_service.select_tools.return_value = []
    mock_gating_service.format_for_mcp.return_value = []

    response = client.post("/api/v1/tools/provision", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["tools"] == []


# Note: Tool execution tests removed
# The tool gating system only provides tool definitions
# LLMs should execute tools directly with MCP servers


def test_health_endpoint_still_works(client):
    """Ensure existing health endpoint still works."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
