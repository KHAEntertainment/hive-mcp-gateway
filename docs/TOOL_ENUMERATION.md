# Tool Enumeration Modes

Hive MCP Gateway supports two conceptual modes for discovering (enumerating) tools from backend MCP servers.

- Deterministic (default): Uses the MCP Python SDK to connect to servers and list tools programmatically. This is enabled today and runs when you add/connect a server.
- LLM‑assisted (optional/experimental): Uses an external LLM (e.g., Anthropic Messages API) to connect and report tools. Present in code as a helper, not wired into the main flow.

## 1) Deterministic Enumeration (Default)

- Path: `MCPClientManager.connect_server()` discovers tools and stores them in `server_tools` and the unified tool repository.
- Trigger: `POST /api/mcp/add_server` (or automatic registration at startup) connects and enumerates immediately.
- Benefits: Fast, reliable, no additional keys required, consistent results.
- Status: Enabled and used by default.

## 2) LLM‑Assisted Enumeration (Optional)

- Path: `services/mcp_connector.py: discover_via_anthropic_api()`
- Intent: Ask an LLM to enumerate available tools (e.g., via Anthropic’s `mcp_servers` support).
- Status: Present as a helper; not wired into `add_server` or the startup pipeline.
- When to use: Only if you need LLM sampling or richer metadata enrichment that is not available via deterministic enumeration.

## Recommendation

- Use deterministic enumeration as the primary method—it is already enabled and tested in the current flow.
- Keep the LLM‑assisted path disabled until a controlled rollout or benchmark indicates clear benefit.

## Future Enablement (Planned)

- Add a feature flag (e.g., `HMG_ENABLE_LLM_ENUM=1`) to route `add_server` through the LLM helper when appropriate credentials are present.
- Gate by server metadata (only certain servers) or fallback automatically if LLM enumeration fails.

