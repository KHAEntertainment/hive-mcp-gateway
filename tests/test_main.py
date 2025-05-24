# Test cases for main application endpoints
# Tests core FastAPI functionality and health checks

from fastapi.testclient import TestClient

from tool_gating_mcp.main import app

client = TestClient(app)


def test_root_endpoint() -> None:
    """Test the root endpoint returns welcome message."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Tool Gating MCP"}


def test_health_endpoint() -> None:
    """Test the health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["message"] == "Service is running"


def test_health_endpoint_schema() -> None:
    """Test the health endpoint response matches expected schema."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "message" in data
    assert isinstance(data["status"], str)
    assert isinstance(data["message"], str)
