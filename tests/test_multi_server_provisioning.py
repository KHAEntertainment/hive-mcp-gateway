"""Tests for multi-server selective tool provisioning"""

import pytest
from tool_gating_mcp.models.tool import Tool
from tool_gating_mcp.services.discovery import DiscoveryService
from tool_gating_mcp.services.gating import GatingService
from tool_gating_mcp.services.repository import InMemoryToolRepository


@pytest.fixture
def multi_server_repository():
    """Create repository with tools from multiple MCP servers"""
    repo = InMemoryToolRepository()
    repo._tools.clear()  # Clear any demo tools
    
    # Add Exa server tools (7 total)
    exa_tools = [
        Tool(
            id="exa_web_search",
            name="web_search_exa",
            description="Search the web using Exa AI - performs real-time web searches",
            tags=["search", "web", "real-time"],
            estimated_tokens=180,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "numResults": {"type": "number", "default": 5}
                },
                "required": ["query"]
            },
            server="exa"
        ),
        Tool(
            id="exa_research_paper_search",
            name="research_paper_search",
            description="Search across 100M+ research papers with full text access",
            tags=["search", "research", "academic", "papers"],
            estimated_tokens=250,
            server="exa"
        ),
        Tool(
            id="exa_twitter_search",
            name="twitter_search",
            description="Search Twitter/X.com posts and accounts",
            tags=["search", "social", "twitter"],
            estimated_tokens=180,
            server="exa"
        ),
        Tool(
            id="exa_company_research",
            name="company_research",
            description="Research companies using targeted searches",
            tags=["search", "company", "business"],
            estimated_tokens=220,
            server="exa"
        ),
        Tool(
            id="exa_crawling",
            name="crawling",
            description="Extract content from specific URLs",
            tags=["crawl", "extract", "web"],
            estimated_tokens=200,
            server="exa"
        ),
        Tool(
            id="exa_competitor_finder",
            name="competitor_finder",
            description="Find competitors of a company",
            tags=["search", "competitor", "business"],
            estimated_tokens=210,
            server="exa"
        ),
        Tool(
            id="exa_linkedin_search",
            name="linkedin_search",
            description="Search LinkedIn for companies",
            tags=["search", "linkedin", "professional"],
            estimated_tokens=190,
            server="exa"
        )
    ]
    
    # Add Desktop Commander tools (subset of 18)
    desktop_tools = [
        Tool(
            id="desktop_file_write",
            name="file_write",
            description="Write content to a file on the desktop",
            tags=["file", "write", "save", "desktop"],
            estimated_tokens=150,
            server="desktop-commander"
        ),
        Tool(
            id="desktop_file_read",
            name="file_read",
            description="Read content from a file on the desktop",
            tags=["file", "read", "load", "desktop"],
            estimated_tokens=120,
            server="desktop-commander"
        ),
        Tool(
            id="desktop_screenshot",
            name="take_screenshot",
            description="Take a screenshot of the desktop or window",
            tags=["screenshot", "capture", "desktop"],
            estimated_tokens=130,
            server="desktop-commander"
        ),
        Tool(
            id="desktop_execute_command",
            name="execute_command",
            description="Execute a system command",
            tags=["command", "execute", "system"],
            estimated_tokens=160,
            server="desktop-commander"
        ),
        Tool(
            id="desktop_open_application",
            name="open_application",
            description="Open an application on the desktop",
            tags=["application", "open", "launch"],
            estimated_tokens=110,
            server="desktop-commander"
        )
    ]
    
    # Add Context7 tools
    context7_tools = [
        Tool(
            id="context7_resolve_library",
            name="resolve-library-id",
            description="Resolves a package name to a Context7-compatible library ID",
            tags=["documentation", "library", "search"],
            estimated_tokens=150,
            server="context7"
        ),
        Tool(
            id="context7_get_docs",
            name="get-library-docs",
            description="Fetches up-to-date documentation for a library",
            tags=["documentation", "library", "fetch"],
            estimated_tokens=200,
            server="context7"
        )
    ]
    
    # Add Basic Memory tools
    memory_tools = [
        Tool(
            id="memory_store",
            name="store_memory",
            description="Store a memory with a key-value pair",
            tags=["storage", "memory", "save"],
            estimated_tokens=100,
            server="basic-memory"
        ),
        Tool(
            id="memory_retrieve",
            name="retrieve_memory",
            description="Retrieve a stored memory by key",
            tags=["storage", "memory", "load"],
            estimated_tokens=80,
            server="basic-memory"
        )
    ]
    
    # Add all tools to repository
    for tool in exa_tools + desktop_tools + context7_tools + memory_tools:
        repo.add_tool(tool)
    
    return repo


class TestMultiServerProvisioning:
    """Test selective provisioning across multiple MCP servers"""
    
    def test_total_tools_count(self, multi_server_repository):
        """Verify we have tools from all servers"""
        tools = multi_server_repository.list_all_tools()
        
        # Count tools by server
        server_counts = {}
        for tool in tools:
            server = tool.server or "unknown"
            server_counts[server] = server_counts.get(server, 0) + 1
        
        assert server_counts["exa"] == 7
        assert server_counts["desktop-commander"] == 5
        assert server_counts["context7"] == 2
        assert server_counts["basic-memory"] == 2
        assert len(tools) == 16
    
    @pytest.mark.asyncio
    async def test_selective_search_provisioning(self, multi_server_repository):
        """Test provisioning only search tools from specific servers"""
        discovery = DiscoveryService(multi_server_repository)
        
        # Search for "research papers"
        results = await discovery.search_tools("research papers", top_k=10)
        
        # Should find research paper tool from Exa as top result
        assert results[0].tool.id == "exa_research_paper_search"
        assert results[0].tool.server == "exa"
        assert results[0].score > 0.5  # Realistic semantic similarity score
        
        # Should also find other search tools but with lower scores
        search_tools = [r for r in results if "search" in r.tool.tags]
        assert len(search_tools) >= 3
    
    @pytest.mark.asyncio
    async def test_cross_server_provisioning(self, multi_server_repository):
        """Test provisioning tools from different servers for a task"""
        discovery = DiscoveryService(multi_server_repository)
        gating = GatingService(multi_server_repository)
        
        # Query: "search for documentation and save to file"
        search_results = await discovery.search_tools(
            "search for documentation and save to file", 
            top_k=10
        )
        
        # Get tool IDs from search results
        tool_ids = [r.tool.id for r in search_results[:5]]
        
        # Provision with token budget
        gating.max_tokens = 400  # Limited budget
        selected_tools = await gating.select_tools(tool_ids=tool_ids)
        
        # Should get tools from multiple servers
        servers = {tool.server for tool in selected_tools}
        assert len(servers) >= 2  # At least 2 different servers
        
        # Should include both search and file tools
        tool_names = {tool.name for tool in selected_tools}
        assert any("docs" in name or "documentation" in t.description 
                  for t in selected_tools for name in [t.name])
        assert any("file" in t.name or "write" in t.name 
                  for t in selected_tools)
    
    @pytest.mark.asyncio
    async def test_token_budget_limits_tools(self, multi_server_repository):
        """Test that token budget prevents loading all tools"""
        gating = GatingService(multi_server_repository)
        
        # Get all tool IDs
        all_tools = multi_server_repository.list_all_tools()
        all_tool_ids = [t.id for t in all_tools]
        
        # Calculate total tokens if all tools were loaded
        total_possible_tokens = sum(t.estimated_tokens for t in all_tools)
        assert total_possible_tokens > 2000  # Much more than default budget
        
        # Try to provision all tools with default budget
        selected_tools = await gating.select_tools(tool_ids=all_tool_ids)
        
        # Should get fewer tools due to budget
        assert len(selected_tools) < len(all_tools)
        
        # Total tokens should be within budget
        total_tokens = sum(t.estimated_tokens for t in selected_tools)
        assert total_tokens <= gating.max_tokens
    
    @pytest.mark.asyncio
    async def test_specific_server_filtering(self, multi_server_repository):
        """Test getting tools from specific servers only"""
        discovery = DiscoveryService(multi_server_repository)
        
        # Search for tools with exa-specific functionality
        results = await discovery.search_tools("twitter linkedin social", top_k=5)
        
        # Should prioritize Exa social search tools
        exa_results = [r for r in results if r.tool.server == "exa"]
        assert len(exa_results) >= 2
        assert any("twitter" in r.tool.name for r in exa_results)
        assert any("linkedin" in r.tool.name for r in exa_results)
    
    @pytest.mark.asyncio
    async def test_no_context_bloat(self, multi_server_repository):
        """Verify selective provisioning prevents context bloat"""
        discovery = DiscoveryService(multi_server_repository)
        gating = GatingService(multi_server_repository)
        
        # Specific task: "find research papers on AI"
        search_results = await discovery.search_tools(
            "find research papers on AI", 
            top_k=3
        )
        
        # Provision only the top results
        tool_ids = [r.tool.id for r in search_results]
        selected_tools = await gating.select_tools(tool_ids=tool_ids)
        
        # Should get 1-3 highly relevant tools, not all 16
        assert 1 <= len(selected_tools) <= 3
        
        # Should primarily be research/search tools
        assert all("search" in t.tags or "research" in t.tags 
                  for t in selected_tools)
        
        # Token usage should be minimal
        total_tokens = sum(t.estimated_tokens for t in selected_tools)
        assert total_tokens < 800  # Much less than loading all tools (would be 2000+)
    
    @pytest.mark.asyncio
    async def test_tag_based_server_selection(self, multi_server_repository):
        """Test that tags help select appropriate servers"""
        discovery = DiscoveryService(multi_server_repository)
        
        # Search with specific tags
        results = await discovery.search_tools(
            "save data", 
            tags=["storage", "memory"],
            top_k=5
        )
        
        # Should prioritize memory tools
        memory_results = [r for r in results 
                         if r.tool.server == "basic-memory"]
        assert len(memory_results) >= 1
        assert memory_results[0].score > 0.7
    
    def test_mcp_format_includes_server(self, multi_server_repository):
        """Test that MCP format includes server information"""
        gating = GatingService(multi_server_repository)
        
        # Get a tool from a specific server
        tool = multi_server_repository.get_tool("exa_web_search")
        assert tool is not None
        
        # Format for MCP
        mcp_tools = gating._format_tools_for_mcp([tool])
        
        # Verify format
        assert len(mcp_tools) == 1
        mcp_tool = mcp_tools[0]
        assert mcp_tool.name == "web_search_exa"
        assert mcp_tool.description == tool.description
        assert mcp_tool.inputSchema == tool.parameters


class TestTokenBudgetScenarios:
    """Test various token budget scenarios"""
    
    @pytest.mark.asyncio
    async def test_very_low_budget(self, multi_server_repository):
        """Test with very restrictive token budget"""
        gating = GatingService(multi_server_repository)
        gating.max_tokens = 100  # Very low
        
        all_tool_ids = [t.id for t in multi_server_repository.list_all_tools()]
        selected = await gating.select_tools(tool_ids=all_tool_ids)
        
        # Should get at most 1 tool
        assert len(selected) <= 1
        if selected:
            assert selected[0].estimated_tokens <= 100
    
    @pytest.mark.asyncio
    async def test_medium_budget_optimization(self, multi_server_repository):
        """Test optimal selection with medium budget"""
        discovery = DiscoveryService(multi_server_repository)
        gating = GatingService(multi_server_repository)
        gating.max_tokens = 500  # Medium budget
        
        # Complex query needing multiple tools
        results = await discovery.search_tools(
            "research companies save findings to file memory storage",
            top_k=10
        )
        
        tool_ids = [r.tool.id for r in results]
        selected = await gating.select_tools(tool_ids=tool_ids)
        
        # Should get 2-3 tools from different servers
        assert 2 <= len(selected) <= 4
        
        # Should have diverse functionality
        servers = {t.server for t in selected}
        assert len(servers) >= 2
        
        # Total should be within budget
        total = sum(t.estimated_tokens for t in selected)
        assert total <= 500
    
    @pytest.mark.asyncio
    async def test_unlimited_budget_still_filters(self, multi_server_repository):
        """Test that even with high budget, we filter by relevance"""
        discovery = DiscoveryService(multi_server_repository)
        gating = GatingService(multi_server_repository)
        gating.max_tokens = 10000  # Very high budget
        
        # Specific query
        results = await discovery.search_tools("take screenshot", top_k=3)
        tool_ids = [r.tool.id for r in results]
        
        selected = await gating.select_tools(tool_ids=tool_ids, max_tools=3)
        
        # Should still limit to requested tools, not all
        assert len(selected) <= 3
        assert any("screenshot" in t.name for t in selected)