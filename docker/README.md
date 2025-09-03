Hive MCP Gateway — Docker (Headless)

This folder contains Docker assets for running the Hive MCP Gateway in headless/server mode. The native GUI application (PyQt6) is intended to be run directly on your OS and distributed as a macOS app bundle (.app / .dmg / .pkg). If you want the GUI, use the main application instead of Docker.

What’s included
- Headless gateway (production) on port 8001.
- Development profile with live reload and the repo mounted.
- Optional Redis and Prometheus services (off by default via profiles).

What’s not included
- The GUI in Docker is currently disabled/untested. Running PyQt6 via X11 in containers is clunky and not supported for production. Use the native app bundle for GUI usage.

Quick start
- Production: `docker compose -f docker/docker-compose.yml up --build -d`
- Development (live reload): `docker compose -f docker/docker-compose.yml --profile development up`

Pinning Node MCP servers
- The Dockerfile supports build args to pin versions:
  - `PUPPETEER_MCP_VERSION` (default `@modelcontextprotocol/server-puppeteer@latest`)
  - `CONTEXT7_MCP_VERSION` (default `@upstash/context7-mcp@latest`)
- Example:
  `docker compose -f docker/docker-compose.yml build \
     --build-arg PUPPETEER_MCP_VERSION=@modelcontextprotocol/server-puppeteer@0.7.2 \
     --build-arg CONTEXT7_MCP_VERSION=@upstash/context7-mcp@0.2.2`

Configuration
- The container reads `CONFIG_PATH=/app/hive_mcp_gateway_config.json`.
- By default, we bind-mount `../hive_mcp_gateway_config.json` into the container read-only.
- Named volumes persist logs and data across restarts.

Notes
- Images build from the current repo state; no separate branch is required.
- If you change Python dependencies, update `uv.lock` and rebuild.
- If you add Node-based MCP servers, update the Dockerfile’s global npm install list.
