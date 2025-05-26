"""Proxy Service for routing tool execution to backend MCP servers"""

from typing import Dict, Any, Set, Optional, List

from ..models.tool import Tool
from .mcp_client_manager import MCPClientManager
from .repository import InMemoryToolRepository


class ProxyService:
    """Manages proxy operations for tool execution across MCP servers"""
    
    def __init__(
        self, 
        client_manager: MCPClientManager,
        tool_repository: InMemoryToolRepository
    ):
        self.client_manager = client_manager
        self.tool_repository = tool_repository
        self.provisioned_tools: Set[str] = set()
    
    async def discover_all_tools(self) -> None:
        """Discover and index tools from all connected servers"""
        for server_name, tools in self.client_manager.server_tools.items():
            for tool in tools:
                # Convert MCP tool to our Tool model
                tool_obj = Tool(
                    id=f"{server_name}_{tool.name}",
                    name=tool.name,
                    description=tool.description or "",
                    parameters=tool.inputSchema or {},
                    server=server_name,
                    tags=self._extract_tags(tool.description),
                    estimated_tokens=self._estimate_tokens(tool)
                )
                await self.tool_repository.add_tool(tool_obj)
    
    def provision_tool(self, tool_id: str) -> None:
        """Mark a tool as provisioned for use
        
        Args:
            tool_id: Tool identifier to provision
        """
        self.provisioned_tools.add(tool_id)
    
    def unprovision_tool(self, tool_id: str) -> None:
        """Remove a tool from provisioned set
        
        Args:
            tool_id: Tool identifier to unprovision
        """
        self.provisioned_tools.discard(tool_id)
    
    def is_provisioned(self, tool_id: str) -> bool:
        """Check if a tool is provisioned
        
        Args:
            tool_id: Tool identifier to check
            
        Returns:
            True if provisioned, False otherwise
        """
        return tool_id in self.provisioned_tools
    
    async def execute_tool(self, tool_id: str, arguments: dict) -> Any:
        """Execute a provisioned tool via proxy
        
        Args:
            tool_id: Tool identifier (format: "servername_toolname")
            arguments: Tool-specific arguments
            
        Returns:
            Result from tool execution
            
        Raises:
            ValueError: If tool not provisioned or invalid format
        """
        if not self.is_provisioned(tool_id):
            raise ValueError(f"Tool {tool_id} not provisioned. Use provision_tools first.")
        
        # Parse server and tool name from ID
        if '_' not in tool_id:
            raise ValueError(f"Invalid tool ID format: {tool_id}")
        
        # Split only on first underscore to handle tool names with underscores
        server_name, tool_name = tool_id.split('_', 1)
        
        # Execute via client manager
        return await self.client_manager.execute_tool(server_name, tool_name, arguments)
    
    def _extract_tags(self, description: Optional[str]) -> List[str]:
        """Extract tags from tool description
        
        Args:
            description: Tool description text
            
        Returns:
            List of extracted tags
        """
        if not description:
            return []
        
        # Simple tag extraction based on keywords
        tags = []
        keywords = ["search", "web", "browser", "file", "code", "api", "data"]
        desc_lower = description.lower()
        
        for keyword in keywords:
            if keyword in desc_lower:
                tags.append(keyword)
        
        # Add more specific tags based on common patterns
        if "screenshot" in desc_lower:
            tags.append("screenshot")
        if "navigate" in desc_lower or "navigation" in desc_lower:
            tags.append("navigation")
        if "read" in desc_lower:
            tags.append("read")
        if "write" in desc_lower:
            tags.append("write")
        if "documentation" in desc_lower or "docs" in desc_lower:
            tags.append("documentation")
        
        return list(set(tags))  # Remove duplicates
    
    def _estimate_tokens(self, tool: Any) -> int:
        """Estimate token count for a tool
        
        Args:
            tool: MCP tool object
            
        Returns:
            Estimated token count
        """
        # Simple estimation based on description and schema size
        desc_tokens = len(str(tool.description or "").split()) * 1.3
        schema_tokens = len(str(tool.inputSchema or {}).split()) * 1.3
        return int(desc_tokens + schema_tokens + 50)  # Base overhead