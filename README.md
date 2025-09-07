# Hive MCP Gateway

> ⚠️ **CRITICAL REQUIREMENT:** This project requires **TBXark/mcp-proxy** (NOT the Anthropic mcp-proxy)!  
> - **Docker (Recommended):** `docker pull ghcr.io/tbxark/mcp-proxy:latest`
> - **GitHub:** https://github.com/TBXark/mcp-proxy
> - **Important:** Do NOT use `uv tool install mcp-proxy` - that installs the wrong proxy!
> - See [docs/CRITICAL_PROXY_DISCOVERY.md](docs/CRITICAL_PROXY_DISCOVERY.md) for the 3-day debugging story

Hive MCP Gateway is an intelligent system for managing Model Context Protocol (MCP) tools to prevent context bloat. It discovers and uses only the most relevant tools for a given task.

This project is designed for end users first: start the app, connect your MCP clients (Claude Desktop/Code, Gemini CLI), and work. Advanced configuration remains available for power users and headless/Docker setups.

## Docs
- Full docs live under `docs/` to keep the root clean:
  - `docs/ARCHITECTURE.md` – System design and components
  - `docs/USAGE.md` – Usage and configuration guide
  - `docs/TOOL_ENUMERATION.md` – Deterministic vs LLM-assisted enumeration
  - `docs/BUILD.md` – macOS build instructions
  - `docs/DEPLOYMENT.md` – Deployment (including Docker headless)
  - `docs/ROADMAP.md` – Roadmap and plans
  - `docs/TASKS.md` – Near-term tasks and TODOs
  - `docs/CLAUDE_INTEGRATION.md` – Claude-specific integration notes
  - `docs/tool-gating-mcp-troubleshooting-notes.md` – Troubleshooting notes

Docker assets and guidance are under `docker/` (headless use; GUI is native-only).

## Getting Started (GUI First)

1) Install dependencies
- `uv sync`

2) Launch the app
- macOS (built app): open the Hive MCP Gateway app (or run `Launch_Hive_MCP_Gateway.command`)
- Dev mode: `uv run python run_gui.py`

3) Point your MCP client to the gateway
- Claude Desktop/Code: Configure a single MCP server pointed at `http://localhost:8001/mcp`
- Gemini CLI: Use the Client Configuration helper in the app

4) Start using tools
- Use “Add MCP Server” to register backends (Puppeteer, Context7, GitHub MCP, etc.)
- Discover tools with natural language; execute via the gateway proxy

Screenshots (placeholders; replace when ready):
- Main window: `docs/images/gui_home_placeholder.png`
- MCP clients tab: `docs/images/gui_clients_placeholder.png`
- Add server flow: `docs/images/gui_add_server_placeholder.png`
- Logs view: `docs/images/gui_logs_placeholder.png`

Tip: The LLM configuration UI is optional and hidden by default. Enable it with `HMG_ENABLE_LLM_UI=1` if you want to configure providers for future features; it’s not needed for core functionality.

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
- **Optional LLM Integration (Disabled by Default)**: Provider configuration UI exists for future sampling/re-ranking, but the internal LLM is not used for tool selection in the current build. Enable the UI with `HMG_ENABLE_LLM_UI=1`.

## Configuration (Advanced / Optional)

Most users can ignore this section. The app works out of the box via the GUI. For headless deployments or power users, Hive MCP Gateway supports both YAML and JSON configuration formats. The YAML format provides enhanced features including authentication, health checks, and metadata.

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

## Usage (CLI / Headless)

For server-only or Docker deployments:
1. Prepare your configuration file (YAML/JSON) as needed.
2. Run the API + MCP endpoint: `uv run hive-mcp-gateway` or `uv run python -m hive_mcp_gateway.main`

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

## Roadmap (Short)

- Core stabilization: Validate deterministic enumeration and proxy execution end-to-end (no LLM). Add/verify tests and docs, ensure per-server `toolFilter` enforcement, and consider optional provisioning checks.
- LLM-assisted enumeration (flagged): Introduce a feature flag (`HMG_ENABLE_LLM_ENUM=1`) to route `add_server` through LLM-assisted tool enumeration with automatic fallback to deterministic mode; A/B test and measure value.
- Optional LLM re-ranking: If results justify, add LLM-based re-ranking/sampling into discovery; revisit enabling the LLM UI by default.
- GitHub MCP enrichment: Evaluate using GitHub MCP (or similar) as an enrichment source for tool metadata where beneficial.
- Observability: Add lightweight metrics/timing for discovery/execution to guide tuning.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a pull request

Note: Development artifacts, historical documents, and outdated files have been moved to the `.archive` directory to keep the repository clean. These files are not tracked by git but are kept for historical reference.

## License

MIT
