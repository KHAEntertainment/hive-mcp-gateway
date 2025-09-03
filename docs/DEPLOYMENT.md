# Hive MCP Gateway - Deployment and Migration Guide

## Overview

This guide covers the deployment and migration process for the improved Hive MCP Gateway system with JSON configuration, PyQt6 GUI, and native macOS app bundle support. Hive MCP Gateway works with any MCP-compatible client, including Claude Desktop, Claude Code, Gemini CLI, Kiro, and other agentic coding systems.

## Table of Contents

1. [Migration from Existing Installation](#migration-from-existing-installation)
2. [Native macOS Deployment](#native-macos-deployment)
3. [Docker Deployment](#docker-deployment)
4. [Development Setup](#development-setup)
5. [Configuration Management](#configuration-management)
6. [Troubleshooting](#troubleshooting)

## Migration from Existing Installation

### Prerequisites

- Existing Hive MCP Gateway installation at `/Users/bbrenner/hive-mcp-gateway`
- Python 3.12+
- uv package manager
- PyQt6 (for GUI functionality)

### Step 1: Install New Implementation

```bash
# Clone or navigate to the new implementation
cd /path/to/new/hive-mcp-gateway

# Install dependencies
uv sync

# Install additional GUI dependencies
uv add pyinstaller  # For app bundle creation
```

### Step 2: Migrate Configuration

The system includes an automated migration utility:

```bash
# Run migration to import existing servers
python -c "
from src.hive_mcp_gateway.services.config_manager import ConfigManager
from src.hive_mcp_gateway.services.migration_utility import MigrationUtility

config_manager = ConfigManager('hive_mcp_gateway_config.json')
migration = MigrationUtility(config_manager)

# Migrate all servers
result = migration.migrate_from_existing_installation()
print(f'Migration result: {result}')

# Or migrate only large servers (exa, puppeteer)
large_result = migration.migrate_large_servers_only()
print(f'Large servers migration: {large_result}')
"
```

### Step 3: Verify Configuration

Check the generated `hive_mcp_gateway_config.json`:

```bash
cat hive_mcp_gateway_config.json
```

The configuration should include your migrated servers with the new format:

```json
{
  "toolGating": {
    "port": 8001,  // Non-interfering port
    "host": "0.0.0.0",
    "logLevel": "info",
    "autoDiscover": true
  },
  "backendMcpServers": {
    "exa": {
      "type": "stdio",
      "command": "exa-mcp-server",
      "args": ["--tools=web_search_exa,research_paper_search,..."],
      "env": {"EXA_API_KEY": "${EXA_API_KEY}"},
      "description": "Web search, research, and social media tools",
      "enabled": true
    }
    // ... other migrated servers
  }
}
```

### Step 4: Side-by-Side Testing

Run the new implementation alongside your existing one:

```bash
# Start new implementation (uses port 8001)
python src/hive_mcp_gateway/main.py

# Verify it's running
curl http://localhost:8001/health

# Your existing implementation continues on port 8000
curl http://localhost:8000/health
```

## Universal MCP Client Support

Hive MCP Gateway works with **any MCP-compatible client**, including but not limited to:
- Claude Desktop
- Claude Code
- Gemini CLI
- Kiro
- Other agentic coding systems

### Special Benefits for Claude Code

Claude Code in particular suffers from major context window bloat as you add numerous MCPs to its configuration. With Hive MCP Gateway, you can:

1. **Reduce Context Bloat**: Instead of loading 50+ tools that consume thousands of tokens, load only the 3-5 tools you actually need
2. **Improve Performance**: Faster startup times and more responsive interactions
3. **Better Resource Management**: Less memory usage and reduced computational overhead
4. **Dynamic Tool Loading**: Load different tools for different coding tasks without reconfiguring your client

## Native macOS Deployment

### Building the App Bundle

1. **Create the App Bundle:**

```bash
python build/macos_bundle.py
```

2. **Code Signing (Optional but Recommended):**

Edit `build/sign_and_notarize.sh` with your Apple Developer credentials:

```bash
# Update these variables in the script
DEVELOPER_ID_APP="Developer ID Application: Your Name (TEAM_ID)"
APPLE_ID="your-apple-id@example.com"
TEAM_ID="YOUR_TEAM_ID"
APP_PASSWORD="@keychain:AC_PASSWORD"
```

Then run:

```bash
./build/sign_and_notarize.sh
```

3. **Install the App:**

```bash
# Copy to Applications folder
cp -r dist/HiveMCPGateway.app /Applications/

# Or create installer DMG
python build/macos_bundle.py --dmg
```

### Key Features

- **Menu Bar Only:** App runs in menu bar without dock icon (LSUIElement)
- **Auto-Start:** Configurable system startup via Launch Agents
- **Native Notifications:** System tray notifications for status changes
- **Dependency Monitoring:** Automatic mcp-proxy status checking

### GUI Usage

1. **Launch the app** from Applications or via terminal:
```bash
/Applications/HiveMCPGateway.app/Contents/MacOS/HiveMCPGateway
```

2. **Menu Bar Controls:**
   - Right-click menu bar icon for service controls
   - Start/Stop/Restart backend service
   - Open configuration editor
   - View logs and status

3. **Configuration Editor:**
   - Visual JSON editing with syntax highlighting
   - Server management (add/edit/remove)
   - Real-time validation

4. **MCP Snippet Processor:**
   - Paste MCP JSON snippets for instant registration
   - Supports both mcp-proxy and direct formats
   - Automatic server detection and conversion

## Docker Deployment (Headless)

### Quick Start

Docker is intended for running the headless/server gateway. For the GUI, use the native macOS application bundle.

```bash
# Production deployment
docker compose -f docker/docker-compose.yml up --build -d

# Development with live reload
docker compose -f docker/docker-compose.yml --profile development up

# GUI in Docker is disabled/untested; use the native app for GUI
# To experiment, see comments in docker/Dockerfile and docker/docker-compose.yml (PRs welcome)
```

### Configuration

1. **Environment Variables:**

Create `.env` file:

```env
EXA_API_KEY=your_exa_api_key_here
LOG_LEVEL=info
HOST=0.0.0.0
```

HOST=0.0.0.0
PORT=8001
```

2. **Volume Persistence:**

Configuration and logs are persisted in Docker volumes:
- `hive-mcp-gateway-config`: Configuration files
- `hive-mcp-gateway-logs`: Application logs
- `hive-mcp-gateway-data`: Application data

3. **Custom Configuration:**

Mount your own config file:

```yaml
volumes:
  - ./my-config.json:/app/hive_mcp_gateway_config.json:ro

### Pinning Node MCP Server Versions

To ensure reproducible builds, you can pin the Node-based MCP servers used in the image.

Build with explicit versions using build args:

```bash
docker compose -f docker/docker-compose.yml build \
  --build-arg PUPPETEER_MCP_VERSION=@modelcontextprotocol/server-puppeteer@0.7.2 \
  --build-arg CONTEXT7_MCP_VERSION=@upstash/context7-mcp@0.2.2
```

Notes:
- Defaults are set to `@latest` for both packages in `docker/Dockerfile`.
- Adjust versions as needed to match your environment and compatibility.
```

## MCP Transport Note

Hive MCP Gateway exposes an HTTP MCP endpoint at `/mcp`. External `mcp-proxy` is not required for clients that can connect over HTTP. Use `mcp-proxy` only for clients that require stdio (e.g., certain desktop IDE integrations).

## Development Setup

### Local Development

```bash
# Install in development mode
uv sync
uv pip install -e .

# Run with live reload
uvicorn hive_mcp_gateway.main:app --reload --port 8001

# Run GUI for testing
python gui/main_app.py
```

### Testing the Configuration System

```bash
# Test configuration loading
python -c "
from src.hive_mcp_gateway.services.config_manager import ConfigManager
cm = ConfigManager()
config = cm.load_config()
print('Config loaded successfully:', config.tool_gating.port)
"

# Test file watching
python -c "
import asyncio
from src.hive_mcp_gateway.services.config_manager import ConfigManager
from src.hive_mcp_gateway.services.file_watcher import FileWatcherService

async def test_watcher():
    cm = ConfigManager()
    fw = FileWatcherService(cm, None)
    await fw.start_watching()
    print('File watcher started - edit hive_mcp_gateway_config.json to test')
    await asyncio.sleep(30)
    await fw.stop_watching()

asyncio.run(test_watcher())
"
```

## Configuration Management

### JSON Configuration Format

The new system uses a structured JSON configuration:

```json
{
  "toolGating": {
    "port": 8001,
    "host": "0.0.0.0", 
    "logLevel": "info",
    "autoDiscover": true,
    "maxTokensPerRequest": 2000,
    "maxToolsPerRequest": 10,
    "configWatchEnabled": true
  },
  "backendMcpServers": {
    "server_name": {
      "type": "stdio|sse|streamable-http",
      "command": "command_to_run",
      "args": ["arg1", "arg2"],
      "env": {"VAR": "value"},
      "description": "Server description",
      "enabled": true,
      "options": {
        "toolFilter": {
          "mode": "allow|deny",
          "list": ["tool1", "tool2"]
        },
        "timeout": 30,
        "retryCount": 3
      }
    }
  }
}
```

### Environment Variable Substitution

Use `${VARIABLE_NAME}` syntax for environment variables:

```json
{
  "env": {
    "API_KEY": "${MY_API_KEY}",
    "DEBUG": "${DEBUG:-false}"
  }
}
```

### Dynamic Configuration Updates

The system watches for configuration file changes and automatically:
- Reloads server configurations
- Connects/disconnects servers as needed
- Updates tool discovery
- Maintains existing connections when unchanged

## Troubleshooting

### Common Issues

1. **Port Conflicts:**
   ```bash
   # Check what's using port 8001
   lsof -i :8001
   
   # Change port in config
   jq '.toolGating.port = 8002' hive_mcp_gateway_config.json > tmp.json && mv tmp.json hive_mcp_gateway_config.json
   ```

2. **mcp-proxy Not Found (only if using stdio bridging):**
   ```bash
   # Check mcp-proxy status
   ps aux | grep mcp-proxy
   
   # Start mcp-proxy if needed (from your existing installation)
   cd /Users/bbrenner/hive-mcp-gateway
   ./mcp-proxy
   ```

3. **GUI Issues on macOS:**
   ```bash
   # If app won't start, check permissions
   xattr -d com.apple.quarantine /Applications/HiveMCPGateway.app
   
   # For development, run with debug output
   python gui/main_app.py --debug
   ```

4. **Configuration Validation Errors:**
   ```bash
   # Validate configuration manually
   python -c "
   from src.hive_mcp_gateway.services.config_manager import ConfigManager
   import json
   
   cm = ConfigManager()
   with open('hive_mcp_gateway_config.json') as f:
       data = json.load(f)
   
   result = cm.validate_config(data)
   print('Valid:', result.is_valid)
   print('Errors:', result.errors)
   print('Warnings:', result.warnings)
   "
   ```

### Logs and Debugging

- **Application Logs:** Check `logs/` directory or Docker volumes
- **System Logs:** `tail -f /var/log/system.log` (macOS)
- **GUI Logs:** Run GUI from terminal to see debug output
- **Configuration Validation:** Use built-in validation in config editor

### Migration Issues

If migration fails or servers don't work:

1. **Manual Configuration:**
   - Copy server configurations manually from your existing `config.py`
   - Use the GUI's "Add Server" feature
   - Test each server individually

2. **Environment Variables:**
   - Ensure API keys are properly set
   - Check `.env` file or export variables
   - Verify `${VAR}` substitution syntax

3. **Server Compatibility:**
   - Some servers may need updated commands
   - Check server documentation for latest installation methods
   - Test servers individually outside Hive MCP Gateway

## Next Steps

After successful deployment:

1. **Enable Auto-Start:** Use GUI to configure Launch Agent for system startup
2. **Monitor Performance:** Check logs and system resources
3. **Customize Configuration:** Add/remove servers as needed
4. **Backup Configuration:** Store `hive_mcp_gateway_config.json` in version control
5. **Update Dependencies:** Keep MCP servers and Hive MCP Gateway updated

For additional support, check the project documentation and GitHub issues.
