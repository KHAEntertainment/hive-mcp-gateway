#!/usr/bin/env python3
"""
Test Hive MCP Gateway integration using any MCP-compatible client in headless mode

Works with Claude Code, Claude Desktop, Gemini CLI, and other MCP-compatible clients.
"""

import json
import subprocess
import tempfile
import time
from pathlib import Path
from rich.console import Console

console = Console()


def create_mcp_config():
    """Create temporary MCP configuration for testing"""
    config = {
        "mcpServers": {
            "hive-gateway": {
                "url": "http://localhost:8001/mcp"
            }
        }
    }
    
    // Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f, indent=2)
        config_path = f.name
    
    console.print(f"[green]Created MCP config at: {config_path}[/green]")
    console.print(json.dumps(config, indent=2))
    
    return config_path


def test_with_claude_cli(config_path: str):
    """Test using Claude CLI with MCP configuration"""
    
    // Test prompts to exercise Hive MCP Gateway
    test_prompts = [
        "List all registered MCP servers using the hive_gateway tools",
        "Use the discover_tools function to find tools for 'working with git repositories'",
        "Register a new MCP server called 'test-server' with command 'echo' and args ['hello']"
    ]
    
    for i, prompt in enumerate(test_prompts, 1):
        console.print(f"\n[bold cyan]Test {i}: {prompt}[/bold cyan]")
        
        try:
            // Run Claude with MCP config
            cmd = [
                "claude",
                "-p", prompt,
                "--mcp-config", config_path
            ]
            
            console.print(f"[yellow]Running: {' '.join(cmd)}[/yellow]")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                console.print("[green]✓ Success[/green]")
                console.print(result.stdout)
            else:
                console.print("[red]✗ Failed[/red]")
                console.print(f"Error: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            console.print("[red]✗ Timeout[/red]")
        except FileNotFoundError:
            console.print("[red]✗ Claude CLI not found[/red]")
            console.print("Install with: npm install -g @anthropic-ai/claude-cli")
            return
        except Exception as e:
            console.print(f"[red]✗ Error: {str(e)}[/red]")


def test_with_curl():
    """Test MCP endpoint directly with curl"""
    console.print("\n[bold cyan]Testing MCP endpoint directly[/bold cyan]")
    
    // Test if MCP endpoint is accessible
    try:
        result = subprocess.run(
            ["curl", "-s", "-I", "http://localhost:8001/mcp"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if "200 OK" in result.stdout or "text/event-stream" in result.stdout:
            console.print("[green]✓ MCP endpoint is accessible[/green]")
        else:
            console.print("[red]✗ MCP endpoint not responding correctly[/red]")
            console.print(result.stdout)
            
    except Exception as e:
        console.print(f"[red]✗ Error testing endpoint: {str(e)}[/red]")


def test_with_node_script():
    """Create and run a Node.js script to test MCP connection"""
    console.print("\n[bold cyan]Testing with Node.js MCP client[/bold cyan]")
    
    node_script = """
const { Client } = require('@modelcontextprotocol/sdk');
const { SSETransport } = require('@modelcontextprotocol/sdk/transport/sse');

async function testMCP() {
    console.log('Connecting to Hive MCP Gateway...');
    
    const transport = new SSETransport('http://localhost:8001/mcp');
    const client = new Client({
        transport,
        name: 'test-client',
        version: '1.0.0'
    });
    
    try {
        await client.connect();
        console.log('✓ Connected successfully');
        
        // List available tools
        const tools = await client.tools.list();
        console.log(`\\n✓ Found ${tools.tools.length} tools:`);
        tools.tools.forEach(tool => {
            console.log(`  - ${tool.name}: ${tool.description}`);
        });
        
        // Test discover_tools
        console.log('\\nTesting discover_tools...');
        const result = await client.tools.call({
            name: 'discover_tools',
            parameters: {
                query: 'git repository management',
                limit: 5
            }
        });
        console.log('✓ Discovery result:', JSON.stringify(result, null, 2));
        
    } catch (error) {
        console.error('✗ Error:', error.message);
    } finally {
        await client.close();
    }
}

testMCP().catch(console.error);
"""
    
    // Write script to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(node_script)
        script_path = f.name
    
    try:
        // Check if MCP SDK is installed
        check_result = subprocess.run(
            ["npm", "list", "@modelcontextprotocol/sdk"],
            capture_output=True,
            cwd=Path.home()
        )
        
        if check_result.returncode != 0:
            console.print("[yellow]Installing MCP SDK...[/yellow]")
            subprocess.run(
                ["npm", "install", "-g", "@modelcontextprotocol/sdk"],
                check=True
            )
        
        // Run the test script
        result = subprocess.run(
            ["node", script_path],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        console.print(result.stdout)
        if result.stderr:
            console.print(f"[red]Errors: {result.stderr}[/red]")
            
    except Exception as e:
        console.print(f"[red]✗ Error running Node.js test: {str(e)}[/red]")
    finally:
        Path(script_path).unlink(missing_ok=True)


def check_server_running():
    """Check if Hive MCP Gateway server is running"""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:8001/health"],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if result.returncode == 0 and "healthy" in result.stdout:
            console.print("[green]✓ Hive MCP Gateway server is running[/green]")
            return True
        else:
            console.print("[red]✗ Hive MCP Gateway server is not running[/red]")
            console.print("Start it with: hive-mcp-gateway")
            return False
    except:
        console.print("[red]✗ Cannot connect to Hive MCP Gateway server[/red]")
        return False


def main():
    """Run all tests"""
    console.print("[bold green]Hive MCP Gateway Integration Test[/bold green]\n")
    
    // Check server
    if not check_server_running():
        return
    
    // Test MCP endpoint
    test_with_curl()
    
    // Test with Node.js
    test_with_node_script()
    
    // Test with Claude CLI if available
    config_path = create_mcp_config()
    try:
        test_with_claude_cli(config_path)
    finally:
        Path(config_path).unlink(missing_ok=True)
    
    console.print("\n[bold green]Test complete![/bold green]")


if __name__ == "__main__":
    main()