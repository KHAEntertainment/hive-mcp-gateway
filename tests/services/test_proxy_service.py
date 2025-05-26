"""Tests for Proxy Service"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from typing import Any

from tool_gating_mcp.services.proxy_service import ProxyService
from tool_gating_mcp.services.mcp_client_manager import MCPClientManager
from tool_gating_mcp.services.repository import InMemoryToolRepository
from tool_gating_mcp.models.tool import Tool


@pytest.fixture
def mock_client_manager():
    """Fixture for mock MCPClientManager"""
    manager = Mock(spec=MCPClientManager)
    manager.server_tools = {}
    manager.execute_tool = AsyncMock()
    return manager


@pytest.fixture
def mock_tool_repository():
    """Fixture for mock tool repository"""
    repo = Mock(spec=InMemoryToolRepository)
    repo.add_tool = AsyncMock()
    return repo


@pytest.fixture
def proxy_service(mock_client_manager, mock_tool_repository):
    """Fixture for ProxyService instance"""
    return ProxyService(mock_client_manager, mock_tool_repository)


class TestProxyService:
    """Test cases for ProxyService"""

    def test_init(self, proxy_service, mock_client_manager, mock_tool_repository):
        """Test proxy service initialization"""
        assert proxy_service.client_manager == mock_client_manager
        assert proxy_service.tool_repository == mock_tool_repository
        assert proxy_service.provisioned_tools == set()

    @pytest.mark.asyncio
    async def test_discover_all_tools_empty(self, proxy_service):
        """Test discovering tools when no servers connected"""
        proxy_service.client_manager.server_tools = {}
        
        await proxy_service.discover_all_tools()
        
        # No tools should be added
        proxy_service.tool_repository.add_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_discover_all_tools_single_server(self, proxy_service):
        """Test discovering tools from a single server"""
        # Setup mock tools
        mock_tool1 = MagicMock()
        mock_tool1.name = "screenshot"
        mock_tool1.description = "Take a screenshot of a webpage"
        mock_tool1.inputSchema = {"type": "object", "properties": {"url": {"type": "string"}}}
        
        mock_tool2 = MagicMock()
        mock_tool2.name = "navigate"
        mock_tool2.description = "Navigate to a URL"
        mock_tool2.inputSchema = {"type": "object", "properties": {"url": {"type": "string"}}}
        
        proxy_service.client_manager.server_tools = {
            "puppeteer": [mock_tool1, mock_tool2]
        }
        
        await proxy_service.discover_all_tools()
        
        # Verify tools were added to repository
        assert proxy_service.tool_repository.add_tool.call_count == 2
        
        # Check first tool
        first_call = proxy_service.tool_repository.add_tool.call_args_list[0]
        tool_obj = first_call[0][0]
        assert tool_obj.id == "puppeteer_screenshot"
        assert tool_obj.name == "screenshot"
        assert tool_obj.description == "Take a screenshot of a webpage"
        assert tool_obj.server == "puppeteer"
        assert "browser" in tool_obj.tags or "screenshot" in tool_obj.tags

    @pytest.mark.asyncio
    async def test_discover_all_tools_multiple_servers(self, proxy_service):
        """Test discovering tools from multiple servers"""
        # Setup mock tools for multiple servers
        mock_exa_tool = MagicMock()
        mock_exa_tool.name = "web_search"
        mock_exa_tool.description = "Search the web"
        mock_exa_tool.inputSchema = {}
        
        mock_context_tool = MagicMock()
        mock_context_tool.name = "doc_search"
        mock_context_tool.description = "Search documentation"
        mock_context_tool.inputSchema = {}
        
        proxy_service.client_manager.server_tools = {
            "exa": [mock_exa_tool],
            "context7": [mock_context_tool]
        }
        
        await proxy_service.discover_all_tools()
        
        # Verify all tools were added
        assert proxy_service.tool_repository.add_tool.call_count == 2
        
        # Get tool IDs that were added
        tool_ids = [call[0][0].id for call in proxy_service.tool_repository.add_tool.call_args_list]
        assert "exa_web_search" in tool_ids
        assert "context7_doc_search" in tool_ids

    def test_provision_tool(self, proxy_service):
        """Test provisioning a tool"""
        tool_id = "puppeteer_screenshot"
        
        proxy_service.provision_tool(tool_id)
        
        assert tool_id in proxy_service.provisioned_tools

    def test_unprovision_tool(self, proxy_service):
        """Test unprovisioning a tool"""
        tool_id = "puppeteer_screenshot"
        proxy_service.provisioned_tools.add(tool_id)
        
        proxy_service.unprovision_tool(tool_id)
        
        assert tool_id not in proxy_service.provisioned_tools

    def test_unprovision_tool_not_provisioned(self, proxy_service):
        """Test unprovisioning a tool that wasn't provisioned"""
        # Should not raise error
        proxy_service.unprovision_tool("unknown_tool")
        
        assert "unknown_tool" not in proxy_service.provisioned_tools

    def test_is_provisioned(self, proxy_service):
        """Test checking if tool is provisioned"""
        tool_id = "puppeteer_screenshot"
        
        # Not provisioned initially
        assert not proxy_service.is_provisioned(tool_id)
        
        # Provision it
        proxy_service.provisioned_tools.add(tool_id)
        assert proxy_service.is_provisioned(tool_id)

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, proxy_service):
        """Test successful tool execution"""
        tool_id = "puppeteer_screenshot"
        arguments = {"name": "test", "selector": "body"}
        expected_result = {"success": True, "data": "screenshot_data"}
        
        # Provision the tool
        proxy_service.provision_tool(tool_id)
        
        # Setup mock response
        proxy_service.client_manager.execute_tool.return_value = expected_result
        
        # Execute
        result = await proxy_service.execute_tool(tool_id, arguments)
        
        # Verify
        assert result == expected_result
        proxy_service.client_manager.execute_tool.assert_called_once_with(
            "puppeteer", "screenshot", arguments
        )

    @pytest.mark.asyncio
    async def test_execute_tool_not_provisioned(self, proxy_service):
        """Test executing non-provisioned tool"""
        tool_id = "puppeteer_screenshot"
        
        with pytest.raises(ValueError) as exc_info:
            await proxy_service.execute_tool(tool_id, {})
        
        assert "Tool puppeteer_screenshot not provisioned" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_tool_server_not_found(self, proxy_service):
        """Test executing tool when server doesn't exist"""
        tool_id = "unknown_server_tool"
        proxy_service.provision_tool(tool_id)
        
        # Mock the client manager to raise error for unknown server
        proxy_service.client_manager.execute_tool.side_effect = ValueError("Server unknown_server not connected")
        
        with pytest.raises(ValueError) as exc_info:
            await proxy_service.execute_tool(tool_id, {})
        
        assert "Server unknown_server not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_tool_with_underscore_in_name(self, proxy_service):
        """Test executing tool where tool name contains underscore"""
        tool_id = "exa_research_paper_search"  # Server: exa, Tool: research_paper_search
        arguments = {"query": "AI safety"}
        expected_result = {"papers": []}
        
        # Provision the tool
        proxy_service.provision_tool(tool_id)
        
        # Setup mock response
        proxy_service.client_manager.execute_tool.return_value = expected_result
        
        # Execute
        result = await proxy_service.execute_tool(tool_id, arguments)
        
        # Verify - should split only on first underscore
        assert result == expected_result
        proxy_service.client_manager.execute_tool.assert_called_once_with(
            "exa", "research_paper_search", arguments
        )

    def test_extract_tags_empty_description(self, proxy_service):
        """Test tag extraction with empty description"""
        tags = proxy_service._extract_tags(None)
        assert tags == []
        
        tags = proxy_service._extract_tags("")
        assert tags == []

    def test_extract_tags_with_keywords(self, proxy_service):
        """Test tag extraction with matching keywords"""
        description = "Search the web for information and browse websites"
        tags = proxy_service._extract_tags(description)
        
        assert "search" in tags
        assert "web" in tags
        # "browser" is only added if "browser" keyword is in description, not "browse"

    def test_extract_tags_no_matches(self, proxy_service):
        """Test tag extraction with no matching keywords"""
        description = "Calculate mathematical expressions"
        tags = proxy_service._extract_tags(description)
        
        # Should not contain unrelated tags
        assert "search" not in tags
        assert "web" not in tags

    def test_estimate_tokens_empty_tool(self, proxy_service):
        """Test token estimation for empty tool"""
        mock_tool = MagicMock()
        mock_tool.description = None
        mock_tool.inputSchema = None
        
        tokens = proxy_service._estimate_tokens(mock_tool)
        
        # Should return base overhead (50)
        # But empty string split returns [''] with length 1, so 1 * 1.3 = 1.3, rounded to 1
        # So total is 1 + 1 + 50 = 52, but int(1.3 + 1.3 + 50) = 52
        assert 50 <= tokens <= 52

    def test_estimate_tokens_with_content(self, proxy_service):
        """Test token estimation with description and schema"""
        mock_tool = MagicMock()
        mock_tool.description = "This is a test tool for demonstration"  # ~7 words
        mock_tool.inputSchema = {
            "type": "object",
            "properties": {
                "param1": {"type": "string"},
                "param2": {"type": "number"}
            }
        }  # ~10 words
        
        tokens = proxy_service._estimate_tokens(mock_tool)
        
        # Should be approximately (7 * 1.3) + (10 * 1.3) + 50 = ~72
        assert 65 < tokens < 80