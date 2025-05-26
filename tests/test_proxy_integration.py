"""Integration tests for MCP Proxy functionality"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
import asyncio

from tool_gating_mcp.main import app
from tool_gating_mcp.services.mcp_client_manager import MCPClientManager
from tool_gating_mcp.services.proxy_service import ProxyService
from tool_gating_mcp.services.repository import InMemoryToolRepository
from tool_gating_mcp.models.tool import Tool


@pytest.fixture
def mock_mcp_servers():
    """Mock MCP server configurations"""
    return {
        "puppeteer": {
            "command": "mcp-server-puppeteer",
            "args": [],
            "description": "Browser automation"
        },
        "filesystem": {
            "command": "mcp-server-filesystem", 
            "args": ["--root", "/tmp"],
            "description": "File operations"
        }
    }


class TestProxyIntegration:
    """Integration tests for proxy functionality"""

    @pytest.mark.asyncio
    async def test_full_proxy_workflow(self, mock_mcp_servers):
        """Test complete workflow: connect -> discover -> provision -> execute"""
        # Create services
        client_manager = MCPClientManager()
        tool_repository = InMemoryToolRepository()
        proxy_service = ProxyService(client_manager, tool_repository)
        
        # Mock MCP connections
        with patch('tool_gating_mcp.services.mcp_client_manager.stdio_client') as mock_stdio:
            # Setup mock tools for each server
            mock_tools = {
                "puppeteer": [
                    MagicMock(
                        name="screenshot",
                        description="Take a screenshot",
                        inputSchema={"type": "object"}
                    ),
                    MagicMock(
                        name="navigate",
                        description="Navigate to URL",
                        inputSchema={"type": "object"}
                    )
                ],
                "filesystem": [
                    MagicMock(
                        name="read_file",
                        description="Read a file",
                        inputSchema={"type": "object"}
                    )
                ]
            }
            
            # Setup stdio mocks
            for server_name in mock_mcp_servers:
                mock_read = AsyncMock()
                mock_write = AsyncMock()
                mock_session = AsyncMock()
                
                # Configure tools for this server
                mock_tools_result = MagicMock()
                mock_tools_result.tools = mock_tools[server_name]
                mock_session.list_tools.return_value = mock_tools_result
                
                # Setup context managers
                mock_client_context = AsyncMock()
                mock_client_context.__aenter__.return_value = (mock_read, mock_write)
                mock_client_context.__aexit__.return_value = None
                
                mock_stdio.return_value = mock_client_context
                
                with patch('tool_gating_mcp.services.mcp_client_manager.ClientSession') as mock_session_class:
                    mock_session_context = AsyncMock()
                    mock_session_context.__aenter__.return_value = mock_session
                    mock_session_context.__aexit__.return_value = None
                    mock_session_class.return_value = mock_session_context
                    
                    # Connect to server
                    await client_manager.connect_server(server_name, mock_mcp_servers[server_name])
                    
                    # Store session for later use
                    client_manager._active_sessions[server_name] = {
                        "session": mock_session
                    }
            
            # Discover all tools
            await proxy_service.discover_all_tools()
            
            # Verify tools were discovered
            all_tools = await tool_repository.get_all()
            assert len(all_tools) == 3
            tool_ids = [tool.id for tool in all_tools]
            assert "puppeteer_screenshot" in tool_ids
            assert "puppeteer_navigate" in tool_ids
            assert "filesystem_read_file" in tool_ids
            
            # Provision specific tools
            proxy_service.provision_tool("puppeteer_screenshot")
            proxy_service.provision_tool("filesystem_read_file")
            
            # Execute a tool
            mock_result = {"success": True, "screenshot": "base64_data"}
            client_manager._active_sessions["puppeteer"]["session"].call_tool.return_value = mock_result
            
            result = await proxy_service.execute_tool(
                "puppeteer_screenshot",
                {"name": "test", "url": "https://example.com"}
            )
            
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_cross_server_tool_execution(self):
        """Test executing tools from different servers"""
        client_manager = MCPClientManager()
        tool_repository = InMemoryToolRepository()
        proxy_service = ProxyService(client_manager, tool_repository)
        
        # Setup mock sessions for multiple servers
        mock_sessions = {
            "exa": AsyncMock(),
            "context7": AsyncMock()
        }
        
        for server_name, session in mock_sessions.items():
            client_manager._active_sessions[server_name] = {"session": session}
        
        # Provision tools from different servers
        proxy_service.provision_tool("exa_web_search")
        proxy_service.provision_tool("context7_doc_search")
        
        # Execute tool from first server
        exa_result = {"results": ["result1", "result2"]}
        mock_sessions["exa"].call_tool.return_value = exa_result
        
        result1 = await proxy_service.execute_tool(
            "exa_web_search",
            {"query": "test query"}
        )
        assert result1 == exa_result
        mock_sessions["exa"].call_tool.assert_called_once_with(
            "web_search",
            {"query": "test query"}
        )
        
        # Execute tool from second server
        context_result = {"docs": ["doc1", "doc2"]}
        mock_sessions["context7"].call_tool.return_value = context_result
        
        result2 = await proxy_service.execute_tool(
            "context7_doc_search",
            {"query": "api documentation"}
        )
        assert result2 == context_result
        mock_sessions["context7"].call_tool.assert_called_once_with(
            "doc_search",
            {"query": "api documentation"}
        )

    @pytest.mark.asyncio
    async def test_tool_discovery_with_semantic_search(self):
        """Test discovering tools using semantic search after proxy setup"""
        from tool_gating_mcp.services.discovery import DiscoveryService
        from tool_gating_mcp.services.gating import GatingService
        
        # Setup services
        tool_repository = InMemoryToolRepository()
        discovery_service = DiscoveryService(tool_repository)
        gating_service = GatingService(tool_repository, discovery_service)
        
        # Add tools from multiple servers
        tools = [
            Tool(
                id="puppeteer_screenshot",
                name="screenshot",
                description="Take a screenshot of a webpage",
                parameters={},
                server="puppeteer",
                tags=["browser", "screenshot", "web"],
                estimated_tokens=100
            ),
            Tool(
                id="puppeteer_navigate",
                name="navigate",
                description="Navigate browser to a URL",
                parameters={},
                server="puppeteer",
                tags=["browser", "navigation", "web"],
                estimated_tokens=80
            ),
            Tool(
                id="exa_web_search",
                name="web_search",
                description="Search the web for information",
                parameters={},
                server="exa",
                tags=["search", "web", "api"],
                estimated_tokens=150
            ),
            Tool(
                id="filesystem_read_file",
                name="read_file",
                description="Read contents of a file",
                parameters={},
                server="filesystem",
                tags=["file", "read", "filesystem"],
                estimated_tokens=120
            )
        ]
        
        for tool in tools:
            await tool_repository.add_tool(tool)
        
        # Search for browser-related tools
        browser_tools = await discovery_service.find_relevant_tools(
            query="I need to take screenshots of websites",
            limit=3
        )
        
        # Should prioritize screenshot tool
        assert len(browser_tools) > 0
        assert browser_tools[0].tool.id == "puppeteer_screenshot"
        
        # Search for file operations
        file_tools = await discovery_service.find_relevant_tools(
            query="read and write files",
            limit=3
        )
        
        # Should find filesystem tool
        tool_ids = [match.tool.id for match in file_tools]
        assert "filesystem_read_file" in tool_ids

    @pytest.mark.asyncio
    async def test_execute_tool_mcp_endpoint(self):
        """Test executing tool through MCP endpoint (simulated)"""
        # This tests the execute_tool function that would be exposed as MCP tool
        from tool_gating_mcp.main import app
        
        # Setup mock proxy service
        mock_proxy_service = AsyncMock()
        mock_result = {"success": True, "data": "test"}
        mock_proxy_service.execute_tool.return_value = mock_result
        
        # Store in app state
        app.state.proxy_service = mock_proxy_service
        
        # Import the execute_tool function (would be MCP tool in real app)
        from tool_gating_mcp.main import execute_tool
        
        # Execute
        result = await execute_tool("test_tool", {"param": "value"})
        
        assert result == mock_result
        mock_proxy_service.execute_tool.assert_called_once_with(
            "test_tool",
            {"param": "value"}
        )