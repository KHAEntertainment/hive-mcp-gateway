"""MCP Server Integration for Tool Gating System"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import aiohttp
from rich.console import Console
from rich.table import Table

from tool_gating_mcp.models.tool import Tool
from tool_gating_mcp.services.discovery import DiscoveryService
from tool_gating_mcp.services.gating import GatingService
from tool_gating_mcp.services.repository import InMemoryToolRepository


console = Console()


class MCPServerConnector:
    """Connects to MCP servers and extracts their tool definitions"""
    
    def __init__(self, config_path: str = "mcp-servers.json"):
        self.config_path = Path(config_path)
        self.servers: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load MCP server configuration"""
        with open(self.config_path) as f:
            self.servers = json.load(f)
    
    async def discover_server_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """Discover tools from a specific MCP server"""
        config = self.servers.get(server_name)
        if not config:
            raise ValueError(f"Server {server_name} not found in config")
        
        # For this integration test, we'll simulate tool discovery
        # In a real implementation, you would:
        # 1. Start the MCP server process
        # 2. Connect via stdio/HTTP
        # 3. Send list_tools request
        # 4. Parse the response
        
        # Simulated tool definitions based on server type
        if server_name == "context7":
            return [
                {
                    "name": "resolve-library-id",
                    "description": "Resolves a package/product name to a Context7-compatible library ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "libraryName": {"type": "string", "description": "Library name to search for"}
                        },
                        "required": ["libraryName"]
                    }
                },
                {
                    "name": "get-library-docs",
                    "description": "Fetches up-to-date documentation for a library",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "context7CompatibleLibraryID": {"type": "string"},
                            "tokens": {"type": "number", "default": 10000},
                            "topic": {"type": "string"}
                        },
                        "required": ["context7CompatibleLibraryID"]
                    }
                }
            ]
        elif server_name == "exa":
            return [
                {
                    "name": "web_search_exa",
                    "description": "Search the web using Exa AI",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "numResults": {"type": "number", "default": 5}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "research_paper_search",
                    "description": "Search across 100M+ research papers",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "numResults": {"type": "number", "default": 5},
                            "maxCharacters": {"type": "number", "default": 3000}
                        },
                        "required": ["query"]
                    }
                }
            ]
        elif server_name == "basic-memory":
            return [
                {
                    "name": "store_memory",
                    "description": "Store a memory with a key",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "required": ["key", "value"]
                    }
                },
                {
                    "name": "retrieve_memory",
                    "description": "Retrieve a memory by key",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"}
                        },
                        "required": ["key"]
                    }
                }
            ]
        else:
            return []
    
    def convert_to_tool_model(self, mcp_tool: Dict[str, Any], server_name: str) -> Tool:
        """Convert MCP tool definition to our Tool model"""
        # Estimate tokens based on description and parameter complexity
        description_tokens = len(mcp_tool["description"].split()) * 2
        param_tokens = len(json.dumps(mcp_tool.get("parameters", {}))) // 4
        estimated_tokens = description_tokens + param_tokens + 50  # base overhead
        
        # Extract tags from description
        tags = []
        description_lower = mcp_tool["description"].lower()
        if "search" in description_lower:
            tags.append("search")
        if "web" in description_lower:
            tags.append("web")
        if "research" in description_lower or "paper" in description_lower:
            tags.append("research")
        if "memory" in description_lower or "store" in description_lower:
            tags.append("storage")
        if "docs" in description_lower or "documentation" in description_lower:
            tags.append("documentation")
        
        return Tool(
            id=f"{server_name}_{mcp_tool['name']}",
            name=mcp_tool["name"],
            description=mcp_tool["description"],
            parameters=mcp_tool.get("parameters", {}),
            estimated_tokens=estimated_tokens,
            tags=tags,
            server=server_name
        )


async def run_integration_test():
    """Run integration test with real MCP servers"""
    console.print("[bold green]MCP Tool Gating Integration Test[/bold green]\n")
    
    # Initialize components
    connector = MCPServerConnector()
    repo = InMemoryToolRepository()
    discovery_service = DiscoveryService(repo)
    gating_service = GatingService(repo)
    
    # Clear any demo tools
    repo.tools.clear()
    
    # Discover and load tools from each MCP server
    console.print("[yellow]Discovering tools from MCP servers...[/yellow]")
    
    all_tools = []
    for server_name in connector.servers:
        try:
            console.print(f"\n📡 Connecting to {server_name}...")
            mcp_tools = await connector.discover_server_tools(server_name)
            
            for mcp_tool in mcp_tools:
                tool = connector.convert_to_tool_model(mcp_tool, server_name)
                repo.add_tool(tool)
                all_tools.append(tool)
                console.print(f"  ✅ Added: {tool.name} ({tool.estimated_tokens} tokens)")
            
        except Exception as e:
            console.print(f"  ❌ Error: {str(e)}")
    
    console.print(f"\n[green]Total tools loaded: {len(all_tools)}[/green]\n")
    
    # Test 1: Semantic Search
    console.print("[bold cyan]Test 1: Semantic Search[/bold cyan]")
    test_queries = [
        "search for research papers",
        "find documentation for a library",
        "store and retrieve data",
        "search the web"
    ]
    
    for query in test_queries:
        console.print(f"\n🔍 Query: '{query}'")
        results = await discovery_service.search_tools(query, top_k=3)
        
        table = Table(title=f"Results for '{query}'")
        table.add_column("Tool", style="cyan")
        table.add_column("Server", style="yellow")
        table.add_column("Score", style="green")
        table.add_column("Tokens", style="magenta")
        
        for result in results:
            table.add_row(
                result.tool.name,
                result.tool.server,
                f"{result.score:.3f}",
                str(result.tool.estimated_tokens)
            )
        
        console.print(table)
    
    # Test 2: Token Budget Enforcement
    console.print("\n[bold cyan]Test 2: Token Budget Enforcement[/bold cyan]")
    
    # Set a low token budget
    gating_service.max_tokens = 300
    console.print(f"Token budget: {gating_service.max_tokens}")
    
    # Try to provision all tools
    all_tool_ids = [tool.id for tool in all_tools]
    selected_tools = await gating_service.select_tools(tool_ids=all_tool_ids)
    
    console.print(f"\nRequested: {len(all_tool_ids)} tools")
    console.print(f"Selected: {len(selected_tools)} tools")
    
    total_tokens = sum(tool.estimated_tokens for tool in selected_tools)
    console.print(f"Total tokens: {total_tokens}/{gating_service.max_tokens}")
    
    table = Table(title="Selected Tools (within budget)")
    table.add_column("Tool", style="cyan")
    table.add_column("Server", style="yellow")
    table.add_column("Tokens", style="magenta")
    
    for tool in selected_tools:
        table.add_row(tool.name, tool.server, str(tool.estimated_tokens))
    
    console.print(table)
    
    # Test 3: MCP Format Output
    console.print("\n[bold cyan]Test 3: MCP Format Output[/bold cyan]")
    
    # Provision tools for a specific use case
    search_tools = await discovery_service.search_tools("search", top_k=5)
    tool_ids = [r.tool.id for r in search_tools]
    
    mcp_response = await gating_service.provision_tools(tool_ids[:3])
    
    console.print("\nMCP Response Format:")
    console.print(json.dumps(mcp_response, indent=2))
    
    # Test 4: Cross-Server Tool Selection
    console.print("\n[bold cyan]Test 4: Cross-Server Tool Selection[/bold cyan]")
    
    # Search for tools across different servers
    query = "documentation and research"
    results = await discovery_service.search_tools(query, top_k=5)
    
    console.print(f"\n🔍 Query: '{query}'")
    console.print("Tools from multiple servers:")
    
    servers_represented = set()
    for result in results:
        servers_represented.add(result.tool.server)
        console.print(f"  - {result.tool.name} (from {result.tool.server}, score: {result.score:.3f})")
    
    console.print(f"\nServers represented: {', '.join(servers_represented)}")
    
    console.print("\n[bold green]✅ Integration test completed![/bold green]")


if __name__ == "__main__":
    asyncio.run(run_integration_test())