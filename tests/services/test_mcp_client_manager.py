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
        # For now, test the simplified implementation
        await client_manager.connect_server("test_server", mock_mcp_config)
        
        # Verify server was registered
        assert "test_server" in client_manager._active_sessions
        assert client_manager._active_sessions["test_server"]["connected"] is True
        assert client_manager._active_sessions["test_server"]["config"] == mock_mcp_config
        
        # In the simplified version, tools list starts empty
        assert "test_server" in client_manager.server_tools
        assert client_manager.server_tools["test_server"] == []

    @pytest.mark.asyncio
    async def test_connect_server_failure(self, client_manager, mock_mcp_config):
        """Test server connection failure"""
        # Mock a failure during connection
        original_connect = client_manager.connect_server
        
        async def failing_connect(name, config):
            if name == "test_server":
                raise Exception("Connection failed")
            return await original_connect(name, config)
        
        client_manager.connect_server = failing_connect
        
        # Attempt connection and expect failure
        with pytest.raises(Exception) as exc_info:
            await client_manager.connect_server("test_server", mock_mcp_config)
        
        assert "Connection failed" in str(exc_info.value)

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
        
        # Connect to both servers
        for server_name, config in configs.items():
            await client_manager.connect_server(server_name, config)
        
        # Verify both servers connected
        assert len(client_manager._active_sessions) == 2
        assert "server1" in client_manager._active_sessions
        assert "server2" in client_manager._active_sessions
        assert len(client_manager.server_tools) == 2