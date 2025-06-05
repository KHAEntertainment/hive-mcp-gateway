"""Tests for Proxy API endpoints"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tool_gating_mcp.api.proxy import router, get_proxy_service
from tool_gating_mcp.services.proxy_service import ProxyService


@pytest.fixture
def test_app():
    """Create test FastAPI app with proxy router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def mock_proxy_service():
    """Create mock proxy service"""
    service = AsyncMock(spec=ProxyService)
    return service


@pytest.fixture
def client(test_app, mock_proxy_service):
    """Create test client with mocked proxy service"""
    # Override the dependency
    def override_get_proxy_service():
        return mock_proxy_service
    
    test_app.dependency_overrides[get_proxy_service] = override_get_proxy_service
    
    with TestClient(test_app) as test_client:
        yield test_client
    
    # Clean up
    test_app.dependency_overrides.clear()


class TestProxyAPI:
    """Test cases for Proxy API endpoints"""

    def test_execute_tool_success(self, client, mock_proxy_service):
        """Test successful tool execution through API"""
        # Setup mock response
        mock_result = {"success": True, "data": "test_result"}
        mock_proxy_service.execute_tool.return_value = mock_result
        
        # Make request
        response = client.post(
            "/api/proxy/execute",
            json={
                "tool_id": "puppeteer_screenshot",
                "arguments": {"name": "test", "selector": "body"}
            }
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json() == {"result": mock_result}
        
        # Verify service was called correctly
        mock_proxy_service.execute_tool.assert_called_once_with(
            "puppeteer_screenshot",
            {"name": "test", "selector": "body"}
        )

    def test_execute_tool_validation_error(self, client):
        """Test API validation for missing required fields"""
        # Missing tool_id
        response = client.post(
            "/api/proxy/execute",
            json={"arguments": {}}
        )
        assert response.status_code == 422
        
        # Missing arguments
        response = client.post(
            "/api/proxy/execute",
            json={"tool_id": "test_tool"}
        )
        assert response.status_code == 422

    def test_execute_tool_not_provisioned(self, client, mock_proxy_service):
        """Test executing non-provisioned tool"""
        # Setup mock to raise ValueError
        mock_proxy_service.execute_tool.side_effect = ValueError("Tool not provisioned")
        
        response = client.post(
            "/api/proxy/execute",
            json={
                "tool_id": "unprovioned_tool",
                "arguments": {}
            }
        )
        
        assert response.status_code == 400
        assert "Tool not provisioned" in response.json()["detail"]

    def test_execute_tool_server_error(self, client, mock_proxy_service):
        """Test handling server errors during execution"""
        # Setup mock to raise generic exception
        mock_proxy_service.execute_tool.side_effect = Exception("Server connection failed")
        
        response = client.post(
            "/api/proxy/execute",
            json={
                "tool_id": "test_tool",
                "arguments": {"param": "value"}
            }
        )
        
        assert response.status_code == 500
        assert "Tool execution failed" in response.json()["detail"]

    def test_execute_tool_empty_arguments(self, client, mock_proxy_service):
        """Test executing tool with empty arguments"""
        mock_result = {"success": True}
        mock_proxy_service.execute_tool.return_value = mock_result
        
        response = client.post(
            "/api/proxy/execute",
            json={
                "tool_id": "simple_tool",
                "arguments": {}
            }
        )
        
        assert response.status_code == 200
        assert response.json() == {"result": mock_result}

    def test_execute_tool_complex_arguments(self, client, mock_proxy_service):
        """Test executing tool with complex nested arguments"""
        complex_args = {
            "config": {
                "timeout": 5000,
                "options": ["headless", "no-sandbox"],
                "viewport": {"width": 1920, "height": 1080}
            },
            "targets": ["https://example.com", "https://test.com"]
        }
        mock_result = {"screenshots": ["img1.png", "img2.png"]}
        mock_proxy_service.execute_tool.return_value = mock_result
        
        response = client.post(
            "/api/proxy/execute",
            json={
                "tool_id": "puppeteer_batch_screenshot",
                "arguments": complex_args
            }
        )
        
        assert response.status_code == 200
        assert response.json() == {"result": mock_result}
        
        # Verify complex arguments were passed correctly
        mock_proxy_service.execute_tool.assert_called_once_with(
            "puppeteer_batch_screenshot",
            complex_args
        )

    def test_get_proxy_service_not_initialized(self, test_app):
        """Test getting proxy service when not initialized"""
        # Create a fresh app without proxy service
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.post(
                "/api/proxy/execute",
                json={
                    "tool_id": "test_tool",
                    "arguments": {}
                }
            )
            
            assert response.status_code == 500
            assert "Proxy service not initialized" in response.json()["detail"]