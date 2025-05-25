"""Integration tests for the tool gating MCP system."""

import pytest
from fastapi.testclient import TestClient

from tool_gating_mcp.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestIntegration:
    """Integration tests for the complete system."""

    def test_full_workflow(self, client):
        """Test complete workflow: discover -> provision -> execute."""
        # 1. Discover tools for math calculations
        discover_response = client.post(
            "/api/v1/tools/discover",
            json={
                "query": "I need to perform mathematical calculations",
                "tags": ["math"],
                "limit": 5
            }
        )
        assert discover_response.status_code == 200
        discover_data = discover_response.json()
        assert len(discover_data["tools"]) > 0

        # Find calculator tool
        calculator = next(
            (t for t in discover_data["tools"] if "calculator" in t["tool_id"].lower()),
            None
        )
        assert calculator is not None
        assert calculator["score"] > 0.5

        # 2. Provision the discovered tools
        tool_ids = [t["tool_id"] for t in discover_data["tools"][:3]]
        provision_response = client.post(
            "/api/v1/tools/provision",
            json={
                "tool_ids": tool_ids,
                "max_tools": 3
            }
        )
        assert provision_response.status_code == 200
        provision_data = provision_response.json()
        assert len(provision_data["tools"]) <= 3
        assert provision_data["metadata"]["gating_applied"] is True

        # Check calculator is included
        calc_tool = next(
            (t for t in provision_data["tools"] if t["name"] == "Calculator"),
            None
        )
        assert calc_tool is not None
        assert calc_tool["parameters"]["type"] == "object"

        # Note: Tool execution removed - LLMs should execute directly with MCP servers
        # The gating system only provides tool definitions, not execution

    def test_semantic_search_quality(self, client):
        """Test semantic search returns relevant results."""
        test_cases = [
            {
                "query": "search the internet for information",
                "expected_tool": "web-search",
                "tags": ["search", "web"]
            },
            {
                "query": "read data from disk",
                "expected_tool": "file-reader",
                "tags": ["file", "io"]
            },
            {
                "query": "get weather forecast",
                "expected_tool": "weather-api",
                "tags": ["weather", "api"]
            }
        ]

        for test_case in test_cases:
            response = client.post(
                "/api/v1/tools/discover",
                json={
                    "query": test_case["query"],
                    "limit": 5
                }
            )
            assert response.status_code == 200
            data = response.json()

            # Check expected tool is in results
            tool_ids = [t["tool_id"] for t in data["tools"]]
            assert test_case["expected_tool"] in tool_ids

            # Check it's ranked high
            tool = next(
                t for t in data["tools"]
                if t["tool_id"] == test_case["expected_tool"]
            )
            assert tool["score"] > 0.3

    def test_gating_token_budget(self, client):
        """Test that gating respects token budget."""
        # Get all tools
        discover_response = client.post(
            "/api/v1/tools/discover",
            json={
                "query": "all tools",
                "limit": 50
            }
        )
        assert discover_response.status_code == 200
        all_tools = discover_response.json()["tools"]

        # Try to provision all tools
        all_tool_ids = [t["tool_id"] for t in all_tools]
        provision_response = client.post(
            "/api/v1/tools/provision",
            json={
                "tool_ids": all_tool_ids,
                "max_tools": 50,  # High limit
                "context_tokens": 200  # Low token budget to force gating
            }
        )
        assert provision_response.status_code == 200
        data = provision_response.json()

        # Should be limited by token budget
        total_tokens = data["metadata"]["total_tokens"]
        assert total_tokens <= 200
        assert len(data["tools"]) < len(all_tools)  # Some tools excluded

    def test_tag_filtering(self, client):
        """Test tag-based filtering works correctly."""
        response = client.post(
            "/api/v1/tools/discover",
            json={
                "query": "any tool",
                "tags": ["math", "calculation"],
                "limit": 10
            }
        )
        assert response.status_code == 200
        data = response.json()

        # Should return calculator with matching tags
        tools_with_tags = [t for t in data["tools"] if t["matched_tags"]]
        assert len(tools_with_tags) > 0

        # Calculator should have both tags matched
        calculator = next(
            (t for t in tools_with_tags if t["tool_id"] == "calculator"),
            None
        )
        if calculator:
            assert "math" in calculator["matched_tags"]
            assert "calculation" in calculator["matched_tags"]
