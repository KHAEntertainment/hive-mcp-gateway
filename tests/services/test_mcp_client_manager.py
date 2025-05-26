"""Tests for MCP Client Manager"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from tool_gating_mcp.services.mcp_client_manager import MCPClientManager


@pytest.fixture
def mock_mcp_config():
    """Fixture for MCP server configuration"""
    return {
        "command": "test-mcp-server",
        "args": ["--test"],
        "env": {"TEST_ENV": "true"}
    }


@pytest.fixture
def client_manager():
    """Fixture for MCPClientManager instance"""
    return MCPClientManager()


class TestMCPClientManager:
    """Test cases for MCPClientManager"""

    @pytest.mark.asyncio
    async def test_init(self, client_manager):
        """Test client manager initialization"""
        assert client_manager.sessions == {}
        assert client_manager.transports == {}
        assert client_manager.server_tools == {}
        assert client_manager._active_sessions == {}

    @pytest.mark.asyncio
    async def test_connect_server_success(self, client_manager, mock_mcp_config):
        """Test successful server connection"""
        # Mock the stdio_client and session
        mock_read_stream = AsyncMock()
        mock_write_stream = AsyncMock()
        mock_session = AsyncMock()
        mock_tools_result = MagicMock()
        mock_tools_result.tools = [
            MagicMock(name="test_tool", description="Test tool", inputSchema={})
        ]
        mock_session.list_tools.return_value = mock_tools_result
        
        with patch('tool_gating_mcp.services.mcp_client_manager.stdio_client') as mock_stdio:
            # Setup mock to return streams
            mock_client_context = AsyncMock()
            mock_client_context.__aenter__.return_value = (mock_read_stream, mock_write_stream)
            mock_client_context.__aexit__.return_value = None
            mock_stdio.return_value = mock_client_context
            
            with patch('tool_gating_mcp.services.mcp_client_manager.ClientSession') as mock_session_class:
                # Setup session mock
                mock_session_instance = AsyncMock()
                mock_session_instance.__aenter__.return_value = mock_session
                mock_session_instance.__aexit__.return_value = None
                mock_session_class.return_value = mock_session_instance
                
                # Connect to server
                await client_manager.connect_server("test_server", mock_mcp_config)
                
                # Verify stdio_client was called correctly
                mock_stdio.assert_called_once_with(
                    server_command="test-mcp-server",
                    server_args=["--test"],
                    server_env={"TEST_ENV": "true"}
                )
                
                # Verify session was initialized
                mock_session.initialize.assert_called_once()
                
                # Verify tools were discovered
                mock_session.list_tools.assert_called_once()
                
                # Verify server tools were stored
                assert "test_server" in client_manager.server_tools
                assert len(client_manager.server_tools["test_server"]) == 1
                assert client_manager.server_tools["test_server"][0].name == "test_tool"

    @pytest.mark.asyncio
    async def test_connect_server_failure(self, client_manager, mock_mcp_config):
        """Test server connection failure"""
        with patch('tool_gating_mcp.services.mcp_client_manager.stdio_client') as mock_stdio:
            # Make stdio_client raise an exception
            mock_stdio.side_effect = Exception("Connection failed")
            
            # Attempt connection and expect failure
            with pytest.raises(Exception) as exc_info:
                await client_manager.connect_server("test_server", mock_mcp_config)
            
            assert "Failed to connect to test_server: Connection failed" in str(exc_info.value)
            
            # Verify no active sessions were stored
            assert "test_server" not in client_manager._active_sessions
            assert "test_server" not in client_manager.server_tools

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, client_manager):
        """Test successful tool execution"""
        # Setup active session
        mock_session = AsyncMock()
        mock_result = {"success": True, "data": "test_result"}
        mock_session.call_tool.return_value = mock_result
        
        client_manager._active_sessions["test_server"] = {
            "session": mock_session
        }
        
        # Execute tool
        result = await client_manager.execute_tool("test_server", "test_tool", {"param": "value"})
        
        # Verify
        assert result == mock_result
        mock_session.call_tool.assert_called_once_with("test_tool", {"param": "value"})

    @pytest.mark.asyncio
    async def test_execute_tool_server_not_connected(self, client_manager):
        """Test tool execution with disconnected server"""
        with pytest.raises(ValueError) as exc_info:
            await client_manager.execute_tool("unknown_server", "test_tool", {})
        
        assert "Server unknown_server not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect_server(self, client_manager):
        """Test server disconnection"""
        # Setup active session and tools
        client_manager._active_sessions["test_server"] = {
            "session": AsyncMock()
        }
        client_manager.server_tools["test_server"] = ["tool1", "tool2"]
        
        # Disconnect
        await client_manager.disconnect_server("test_server")
        
        # Verify cleanup
        assert "test_server" not in client_manager._active_sessions
        assert "test_server" not in client_manager.server_tools

    @pytest.mark.asyncio
    async def test_disconnect_server_not_connected(self, client_manager):
        """Test disconnecting non-existent server"""
        # Should not raise error
        await client_manager.disconnect_server("unknown_server")
        
        # Verify nothing changed
        assert len(client_manager._active_sessions) == 0

    @pytest.mark.asyncio
    async def test_disconnect_all(self, client_manager):
        """Test disconnecting all servers"""
        # Setup multiple active sessions
        client_manager._active_sessions = {
            "server1": {"session": AsyncMock()},
            "server2": {"session": AsyncMock()},
            "server3": {"session": AsyncMock()}
        }
        client_manager.server_tools = {
            "server1": ["tool1"],
            "server2": ["tool2"],
            "server3": ["tool3"]
        }
        
        # Disconnect all
        await client_manager.disconnect_all()
        
        # Verify all cleaned up
        assert len(client_manager._active_sessions) == 0
        assert len(client_manager.server_tools) == 0

    @pytest.mark.asyncio
    async def test_multiple_server_connections(self, client_manager):
        """Test connecting to multiple servers"""
        configs = {
            "server1": {"command": "mcp1", "args": []},
            "server2": {"command": "mcp2", "args": ["--flag"]},
        }
        
        with patch('tool_gating_mcp.services.mcp_client_manager.stdio_client') as mock_stdio:
            # Setup different responses for each server
            mock_sessions = {}
            for server_name in configs:
                mock_read = AsyncMock()
                mock_write = AsyncMock()
                mock_session = AsyncMock()
                
                # Different tools for each server
                mock_tools_result = MagicMock()
                mock_tools_result.tools = [
                    MagicMock(name=f"{server_name}_tool", description=f"Tool from {server_name}", inputSchema={})
                ]
                mock_session.list_tools.return_value = mock_tools_result
                mock_sessions[server_name] = mock_session
                
                # Setup context manager
                mock_client_context = AsyncMock()
                mock_client_context.__aenter__.return_value = (mock_read, mock_write)
                mock_client_context.__aexit__.return_value = None
                
                # Configure stdio_client to return different contexts
                if server_name == "server1":
                    mock_stdio.side_effect = [mock_client_context]
                else:
                    mock_stdio.side_effect = [mock_client_context, mock_client_context]
            
            with patch('tool_gating_mcp.services.mcp_client_manager.ClientSession') as mock_session_class:
                # Setup session mocks
                session_contexts = []
                for server_name, mock_session in mock_sessions.items():
                    mock_session_context = AsyncMock()
                    mock_session_context.__aenter__.return_value = mock_session
                    mock_session_context.__aexit__.return_value = None
                    session_contexts.append(mock_session_context)
                
                mock_session_class.side_effect = session_contexts
                
                # Connect to both servers
                for server_name, config in configs.items():
                    await client_manager.connect_server(server_name, config)
                
                # Verify both servers connected
                assert len(client_manager.server_tools) == 2
                assert "server1_tool" in [t.name for t in client_manager.server_tools["server1"]]
                assert "server2_tool" in [t.name for t in client_manager.server_tools["server2"]]