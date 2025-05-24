import pytest
from unittest.mock import AsyncMock, Mock

from tool_gating_mcp.services.gating import GatingService
from tool_gating_mcp.models.tool import Tool, MCPTool


@pytest.fixture
def mock_tool_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def gating_service(mock_tool_repo):
    return GatingService(mock_tool_repo)


@pytest.fixture
def sample_tools():
    return [
        Tool(
            id="tool-1",
            name="Tool 1",
            description="First tool",
            estimated_tokens=50,
            tags=["tag1", "tag2"]
        ),
        Tool(
            id="tool-2",
            name="Tool 2",
            description="Second tool",
            estimated_tokens=100,
            tags=["tag2", "tag3"]
        ),
        Tool(
            id="tool-3",
            name="Tool 3",
            description="Third tool",
            estimated_tokens=150,
            tags=["tag3", "tag4"]
        ),
        Tool(
            id="tool-4",
            name="Tool 4",
            description="Fourth tool",
            estimated_tokens=200,
            tags=["tag4", "tag5"]
        ),
        Tool(
            id="tool-5",
            name="Tool 5",
            description="Fifth tool",
            estimated_tokens=75,
            tags=["tag5", "tag1"]
        )
    ]


class TestGatingService:
    @pytest.mark.asyncio
    async def test_select_tools_by_ids(self, gating_service, mock_tool_repo, sample_tools):
        # Arrange
        selected_ids = ["tool-1", "tool-3", "tool-5"]
        mock_tool_repo.get_by_ids.return_value = [
            t for t in sample_tools if t.id in selected_ids
        ]
        
        # Act
        result = await gating_service.select_tools(
            tool_ids=selected_ids,
            max_tools=5
        )
        
        # Assert
        assert len(result) == 3
        assert all(t.id in selected_ids for t in result)
        mock_tool_repo.get_by_ids.assert_called_once_with(selected_ids)
        
    @pytest.mark.asyncio
    async def test_select_tools_with_max_limit(self, gating_service, mock_tool_repo, sample_tools):
        # Arrange
        mock_tool_repo.get_by_ids.return_value = sample_tools
        
        # Act
        result = await gating_service.select_tools(
            tool_ids=[t.id for t in sample_tools],
            max_tools=3
        )
        
        # Assert
        assert len(result) == 3
        # Should select first 3 tools that fit
        
    @pytest.mark.asyncio
    async def test_select_tools_with_token_budget(self, gating_service, mock_tool_repo, sample_tools):
        # Arrange
        mock_tool_repo.get_by_ids.return_value = sample_tools
        gating_service.max_tokens = 250  # Can fit tool-1 (50) + tool-2 (100) + tool-5 (75) = 225
        
        # Act
        result = await gating_service.select_tools(
            tool_ids=[t.id for t in sample_tools],
            max_tools=10
        )
        
        # Assert
        total_tokens = sum(t.estimated_tokens for t in result)
        assert total_tokens <= 250
        # Should have selected tools that fit within budget
        
    @pytest.mark.asyncio
    async def test_select_tools_no_ids_uses_popular(self, gating_service, mock_tool_repo, sample_tools):
        # Arrange
        mock_tool_repo.get_popular.return_value = sample_tools[:3]
        
        # Act
        result = await gating_service.select_tools(max_tools=5)
        
        # Assert
        assert len(result) <= 3
        mock_tool_repo.get_popular.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_format_for_mcp(self, gating_service, sample_tools):
        # Arrange
        tools = sample_tools[:2]
        
        # Act
        mcp_tools = await gating_service.format_for_mcp(tools)
        
        # Assert
        assert len(mcp_tools) == 2
        assert all(isinstance(t, MCPTool) for t in mcp_tools)
        
        # Check first tool conversion
        assert mcp_tools[0].name == "Tool 1"
        assert mcp_tools[0].description == "First tool"
        assert mcp_tools[0].inputSchema == {"type": "object"}  # Default schema when no params
        
    @pytest.mark.asyncio
    async def test_format_for_mcp_with_parameters(self, gating_service):
        # Arrange
        tool_with_params = Tool(
            id="param-tool",
            name="Param Tool",
            description="Tool with parameters",
            estimated_tokens=100,
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                }
            }
        )
        
        # Act
        mcp_tools = await gating_service.format_for_mcp([tool_with_params])
        
        # Assert
        assert len(mcp_tools) == 1
        assert mcp_tools[0].inputSchema == tool_with_params.parameters
        
    @pytest.mark.asyncio
    async def test_empty_tool_selection(self, gating_service, mock_tool_repo):
        # Arrange
        mock_tool_repo.get_by_ids.return_value = []
        
        # Act
        result = await gating_service.select_tools(
            tool_ids=["non-existent"],
            max_tools=5
        )
        
        # Assert
        assert result == []
        
    @pytest.mark.asyncio
    async def test_token_budget_enforcement(self, gating_service, mock_tool_repo):
        # Arrange
        # Create tools with specific token counts
        tools = [
            Tool(id="small", name="Small", description="Small tool", estimated_tokens=50),
            Tool(id="medium", name="Medium", description="Medium tool", estimated_tokens=100),
            Tool(id="large", name="Large", description="Large tool", estimated_tokens=300),
            Tool(id="tiny", name="Tiny", description="Tiny tool", estimated_tokens=25),
        ]
        mock_tool_repo.get_by_ids.return_value = tools
        gating_service.max_tokens = 200  # Can fit small + medium + tiny = 175
        
        # Act
        result = await gating_service.select_tools(
            tool_ids=[t.id for t in tools],
            max_tools=10
        )
        
        # Assert
        total_tokens = sum(t.estimated_tokens for t in result)
        assert total_tokens <= 200
        # Should not include the large tool
        assert not any(t.id == "large" for t in result)
        
    @pytest.mark.asyncio
    async def test_user_context_handling(self, gating_service, mock_tool_repo, sample_tools):
        # Arrange
        mock_tool_repo.get_by_ids.return_value = sample_tools
        user_context = {"user_id": "123", "permissions": ["read", "write"]}
        
        # Act
        result = await gating_service.select_tools(
            tool_ids=[t.id for t in sample_tools],
            max_tools=3,
            user_context=user_context
        )
        
        # Assert
        # For now, user context doesn't affect selection
        assert len(result) <= 3