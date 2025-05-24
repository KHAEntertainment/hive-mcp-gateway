# Test cases for tool discovery service
# Tests semantic search and tag-based tool discovery

from unittest.mock import AsyncMock, MagicMock

import pytest

from tool_gating_mcp.models.tool import Tool, ToolMatch
from tool_gating_mcp.services.discovery import DiscoveryService


@pytest.fixture
def mock_tool_repo():
    """Mock tool repository for testing."""
    repo = AsyncMock()
    repo.get_all = AsyncMock(
        return_value=[
            Tool(
                id="calc-1",
                name="Calculator",
                description="Perform mathematical calculations",
                tags=["math", "calculation"],
                estimated_tokens=150,
            ),
            Tool(
                id="weather-1",
                name="Weather API",
                description="Get current weather information",
                tags=["weather", "api"],
                estimated_tokens=200,
            ),
            Tool(
                id="converter-1",
                name="Unit Converter",
                description="Convert between different units of measurement",
                tags=["math", "conversion", "units"],
                estimated_tokens=180,
            ),
        ]
    )
    return repo


@pytest.fixture
def discovery_service(mock_tool_repo):
    """Create discovery service with mocked dependencies."""
    service = DiscoveryService(mock_tool_repo)
    # Mock the sentence transformer
    service.encoder = MagicMock()
    service.encoder.encode = MagicMock(
        side_effect=lambda text: [0.5, 0.5]
    )  # Simple mock embedding
    return service


@pytest.mark.asyncio
async def test_find_relevant_tools_by_query(discovery_service):
    """Test finding tools by semantic query."""
    results = await discovery_service.find_relevant_tools(
        query="I need to do some calculations", limit=2
    )

    assert len(results) <= 2
    assert all(isinstance(result, ToolMatch) for result in results)
    assert all(0 <= result.score <= 1 for result in results)


@pytest.mark.asyncio
async def test_find_relevant_tools_by_tags(discovery_service, mock_tool_repo):
    """Test filtering tools by tags."""
    results = await discovery_service.find_relevant_tools(
        query="any tool", tags=["math"], limit=10
    )

    # Should only return tools with "math" tag
    math_tools = [r for r in results if "math" in r.tool.tags]
    assert len(math_tools) == len(results)
    assert all("math" in result.matched_tags for result in results)


@pytest.mark.asyncio
async def test_find_relevant_tools_with_context(discovery_service):
    """Test tool discovery with additional context."""

    # Mock encoder to return different embeddings based on text content
    def mock_encode(text):
        if "weather" in text.lower() or "temperature" in text.lower():
            return [0.9, 0.1]
        else:
            return [0.1, 0.1]

    discovery_service.encoder.encode = MagicMock(side_effect=mock_encode)

    results = await discovery_service.find_relevant_tools(
        query="temperature",
        context="User is asking about weather in their city",
        limit=1,
    )

    assert len(results) <= 1
    if results:
        assert results[0].tool.name == "Weather API"


@pytest.mark.asyncio
async def test_find_relevant_tools_empty_query(discovery_service):
    """Test discovery with empty results."""
    # Mock empty tool list
    discovery_service.tool_repo.get_all = AsyncMock(return_value=[])

    results = await discovery_service.find_relevant_tools(
        query="find something", limit=5
    )

    assert results == []


@pytest.mark.asyncio
async def test_semantic_scoring(discovery_service):
    """Test that semantic similarity scoring works."""
    results = await discovery_service.find_relevant_tools(
        query="mathematical operations", limit=3
    )

    # Results should be sorted by score
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_tag_boosting(discovery_service):
    """Test that tag matches boost scores."""
    results = await discovery_service.find_relevant_tools(
        query="convert", tags=["conversion"], limit=3
    )

    # Tool with matching tag should have higher score
    converter_match = next((r for r in results if r.tool.id == "converter-1"), None)
    assert converter_match is not None
    assert "conversion" in converter_match.matched_tags
