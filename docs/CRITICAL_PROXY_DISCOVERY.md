# CRITICAL DISCOVERY: MCP Proxy Confusion (September 2024)

## The 3-Day Debugging Saga

### THE PROBLEM
We spent **3 days** troubleshooting STDIO server connection issues, only to discover we were using the **WRONG MCP PROXY** the entire time.

### THE ROOT CAUSE

There are **TWO DIFFERENT** projects called "mcp-proxy":

1. **Anthropic mcp-proxy** (`uv tool install mcp-proxy`)
   - Official Anthropic MCP proxy
   - Version: 0.8.2
   - Command line args: `--named-server`, `--port`, etc.
   - NOT compatible with our configuration format

2. **TBXark/mcp-proxy** (https://github.com/TBXark/mcp-proxy)
   - Go-based proxy that ajbmachon's tool-gating-mcp was designed for
   - Uses JSON config file with `--config` flag
   - Available as Docker image: `ghcr.io/tbxark/mcp-proxy:latest`
   - THIS IS THE ONE WE NEEDED

### WHAT WENT WRONG

1. We installed `mcp-proxy` via uv: `uv tool install mcp-proxy`
2. This installed the **Anthropic version**, not the TBXark version
3. Our code was written for TBXark's proxy (JSON config, different endpoints)
4. The Anthropic proxy couldn't parse our `--config` flag and silently failed
5. We spent days debugging STDIO connection issues when the proxy wasn't even running

### THE SYMPTOMS

- "MCP Proxy could not be started automatically (binary/docker not found)"
- STDIO servers showing as disconnected (red in GUI)
- 0 tools discovered
- Endless initialization timeouts and "cancel scope" errors
- Direct STDIO connections failing with race conditions

### THE SOLUTION

Use the Docker image of TBXark/mcp-proxy:
```bash
docker pull ghcr.io/tbxark/mcp-proxy:latest
```

The proxy orchestrator now prioritizes Docker and uses the correct proxy.

### CRITICAL DIFFERENCES

#### Anthropic mcp-proxy
- Command: `mcp-proxy --named-server-config servers.json --port 9090`
- Endpoint format: Unknown/different
- Config format: Different JSON structure
- Installation: `uv tool install mcp-proxy`

#### TBXark mcp-proxy  
- Command: `mcp-proxy --config config.json`
- Endpoint format: `http://localhost:9090/{server_name}/`
- Config format: Our existing JSON format
- Installation: Docker or build from Go source

### LESSONS LEARNED

1. **Always verify which implementation you're using** when multiple projects share the same name
2. **Check version and help output** to confirm the right tool
3. **Docker images can save debugging time** by ensuring the right version
4. **The original project documentation matters** - ajbmachon used TBXark, not Anthropic

### HOW TO VERIFY YOU HAVE THE RIGHT PROXY

Wrong (Anthropic):
```bash
$ mcp-proxy --version
mcp-proxy 0.8.2

$ mcp-proxy --help
usage: mcp-proxy [-h] [--version] [-H KEY VALUE] ...
```

Right (TBXark via Docker):
```bash
$ docker run ghcr.io/tbxark/mcp-proxy:latest --help
# Shows different help with --config option
```

### THE FIX TIMELINE

- **Day 1-3**: Trying to debug "STDIO connection issues"
- **Day 4**: Discovered we had the wrong mcp-proxy entirely
- **Solution**: Used Docker image of the correct proxy
- **Result**: Everything worked immediately

## Never Forget

**We weren't debugging connection issues. We were using the wrong software entirely.**

This is why the original ajbmachon/tool-gating-mcp project documentation should have been more explicit about WHICH mcp-proxy to use.
