# Test cases for tool gating service
# Tests intelligent tool selection and MCP formatting

from unittest.mock import AsyncMock

import pytest

from tool_gating_mcp.models.tool import MCPTool, Tool
from tool_gating_mcp.services.gating import GatingService


@pytest.fixture
def mock_tool_repo():
    """Mock tool repository for testing."""
    repo = AsyncMock()
    repo.get_by_ids = AsyncMock()
    repo.get_popular = AsyncMock()
    return repo


@pytest.fixture
def gating_service(mock_tool_repo):
    """Create gating service with mocked dependencies."""
    service = GatingService(mock_tool_repo)
    service.max_tokens = 500  # Set token limit for testing
    service.max_tools = 3  # Set tool limit for testing
    return service


@pytest.fixture
def sample_tools():
    """Sample tools for testing."""
    return [
        Tool(
            id="calc-1",
            name="Calculator",
            description="Math calculations",
            tags=["math"],
            estimated_tokens=100,
            parameters={
                "type": "object",
                "properties": {
                    "operation": {"type": "string"},
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
            },
        ),
        Tool(
            id="weather-1",
            name="Weather",
            description="Weather info",
            tags=["weather"],
            estimated_tokens=150,
            parameters={
                "type": "object",
                "properties": {"location": {"type": "string"}},
            },
        ),
        Tool(
            id="translate-1",
            name="Translator",
            description="Language translation",
            tags=["language"],
            estimated_tokens=200,
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "target_lang": {"type": "string"},
                },
            },
        ),
        Tool(
            id="large-1",
            name="LargeTool",
            description="Tool with many tokens",
            tags=["large"],
            estimated_tokens=400,
            parameters={"type": "object"},
        ),
    ]


@pytest.mark.asyncio
async def test_select_tools_by_ids(gating_service, mock_tool_repo, sample_tools):
    """Test selecting specific tools by IDs."""
    mock_tool_repo.get_by_ids.return_value = sample_tools[:2]

    selected = await gating_service.select_tools(tool_ids=["calc-1", "weather-1"])

    assert len(selected) == 2
    assert selected[0].id == "calc-1"
    assert selected[1].id == "weather-1"
    mock_tool_repo.get_by_ids.assert_called_once_with(["calc-1", "weather-1"])


@pytest.mark.asyncio
async def test_select_tools_token_limit(gating_service, mock_tool_repo, sample_tools):
    """Test that token budget is respected."""
    mock_tool_repo.get_by_ids.return_value = sample_tools

    # With 500 token limit, should only select first 3 tools (100+150+200=450)
    selected = await gating_service.select_tools(tool_ids=[t.id for t in sample_tools])

    total_tokens = sum(t.estimated_tokens for t in selected)
    assert total_tokens <= 500
    assert len(selected) == 3  # First three tools fit within budget


@pytest.mark.asyncio
async def test_select_tools_count_limit(gating_service, mock_tool_repo, sample_tools):
    """Test that tool count limit is respected."""
    mock_tool_repo.get_by_ids.return_value = sample_tools[:2]

    selected = await gating_service.select_tools(
        tool_ids=[t.id for t in sample_tools[:2]], max_tools=1
    )

    assert len(selected) == 1


@pytest.mark.asyncio
async def test_select_popular_tools(gating_service, mock_tool_repo, sample_tools):
    """Test selecting popular tools when no IDs provided."""
    mock_tool_repo.get_popular.return_value = sample_tools[:3]

    selected = await gating_service.select_tools()

    assert len(selected) <= 3
    mock_tool_repo.get_popular.assert_called_once()


@pytest.mark.asyncio
async def test_format_for_mcp(gating_service, sample_tools):
    """Test converting tools to MCP format."""
    mcp_tools = await gating_service.format_for_mcp(sample_tools[:2])

    assert len(mcp_tools) == 2
    assert all(isinstance(t, MCPTool) for t in mcp_tools)

    # Check first tool
    assert mcp_tools[0].name == "Calculator"
    assert mcp_tools[0].description == "Math calculations"
    assert mcp_tools[0].inputSchema == sample_tools[0].parameters

    # Check second tool
    assert mcp_tools[1].name == "Weather"
    assert mcp_tools[1].description == "Weather info"


@pytest.mark.asyncio
async def test_empty_tool_selection(gating_service, mock_tool_repo):
    """Test handling empty tool selection."""
    mock_tool_repo.get_by_ids.return_value = []

    selected = await gating_service.select_tools(tool_ids=[])

    assert selected == []


@pytest.mark.asyncio
async def test_format_empty_tools(gating_service):
    """Test formatting empty tool list."""
    mcp_tools = await gating_service.format_for_mcp([])

    assert mcp_tools == []
