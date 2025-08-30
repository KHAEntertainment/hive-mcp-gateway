# Automatic Server Registration

Hive MCP Gateway features an advanced automatic server registration system that simplifies MCP server management through a multi-stage pipeline with fallback mechanisms.

## Overview

The automatic registration system provides:

- **Multi-Stage Pipeline**: Registration process with multiple stages for robust server onboarding
- **Fallback Mechanisms**: Automatic fallback to alternative registration methods when primary methods fail
- **Health Monitoring**: Continuous health checks and status updates
- **Retry Logic**: Automatic retry with exponential backoff for failed registrations
- **Error Recovery**: Comprehensive error handling and recovery mechanisms

## Registration Pipeline

The automatic registration process follows a three-stage pipeline:

### Stage 1: Primary Registration

1. Load server configuration from the main configuration file
2. Validate server configuration parameters
3. Attempt direct connection to the server
4. Register server in the internal registry
5. Discover and catalog available tools

### Stage 2: Health Validation

1. Perform initial health check on registered servers
2. Update server status with health information
3. Validate tool discovery results
4. Set server connection status

### Stage 3: Retry Failed Registrations

1. Identify servers that failed initial registration
2. Apply exponential backoff before retry attempts
3. Retry registration with primary method
4. Apply fallback registration if primary retry fails

## Fallback Mechanisms

When primary registration methods fail, the system automatically attempts fallback registration:

### Primary Registration Method

1. Direct connection to the MCP server
2. Tool discovery and validation
3. Full server registration with all features enabled

### Fallback Registration Method

1. Registry-only registration without active connection
2. Server marked as disconnected but available for future activation
3. Metadata and configuration preserved for later use

## Configuration

Automatic registration is configured through the main configuration file:

```yaml
toolGating:
  autoDiscover: true  # Enable automatic server discovery and registration
  # ... other settings
```

Each server can be individually enabled or disabled:

```yaml
backendMcpServers:
  server_name:
    enabled: true # Set to false to skip registration
    # ... other server settings
```

## Health Monitoring

The system continuously monitors server health through:

### Periodic Health Checks

```yaml
healthCheck:
  enabled: true
  interval: 60  # Check every 60 seconds
```

### Health Status Tracking

Servers maintain health status information:
- `healthy`: Server is operating normally
- `unhealthy`: Server is experiencing issues
- `degraded`: Server is operating with reduced functionality
- `unknown`: Health status cannot be determined

## Retry Logic

Failed registrations are automatically retried with exponential backoff:

1. **First retry**: 2 seconds delay
2. **Second retry**: 4 seconds delay
3. **Third retry**: 8 seconds delay
4. **Maximum retries**: 3 attempts

Configuration options:

```yaml
options:
  retryCount: 3 # Number of retry attempts
```

## Error Handling

The registration system includes comprehensive error handling:

### Error Types

- **Configuration Errors**: Invalid server configuration
- **Connection Errors**: Unable to connect to server
- **Authentication Errors**: Authentication failures
- **Discovery Errors**: Tool discovery failures

### Recovery Actions

- **Reload Configuration**: For configuration errors
- **Refresh Authentication**: For authentication failures
- **Reconnect**: For connection issues
- **Health Check**: For diagnostic purposes

## API Integration

The automatic registration system integrates with the REST API:

### List Registered Servers

```http
GET /api/mcp/servers
```

### Register New Server

```http
POST /api/mcp/servers
Content-Type: application/json

{
  "name": "new_server",
  "config": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@upstash/context7-mcp@latest"]
  }
}
```

### Unregister Server

```http
DELETE /api/mcp/servers/{server_name}
```

## Programmatic Usage

The automatic registration system can be used programmatically:

```python
from hive_mcp_gateway.services.auto_registration import AutoRegistrationService

# Initialize the registration service
auto_registration = AutoRegistrationService(config_manager, client_manager, registry)

# Register all servers from configuration
results = await auto_registration.register_all_servers(config)

# Register a new server
result = await auto_registration.register_new_server("new_server", server_config)

# Unregister a server
result = await auto_registration.unregister_server("server_name")
```

## Monitoring and Metrics

The system provides detailed metrics for monitoring:

### Registration Statistics

- Total servers registered
- Successful registrations
- Failed registrations
- Skipped registrations (disabled servers)

### Health Metrics

- Server health status distribution
- Health check success/failure rates
- Average response times
- Error rates by server

### Performance Metrics