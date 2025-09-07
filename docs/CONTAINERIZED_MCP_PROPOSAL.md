# Containerized MCP Servers Architecture

## Overview

Instead of running MCP servers as local processes, containerize each server for isolation, consistency, and better management.

## Architecture

```
┌─────────────────────────────────────────┐
│       Hive MCP Gateway (Port 8001)      │
│                                          │
│  ┌────────────────────────────────┐     │
│  │   MCP Client Manager           │     │
│  │                                │     │
│  │  Connects to MCP servers via:  │     │
│  │  - Docker containers (stdio)   │     │
│  │  - Docker containers (HTTP)    │     │
│  └────────────────────────────────┘     │
└─────────────────────────────────────────┘
                    │
       ┌────────────┼────────────┐
       ↓            ↓            ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Container 1  │ │ Container 2  │ │ Container 3  │
│              │ │              │ │              │
│ basic_memory │ │  context7    │ │  puppeteer   │
│   (FastMCP)  │ │  (npx MCP)   │ │  (Browser)   │
│              │ │              │ │              │
│ • Isolated   │ │ • Isolated   │ │ • Isolated   │
│ • No banners │ │ • Clean logs │ │ • Sandboxed  │
└──────────────┘ └──────────────┘ └──────────────┘
```

## Implementation Approaches

### Option 1: Docker Compose Integration

```yaml
# docker-compose.mcp.yml
services:
  basic-memory:
    image: fastmcp/basic-memory:latest
    command: ["mcp"]
    environment:
      - FASTMCP_NO_BANNER=1
    labels:
      - "mcp.server=basic_memory"
      - "mcp.type=stdio"
  
  context7:
    build:
      context: .
      dockerfile: Dockerfile.context7
    command: ["npx", "-y", "@upstash/context7-mcp@latest"]
    labels:
      - "mcp.server=context7"
      - "mcp.type=stdio"
```

### Option 2: Dynamic Container Creation

```python
class ContainerizedMCPClient:
    async def connect_server(self, name: str, config: dict):
        import docker
        client = docker.from_env()
        
        # Create container for MCP server
        container = client.containers.run(
            image=config.get('image', f'mcp/{name}:latest'),
            command=config.get('command'),
            detach=True,
            stdin_open=True,
            tty=False,
            labels={'mcp.server': name},
            environment=config.get('env', {})
        )
        
        # Connect via docker exec for stdio
        exec_cmd = container.exec_run(
            cmd='cat',  # Bridge for stdio
            stdin=True,
            stdout=True,
            stderr=False,
            stream=True
        )
        
        # Use exec streams as stdio
        return exec_cmd.output, exec_cmd.input
```

### Option 3: Dagger Container-Use Integration

Using the `container-use` project mentioned:

```python
class DaggerMCPClient:
    async def connect_server(self, name: str, config: dict):
        # Use dagger/container-use for managed containers
        subprocess.run([
            "container-use", 
            "start",
            f"--name={name}",
            f"--command={config['command']}",
            f"--args={' '.join(config['args'])}"
        ])
        
        # Connect via container-use stdio bridge
        return await self._connect_container_stdio(name)
```

## Configuration Changes

```json
{
  "servers": {
    "basic_memory": {
      "type": "container",
      "transport": "stdio",
      "image": "ghcr.io/fastmcp/basic-memory:latest",
      "command": "mcp",
      "env": {
        "FASTMCP_NO_BANNER": "1"
      }
    },
    "context7": {
      "type": "container", 
      "transport": "stdio",
      "dockerfile": "./dockerfiles/context7.Dockerfile",
      "command": "npx -y @upstash/context7-mcp@latest"
    }
  }
}
```

## Benefits

1. **Solves Banner Problem**: Container stdout/stderr can be managed separately
2. **Process Isolation**: No conflicts between multiple instances
3. **Resource Control**: CPU/memory limits per server
4. **Easy Cleanup**: `docker stop` and `docker rm`
5. **Reproducible**: Same environment every time
6. **Security**: Sandboxed execution
7. **Scalability**: Can run multiple instances easily

## Implementation Steps

### Phase 1: Proof of Concept
1. Create Dockerfile for one problematic server (basic_memory)
2. Test stdio communication through Docker
3. Verify banner issue is resolved

### Phase 2: Integration
1. Add Docker client to MCP Client Manager
2. Create container management service
3. Update configuration schema

### Phase 3: Production
1. Pre-build common MCP server images
2. Add health checks and monitoring
3. Implement container lifecycle management

## Example Dockerfiles

### FastMCP Server (basic_memory)
```dockerfile
FROM python:3.11-slim
RUN pip install uvx basic-memory
ENV FASTMCP_NO_BANNER=1
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["uvx", "basic-memory", "mcp"]
```

### Node.js MCP Server (context7)
```dockerfile
FROM node:20-slim
RUN npm install -g @upstash/context7-mcp@latest
ENTRYPOINT ["npx", "-y", "@upstash/context7-mcp@latest"]
```

## Testing Strategy

1. Start with most problematic servers (basic_memory, context7)
2. Compare containerized vs native performance
3. Validate tool discovery works correctly
4. Test multiple simultaneous connections

## Considerations

- **Performance**: Container overhead vs process isolation benefits
- **Complexity**: Additional Docker dependency
- **Storage**: Docker images need disk space
- **Networking**: Container networking for HTTP-based MCPs
- **Development**: Harder to debug containerized services

## Recommendation

Start with a hybrid approach:
- Containerize problematic stdio servers (FastMCP)
- Keep simple/stable servers native
- Make containerization optional via config flag

This solves our immediate banner problem while providing a path to full containerization if needed.
