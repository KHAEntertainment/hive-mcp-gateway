#!/bin/bash
# Test MCP connection and debug issues

echo "🔍 Hive MCP Gateway Connection Test"
echo "==================================="

# 1. Check if server is running
echo -e "\n1. Checking Hive MCP Gateway server..."
if curl -s http://localhost:8001/health | grep -q "healthy"; then
    echo "✅ Server is running"
else
    echo "❌ Server is not running. Start with: hive-mcp-gateway"
    exit 1
fi

# 2. Check MCP endpoint
echo -e "\n2. Checking MCP endpoint..."
response=$(curl -s -I http://localhost:8001/mcp)
if echo "$response" | grep -q "200\|text/event-stream"; then
    echo "✅ MCP endpoint is accessible"
    echo "$response" | head -3
else
    echo "❌ MCP endpoint not responding"
    echo "$response"
fi

# 3. Check if mcp-proxy is installed
echo -e "\n3. Checking mcp-proxy installation..."
if command -v mcp-proxy &> /dev/null; then
    echo "✅ mcp-proxy is installed at: $(which mcp-proxy)"
else
    echo "❌ mcp-proxy not found in PATH"
    echo "Install with: uv tool install mcp-proxy"
    
    # Check common locations
    echo -e "\nChecking common locations:"
    locations=(
        "$HOME/.local/bin/mcp-proxy"
        "$HOME/.cargo/bin/mcp-proxy"
        "/usr/local/bin/mcp-proxy"
        "$HOME/Library/Application Support/uv/bin/mcp-proxy"
    )
    
    for loc in "${locations[@]}"; do
        if [ -f "$loc" ]; then
            echo "Found at: $loc"
            echo "Add to PATH or use full path in your MCP client config"
        fi
    done
fi

# 4. Test SSE connection
echo -e "\n4. Testing SSE connection..."
echo "Connecting to http://localhost:8001/mcp for 3 seconds..."
timeout 3 curl -s -N http://localhost:8001/mcp | head -20

# 5. Show MCP client config suggestion
echo -e "\n5. MCP Client Configuration"
echo "==========================="
echo "For any MCP-compatible client (Claude Desktop, Claude Code, Gemini CLI, etc.), use one of these configurations:"

echo -e "\nOption A: With mcp-proxy (if installed):"
cat << 'EOF'
{
  "mcpServers": {
    "hive-gateway": {
      "command": "mcp-proxy",
      "args": ["http://localhost:8001/mcp"]
    }
  }
}
EOF

echo -e "\nOption B: Direct URL (if your MCP client supports SSE):"
cat << 'EOF'
{
  "mcpServers": {
    "hive-gateway": {
      "url": "http://localhost:8001/mcp"
    }
  }
}
EOF

echo -e "\nOption C: With full path to mcp-proxy:"
if [ -f "$HOME/.local/bin/mcp-proxy" ]; then
    cat << EOF
{
  "mcpServers": {
    "hive-gateway": {
      "command": "$HOME/.local/bin/mcp-proxy",
      "args": ["http://localhost:8001/mcp"]
    }
  }
}
EOF
fi

echo -e "\n✅ Test complete!"