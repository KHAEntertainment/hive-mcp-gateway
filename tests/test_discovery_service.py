import pytest
from unittest.mock import AsyncMock, Mock, patch
import numpy as np

from tool_gating_mcp.services.discovery import DiscoveryService
from tool_gating_mcp.models.tool import Tool, ToolMatch


@pytest.fixture
def mock_tool_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def sample_tools():
    return [
        Tool(
            id="calculator",
            name="Calculator",
            description="Perform mathematical calculations and solve equations",
            tags=["math", "calculation", "arithmetic"],
            estimated_tokens=50
        ),
        Tool(
            id="web-search",
            name="Web Search",
            description="Search the web for information and retrieve results",
            tags=["search", "web", "internet", "query"],
            estimated_tokens=100
        ),
        Tool(
            id="file-reader",
            name="File Reader",
            description="Read and parse files from the filesystem",
            tags=["file", "io", "read", "filesystem"],
            estimated_tokens=75
        ),
        Tool(
            id="database-query",
            name="Database Query",
            description="Execute SQL queries and manage database operations",
            tags=["database", "sql", "query", "data"],
            estimated_tokens=120
        ),
        Tool(
            id="image-processor",
            name="Image Processor",
            description="Process and manipulate images with various filters",
            tags=["image", "graphics", "visual", "processing"],
            estimated_tokens=150
        )
    ]


class TestDiscoveryService:
    @pytest.mark.asyncio
    async def test_find_relevant_tools_by_query(self, mock_tool_repo, sample_tools):
        # Arrange
        mock_tool_repo.get_all.return_value = sample_tools
        service = DiscoveryService(mock_tool_repo)
        
        # Act
        results = await service.find_relevant_tools(
            query="I need to perform some calculations",
            limit=3
        )
        
        # Assert
        assert len(results) <= 3
        assert all(isinstance(r, ToolMatch) for r in results)
        # Calculator should be ranked high for calculation query
        tool_ids = [r.tool.id for r in results]
        assert "calculator" in tool_ids
        
    @pytest.mark.asyncio
    async def test_find_relevant_tools_with_tags(self, mock_tool_repo, sample_tools):
        # Arrange
        mock_tool_repo.get_all.return_value = sample_tools
        service = DiscoveryService(mock_tool_repo)
        
        # Act
        results = await service.find_relevant_tools(
            query="data processing",
            tags=["database", "query"],
            limit=5
        )
        
        # Assert
        # Tools with matching tags should be boosted
        assert len(results) > 0
        # Find the database tool in results
        db_tool = next((r for r in results if r.tool.id == "database-query"), None)
        assert db_tool is not None
        assert "database" in db_tool.matched_tags
        assert "query" in db_tool.matched_tags
        # It should have a high score due to tag boost
        assert db_tool.score > 0.5
        
    @pytest.mark.asyncio
    async def test_find_relevant_tools_with_context(self, mock_tool_repo, sample_tools):
        # Arrange
        mock_tool_repo.get_all.return_value = sample_tools
        service = DiscoveryService(mock_tool_repo)
        
        # Act
        results = await service.find_relevant_tools(
            query="read data",
            context="User wants to read CSV files from disk",
            limit=3
        )
        
        # Assert
        # File reader should rank high
        tool_ids = [r.tool.id for r in results]
        assert "file-reader" in tool_ids
        
    @pytest.mark.asyncio
    async def test_semantic_scoring(self, mock_tool_repo, sample_tools):
        # Arrange
        mock_tool_repo.get_all.return_value = sample_tools
        service = DiscoveryService(mock_tool_repo)
        
        # Act
        results = await service.find_relevant_tools(
            query="search for information online",
            limit=10
        )
        
        # Assert
        # All tools should have scores
        assert all(r.score > 0 for r in results)
        # Scores should be descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
        # Web search tool should be in the results
        web_search = next((r for r in results if r.tool.id == "web-search"), None)
        assert web_search is not None
        
    @pytest.mark.asyncio
    async def test_empty_tool_registry(self, mock_tool_repo):
        # Arrange
        mock_tool_repo.get_all.return_value = []
        service = DiscoveryService(mock_tool_repo)
        
        # Act
        results = await service.find_relevant_tools(
            query="any query",
            limit=5
        )
        
        # Assert
        assert results == []
        
    @pytest.mark.asyncio
    async def test_tag_filtering(self, mock_tool_repo, sample_tools):
        # Arrange
        mock_tool_repo.get_all.return_value = sample_tools
        service = DiscoveryService(mock_tool_repo)
        
        # Act
        results = await service.find_relevant_tools(
            query="anything",
            tags=["math", "calculation"],
            limit=10
        )
        
        # Assert
        # Only calculator has both tags
        matching_tools = [r for r in results if len(r.matched_tags) > 0]
        assert len(matching_tools) >= 1
        assert matching_tools[0].tool.id == "calculator"
        
    @pytest.mark.asyncio
    async def test_limit_parameter(self, mock_tool_repo, sample_tools):
        # Arrange
        mock_tool_repo.get_all.return_value = sample_tools
        service = DiscoveryService(mock_tool_repo)
        
        # Test various limits
        for limit in [1, 2, 3, 5, 10]:
            # Act
            results = await service.find_relevant_tools(
                query="general query",
                limit=limit
            )
            
            # Assert
            assert len(results) <= limit
            
    @pytest.mark.asyncio
    async def test_caching_behavior(self, mock_tool_repo, sample_tools):
        # Arrange
        mock_tool_repo.get_all.return_value = sample_tools
        service = DiscoveryService(mock_tool_repo)
        
        # Act - first call should compute embeddings
        results1 = await service.find_relevant_tools(
            query="test query",
            limit=3
        )
        
        # Act - second call should use cached embeddings
        results2 = await service.find_relevant_tools(
            query="test query",
            limit=3
        )
        
        # Assert
        assert results1[0].tool.id == results2[0].tool.id
        # Repository should only be called once per test
        assert mock_tool_repo.get_all.call_count == 2
        
    @pytest.mark.asyncio
    async def test_score_validation(self, mock_tool_repo, sample_tools):
        # Arrange
        mock_tool_repo.get_all.return_value = sample_tools
        service = DiscoveryService(mock_tool_repo)
        
        # Act
        results = await service.find_relevant_tools(
            query="any query",
            limit=10
        )
        
        # Assert - all scores should be valid
        for result in results:
            assert 0.0 <= result.score <= 1.0
            assert isinstance(result.score, float)