# Hive MCP Gateway

Hive MCP Gateway is an intelligent system for managing Model Context Protocol (MCP) tools to prevent context bloat. It discovers and provisions only the most relevant tools for each task, supporting both stdio and HTTP-based MCP servers.

## Platform Support

**Currently Supported:**
- ✅ **macOS** - Full support with native .app bundle and DMG installer

**Coming Soon:**
- 🚧 **Windows** - Native .exe with installer (in development)
- 🚧 **Linux** - AppImage and DEB/RPM packages (in development)

The application is built with cross-platform compatibility in mind using PyQt6 and a universal codebase that adapts to each platform's conventions.

## Features

- **Unified Configuration**: Supports both YAML and JSON configuration formats
- **Multi-Protocol Support**: Works with stdio, SSE, and streamable HTTP MCP servers
- **Enhanced Security**: Built-in authentication support for bearer tokens and basic auth
- **Automatic Health Checks**: Continuous monitoring of server health and connectivity
- **Rich Metadata**: Server categorization, versioning, and tagging
- **Automatic Registration**: Multi-stage registration pipeline with fallback mechanisms
- **Comprehensive Error Handling**: Advanced error recovery and retry logic
- **Backward Compatibility**: Seamless migration from legacy JSON configurations

## Configuration

Hive MCP Gateway supports both YAML and JSON configuration formats. The new YAML format provides enhanced features including authentication, health checks, and metadata.

### YAML Configuration Example

```yaml
toolGating:
  port: 8001
  host: "0.0.0.0"
  logLevel: "info"
  autoDiscover: true
  maxTokensPerRequest: 2000
  maxToolsPerRequest: 10
  configWatchEnabled: true
  healthCheckInterval: 30
  connectionTimeout: 10

backendMcpServers:
  context7:
    type: "stdio"
    command: "npx"
    args: ["-y", "@upstash/context7-mcp@latest"]
    env: {}
    description: "Documentation search and library information"
    enabled: true
    authentication:
      type: "none"
    healthCheck:
      enabled: true
      interval: 60
    metadata:
      category: "documentation"
      version: "latest"
      tags: ["docs", "library", "search"]
    options:
      toolFilter:
        mode: "allow"
        list: []
      timeout: 30
      retryCount: 3
      batchSize: 1

  exa:
    type: "sse"
    url: "http://localhost:8002/exa"
    headers:
      Authorization: "Bearer ${EXA_API_KEY}"
    description: "Web search, research, and social media tools"
    enabled: true
    authentication:
      type: "bearer"
      token: "${EXA_API_KEY}"
    healthCheck:
      enabled: true
      interval: 45
      endpoint: "/health"
    metadata:
      category: "search"
      version: "1.0"
      tags: ["search", "research", "web"]
    options:
      toolFilter:
        mode: "allow"
        list:
          - "web_search_exa"
          - "research_paper_search"
          - "twitter_search"
      timeout: 45
      retryCount: 3
      batchSize: 10
```

### Configuration Schema

#### ToolGating Settings

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| port | integer | Port to listen on | 8001 |
| host | string | Host to bind to | "0.0.0.0" |
| logLevel | string | Logging level (debug, info, warning, error) | "info" |
| autoDiscover | boolean | Automatically discover tools | true |
| maxTokensPerRequest | integer | Maximum tokens per request | 2000 |
| maxToolsPerRequest | integer | Maximum tools per request | 10 |
| configWatchEnabled | boolean | Watch config file for changes | true |
| healthCheckInterval | integer | Health check interval in seconds | 30 |
| connectionTimeout | integer | Connection timeout in seconds | 10 |

#### Backend Server Configuration

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| type | string | Server type (stdio, sse, streamable-http) | Yes |
| command | string | Command to execute (stdio only) | For stdio |
| args | array | Command arguments (stdio only) | No |
| env | object | Environment variables (stdio only) | No |
| url | string | Server URL (HTTP only) | For HTTP |
| headers | object | HTTP headers (HTTP only) | No |
| description | string | Human-readable description | No |
| enabled | boolean | Whether server is enabled | No (default: true) |

#### Authentication Configuration

| Type | Fields | Description |
|------|--------|-------------|
| none | - | No authentication |
| bearer | token | Bearer token authentication |
| basic | username, password | Basic authentication |

#### Health Check Configuration

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| enabled | boolean | Enable health checks | true |
| interval | integer | Check interval in seconds | 60 |
| endpoint | string | Health check endpoint (HTTP only) | "/health" |
| timeout | integer | Check timeout in seconds | 10 |

#### Metadata Configuration

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| category | string | Server category | "unknown" |
| version | string | Server version | "unknown" |
| tags | array | Server tags | [] |

## Migration from JSON

To migrate from the legacy JSON format to the new YAML format with enhanced features:

```bash
python scripts/migrate_config_to_yaml.py hive_mcp_gateway_config.json config/hive_mcp_gateway_config.yaml --backup
```

This will:
1. Convert your existing JSON configuration to YAML
2. Add new fields for authentication, health checks, and metadata
3. Create a backup of your original configuration (if --backup is specified)

## Installation

### macOS (Current)

1. **Download the latest release:**
   ```bash
   # Download from GitHub releases or build from source
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Build the application:**
   ```bash
   ./build/build_macos.sh
   ```

### Windows (Coming Soon)

Windows support is in active development. The application will be available as:
- Native Windows executable (.exe)
- MSI installer package
- Chocolatey package

**Build Requirements (when available):**
- Python 3.12+
- uv package manager
- PyInstaller
- NSIS (for installer)

### Linux (Coming Soon)

Linux support is in active development. The application will be available as:
- AppImage (universal Linux binary)
- DEB packages (Debian/Ubuntu)
- RPM packages (Fedora/RHEL)
- AUR package (Arch Linux)

**Build Requirements (when available):**
- Python 3.12+
- uv package manager
- PyInstaller
- appimagetool
- fpm (for package creation)

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a configuration file (YAML or JSON):
   ```bash
   cp config/hive_mcp_gateway_config.yaml.example config/hive_mcp_gateway_config.yaml
   ```

3. Run the server:
   ```bash
   python -m hive_mcp_gateway
   ```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /api/tools` - List available tools
- `POST /api/proxy/execute` - Execute a tool
- `GET /api/mcp/servers` - List MCP servers
- `POST /api/mcp/servers` - Register a new MCP server

## Error Handling

Hive MCP Gateway includes comprehensive error handling with:
- Automatic retry with exponential backoff
- Circuit breaker pattern to prevent cascading failures
- Detailed error logging and reporting
- Graceful degradation when servers are unavailable

## Universal MCP Compatibility

Hive MCP Gateway is designed to work with **any MCP-compatible solution**, not just Claude Desktop. It serves as a universal proxy layer that can connect to any Model Context Protocol implementation.

### Key Benefits for All MCP Clients:
- **Context Optimization**: Reduces token usage by 50-90% by loading only relevant tools
- **Cross-Server Intelligence**: Seamlessly combines tools from multiple MCP servers
- **Dynamic Discovery**: Find tools using natural language queries
- **Flexible Integration**: Works with stdio, SSE, and HTTP-based MCP servers

### Special Note for Claude Code:
Claude Code in particular suffers from major context window bloat as you add numerous MCPs to its configuration. With Hive MCP Gateway, you can:
- Connect to a single endpoint instead of configuring dozens of individual MCP servers
- Dynamically load only the tools needed for each coding task
- Maintain optimal context space for your actual code and conversation
- Reduce startup time and memory usage

This makes Hive MCP Gateway especially valuable for Claude Code users who work with multiple MCP tools simultaneously.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a pull request

Note: Development artifacts, historical documents, and outdated files have been moved to the `.archive` directory to keep the repository clean. These files are not tracked by git but are kept for historical reference.

## License

MIT
