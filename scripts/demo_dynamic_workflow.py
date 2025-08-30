#!/usr/bin/env python3
"""
Demonstrate the Hive MCP Gateway workflow:
1. Claude starts with ONLY Hive MCP Gateway
2. Claude uses Hive MCP Gateway to discover what tools are available
3. Claude gets tool definitions from Hive MCP Gateway
4. Claude uses those tool definitions to call the actual MCP servers

This avoids loading all MCP servers and their tools into Claude's context at startup.
Works with any MCP-compatible client including Claude Desktop, Claude Code, Gemini CLI, etc.
"""

import json
import subprocess
import tempfile
from pathlib import Path
import asyncio
import httpx

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def create_claude_config_with_hive_only() -> Path:
    """Create config with ONLY Hive MCP Gateway - no other MCP servers."""
    config = {
        "mcpServers": {
            "hive-gateway": {
                "command": "mcp-proxy",
                "args": ["http://localhost:8001/mcp"],
                "env": {}
            }
        }
    }
    
    config_file = Path(tempfile.mktemp(suffix="_hive_only.json"))
    config_file.write_text(json.dumps(config, indent=2))
    return config_file


def demonstrate_workflow():
    """Show the complete Hive MCP Gateway workflow."""
    console.print(Panel.fit(
        "[bold green]Hive MCP Gateway Dynamic Workflow Demo[/bold green]\n\n"
        "This demonstrates how MCP clients can:\n"
        "1. Start with ONLY Hive MCP Gateway\n"
        "2. Discover tools dynamically based on needs\n"
        "3. Get tool definitions without loading all MCP servers"
    ))
    
    // Create config with only Hive MCP Gateway
    config_file = create_claude_config_with_hive_only()
    console.print(f"\n[cyan]Created Claude config with ONLY Hive MCP Gateway:[/cyan]")
    console.print(json.dumps(json.loads(config_file.read_text()), indent=2))
    
    // Test 1: Show available tools at startup
    console.print("\n[bold yellow]Test 1: What tools does the MCP client have at startup?[/bold yellow]")
    cmd1 = [
        "claude", "-p",
        "List all the MCP tools you currently have access to. Just list their names.",
        "--mcp-config", str(config_file),
        "--allowedTools", "*",
        "--max-turns", "1"
    ]
    
    result1 = subprocess.run(cmd1, capture_output=True, text=True)
    console.print("[green]MCP client's response:[/green]")
    console.print(result1.stdout or result1.stderr)
    
    // Test 2: Use Hive MCP Gateway to discover tools
    console.print("\n[bold yellow]Test 2: Using Hive MCP Gateway to discover web search tools[/bold yellow]")
    cmd2 = [
        "claude", "-p",
        "Use the hive-gateway discover_tools to find tools for 'web search research papers'. List what you find.",
        "--mcp-config", str(config_file),
        "--allowedTools", "mcp__hive-gateway__discover_tools",
        "--max-turns", "2"
    ]
    
    result2 = subprocess.run(cmd2, capture_output=True, text=True)
    console.print("[green]MCP client's response:[/green]")
    console.print(result2.stdout or result2.stderr)
    
    // Test 3: Use Hive MCP Gateway to provision tools
    console.print("\n[bold yellow]Test 3: Using Hive MCP Gateway to provision specific tools[/bold yellow]")
    cmd3 = [
        "claude", "-p",
        "Use hive-gateway provision_tools to load the exa research paper search tool if available.",
        "--mcp-config", str(config_file),
        "--allowedTools", "mcp__hive-gateway__provision_tools",
        "--max-turns", "2"
    ]
    
    result3 = subprocess.run(cmd3, capture_output=True, text=True)
    console.print("[green]MCP client's response:[/green]")
    console.print(result3.stdout or result3.stderr)
    
    // Compare approaches
    console.print("\n[bold red]Compare: What if we loaded ALL MCP servers directly?[/bold red]")
    
    table = Table(title="Context Usage Comparison")
    table.add_column("Approach", style="cyan")
    table.add_column("Tools Loaded", style="yellow")
    table.add_column("Context Tokens", style="red")
    
    table.add_row(
        "Hive MCP Gateway Only",
        "~6 tools (hive-gateway functions)",
        "~500 tokens"
    )
    table.add_row(
        "All MCP Servers",
        "100+ tools (all servers)",
        "~10,000+ tokens"
    )
    
    console.print(table)
    
    // Cleanup
    config_file.unlink()
    
    console.print("\n[bold green]Key Insight:[/bold green]")
    console.print("With Hive MCP Gateway, MCP clients can discover and get definitions for ANY tool")
    console.print("from ANY registered MCP server, but only loads what's needed for the task!")
    console.print("\n[yellow]Note:[/yellow] To actually execute the discovered tools, you would need to:")
    console.print("1. Use the MCP connector in the Messages API (for programmatic use)")
    console.print("2. Or temporarily add the specific MCP server to your MCP client's config")


async def main():
    // First ensure we have tools registered
    await ensure_tools_registered()
    
    // Then run the demonstration
    demonstrate_workflow()


if __name__ == "__main__":
    asyncio.run(main())