# Configuration Guide

Tool Gating MCP supports both YAML and JSON configuration formats. The YAML format is recommended as it provides better readability and supports comments.

## Configuration File Locations

By default, Tool Gating MCP looks for configuration files in the following locations:

1. `config/tool_gating_config.yaml` (YAML format)
2. `tool_gating_config.json` (JSON format)

You can specify a custom configuration file using the `CONFIG_PATH` environment variable:

```bash
CONFIG_PATH=/path/to/your/config.yaml python -m hive_mcp_gateway
```

## YAML Configuration Format

The YAML configuration format provides enhanced features including authentication, health checks, and metadata.

### Basic Structure

```yaml
toolGating:
  # Application settings
  port: 8001
  host: "0.0.0.0"
  logLevel: "info"
  # ... other tool gating settings

backendMcpServers:
  # Server configurations
  server_name:
    # Server settings
```

### Tool Gating Settings

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `port` | integer | Port to listen on | 8001 |
| `host` | string | Host to bind to | "0.0.0.0" |
| `logLevel` | string | Logging level (debug, info, warning, error) | "info" |
| `autoDiscover` | boolean | Automatically discover tools from connected servers | true |
| `maxTokensPerRequest` | integer | Maximum tokens allowed per request | 2000 |
| `maxToolsPerRequest` | integer | Maximum tools to include per request | 10 |
| `configWatchEnabled` | boolean | Watch configuration file for changes | true |
| `healthCheckInterval` | integer | Interval between health checks in seconds | 30 |
| `connectionTimeout` | integer | Connection timeout in seconds | 10 |

### Backend Server Configuration

Each backend MCP server can be configured with the following settings:

#### Common Fields

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `type` | string | Server type: `stdio`, `sse`, or `streamable-http` | Yes |
| `description` | string | Human-readable description of the server | No |
| `enabled` | boolean | Whether the server is enabled | No (default: true) |
| `authentication` | object | Authentication configuration | No |
| `healthCheck` | object | Health check configuration | No |
| `metadata` | object | Server metadata | No |
| `options` | object | Server-specific options | No |

#### Stdio Server Fields

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `command` | string | Command to execute | Yes |
| `args` | array | Command arguments | No |
| `env` | object | Environment variables | No |

#### HTTP Server Fields

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `url` | string | Server URL | Yes |
| `headers` | object | HTTP headers to send with requests | No |

### Authentication Configuration

Tool Gating MCP supports several authentication methods:

#### No Authentication

```yaml
authentication:
  type: "none"
```

#### Bearer Token Authentication

```yaml
authentication:
  type: "bearer"
  token: "${API_TOKEN}"  # Environment variable substitution supported
```

#### Basic Authentication

```yaml
authentication:
  type: "basic"
  username: "${USERNAME}"
  password: "${PASSWORD}"
```

### Health Check Configuration

Health checks monitor server connectivity and performance:

```yaml
healthCheck:
  enabled: true
  interval: 60 # Check every 60 seconds
  endpoint: "/health"  # For HTTP servers only
  timeout: 10   # Timeout after 10 seconds
```

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `enabled` | boolean | Enable health checks | true |
| `interval` | integer | Check interval in seconds | 60 |
| `endpoint` | string | Health check endpoint (HTTP servers only) | "/health" |
| `timeout` | integer | Check timeout in seconds | 10 |

### Metadata Configuration

Metadata provides additional information about servers:

```yaml
metadata:
  category: "search"
  version: "1.0"
  tags: ["web", "research", "api"]
  description: "Web search and research tools"
```

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `category` | string | Server category | "unknown" |
| `version` | string | Server version | "unknown" |
| `tags` | array | Server tags | [] |
| `description` | string | Detailed description | "" |

### Server Options

Server options configure tool filtering and execution behavior:

```yaml
options:
  toolFilter:
    mode: "allow"  # or "deny"
    list: ["tool1", "tool2"]
  timeout: 30
  retryCount: 3
  batchSize: 10
```

#### Tool Filter

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `mode` | string | Filter mode: "allow" or "deny" | "allow" |
| `list` | array | List of tool names | [] |

#### Execution Options

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `timeout` | integer | Tool execution timeout in seconds | 30 |
| `retryCount` | integer | Number of retry attempts | 3 |
| `batchSize` | integer | Number of tools to process in batch | 10 |

## Example Configurations

### Stdio Server with Authentication

```yaml
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
```

### HTTP Server with Bearer Authentication

```yaml
backendMcpServers:
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

### HTTP Server with Basic Authentication

```yaml
backendMcpServers:
  github:
    type: "streamable-http"
    url: "https://api.github.com/mcp"
    headers:
      User-Agent: "ToolGatingMCP/1.0"
    description: "GitHub integration for repository management"
    enabled: false
    authentication:
      type: "basic"
      username: "${GITHUB_USERNAME}"
      password: "${GITHUB_TOKEN}"
    healthCheck:
      enabled: true
      interval: 60
      endpoint: "/health"
    metadata:
      category: "version-control"
      version: "v3"
      tags: ["github", "git", "repository"]
    options:
      timeout: 30
      retryCount: 2
      batchSize: 1
```

## Environment Variable Substitution

Tool Gating MCP supports environment variable substitution in configuration files using the `${VARIABLE_NAME}` syntax:

```yaml
backendMcpServers:
 exa:
    type: "sse"
    url: "http://localhost:8002/exa"
    headers:
      Authorization: "Bearer ${EXA_API_KEY}"
    # ...
```

## Migration from JSON

To migrate from the legacy JSON format to the new YAML format with enhanced features:

```bash
python scripts/migrate_config_to_yaml.py tool_gating_config.json config/tool_gating_config.yaml --backup
```

This will:
1. Convert your existing JSON configuration to YAML
2. Add new fields for authentication, health checks, and metadata
3. Create a backup of your original configuration (if --backup is specified)

The migration script automatically adds default values for new fields:
- Authentication: `type: "none"`
- Health Check: `enabled: true, interval: 60`
- Metadata: `category: "unknown", version: "unknown", tags: []`
- Options: `timeout: 30, retryCount: 3, batchSize: 1`

## Validation

Tool Gating MCP validates configuration files at startup and provides detailed error messages for invalid configurations. The validation includes:

- Required fields for each server type
- Valid values for enumerated fields
- Proper syntax for environment variable substitution
- Consistent data types

If validation fails, the application will log detailed error messages and exit.