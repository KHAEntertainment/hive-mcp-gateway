# Error Handling and Recovery

Tool Gating MCP includes a comprehensive error handling and recovery system designed to maintain system stability and provide graceful degradation when issues occur.

## Error Types

The system defines several specific error types to handle different failure scenarios:

### MCPError
Base exception class for all MCP-related errors.

### ConfigurationError
Raised when there are issues with server configuration.

### ConnectionError
Raised when connection to MCP servers fails.

### AuthenticationError
Raised when authentication with MCP servers fails.

### ToolExecutionError
Raised when tool execution fails.

### HealthCheckError
Raised when server health checks fail.

## Error Handling Features

### Automatic Retry with Exponential Backoff

The system automatically retries failed operations with exponential backoff to prevent overwhelming servers:

```python
async def retry_with_backoff(self, func, *args, max_retries=3, base_delay=1.0, **kwargs):
    """Execute a function with exponential backoff retry logic."""
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Max retries exceeded for {func.__name__}: {e}")
                raise
            
            delay = base_delay * (2 ** attempt)  # Exponential backoff
            logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
```

### Circuit Breaker Pattern

To prevent cascading failures, the system implements a circuit breaker pattern that temporarily disables problematic servers:

```python
def should_circuit_break(self, server_name: str) -> bool:
    """Determine if circuit breaker should be triggered for a server."""
    recent_errors = len(self.error_timestamps.get(server_name, []))
    return recent_errors > self.max_errors_per_minute * 2  # Trigger at 2x error rate
```

### Error Rate Limiting

The system tracks error rates and implements throttling when servers are experiencing high error rates:

```python
def _determine_recovery_action(self, server_name: str, error: Exception, error_info: Dict[str, Any]) -> Dict[str, Any]:
    """Determine appropriate recovery action based on error type and frequency."""
    # Check error rate
    recent_errors = len(self.error_timestamps.get(server_name, []))
    if recent_errors > self.max_errors_per_minute:
        return {
            "action": "throttle",
            "delay": 30,  # Wait 30 seconds
            "details": {"reason": "high_error_rate", "error_count": recent_errors}
        }
    # ... other recovery actions
```

## Recovery Actions

The error handler automatically determines and executes appropriate recovery actions based on error types:

### Reload Configuration
For configuration errors, the system can reload the server configuration.

### Refresh Authentication
For authentication errors, the system can attempt to refresh authentication credentials.

### Reconnect
For connection errors, the system can attempt to reconnect to the server.

### Health Check
For health check failures, the system can perform additional diagnostic checks.

### Retry Tool
For tool execution errors, the system can retry the tool execution.

## Error Tracking and Monitoring

The system maintains detailed error statistics for monitoring and debugging:

```python
def get_error_summary(self) -> Dict[str, Any]:
    """Get a summary of all errors across servers."""
    return {
        "total_servers_with_errors": len(self.error_counts),
        "error_counts": self.error_counts,
        "recent_errors_by_server": {
            server: len(timestamps) 
            for server, timestamps in self.error_timestamps.items()
        }
    }
```

### Error Statistics

- Total errors per server
- Recent error rates (errors per minute)
- Recovery actions taken
- Error types and frequencies

## Integration with Logging

All errors are logged with appropriate severity levels:

- **ERROR**: Configuration errors, authentication failures
- **WARNING**: Connection issues, health check failures
- **INFO**: Tool execution errors (for debugging)

## Custom Error Handling

Developers can implement custom error handling by extending the `ErrorHandler` class or by providing custom recovery actions:

```python
class CustomErrorHandler(ErrorHandler):
    def _determine_recovery_action(self, server_name: str, error: Exception, error_info: Dict[str, Any]) -> Dict[str, Any]:
        # Custom recovery logic
        recovery_action = super()._determine_recovery_action(server_name, error, error_info)
        
        # Add custom recovery actions
        if isinstance(error, CustomErrorType):
            recovery_action.update({
                "action": "custom_action",
                "details": {"custom_field": "custom_value"}
            })
        
        return recovery_action
```

## Best Practices

### Environment Variable Management

Use environment variables for sensitive configuration like API keys:

```yaml
backendMcpServers:
  exa:
    # ...
    authentication:
      type: "bearer"
      token: "${EXA_API_KEY}"  # Securely managed via environment variables
```

### Health Check Configuration

Configure appropriate health check intervals for different server types:

```yaml
healthCheck:
 enabled: true
  interval: 60  # Adjust based on server stability and requirements
  timeout: 10   # Prevent hanging health checks
```

### Monitoring and Alerting

Implement monitoring and alerting for critical error conditions:

- High error rates across multiple servers
- Repeated circuit breaker activations
- Authentication failures
- Configuration validation errors

## Troubleshooting

### Common Issues

1. **Connection Refused**: Check server URLs and network connectivity
2. **Authentication Failed**: Verify API keys and credentials
3. **High Error Rates**: Investigate server performance and stability
4. **Configuration Validation Errors**: Check configuration file syntax and required fields

### Diagnostic Commands

```bash
# Check server health
curl http://localhost:8001/health

# View detailed logs
tail -f server.log

# Test configuration validity
python -m hive_mcp_gateway --validate-config
```

### Log Analysis

Key log entries to monitor:

- Error messages with stack traces
- Recovery actions taken
- Circuit breaker activations
- Health check results

## Extending Error Handling

To add new error types or recovery actions:

1. Create a new exception class extending `MCPError`
2. Add handling logic in the `ErrorHandler` class
3. Update recovery action determination logic
4. Add appropriate logging and monitoring

```python
class CustomMCPError(MCPError):
    """Custom MCP error for specific use cases."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CUSTOM_ERROR", details)