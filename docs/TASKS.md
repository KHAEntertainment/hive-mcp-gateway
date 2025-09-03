# Tasks & TODOs

This file tracks near-term engineering tasks. Use alongside GitHub Issues for discussion and assignment.

## 1) Dynamic Port Fallback on Startup
- Summary: If the configured port (default 8001) is in use, start the API on the next available port instead of failing.
- Scope:
  - Detect port-in-use before launching (GUI `ServiceManager` and/or server startup in `main.py`).
  - Search sequentially (e.g., 8001→8010) or pick an ephemeral free port; prefer sequential for predictability.
  - Do not overwrite the persisted config automatically; only use the fallback at runtime and notify the user in GUI logs/status.
  - Respect `PORT` env if set (do not auto-fallback when explicitly pinned); log a clear error instead.
- Acceptance Criteria:
  - Starting with 8001 occupied results in successful start on another port, visible in GUI Status and reachable at `/health` and `/mcp`.
  - Clear notification to the user about which port was chosen and why.
  - Restarting on a free 8001 goes back to 8001 unless user changed config.

Follow-up (GUI Notice)
- Add a visible notice when a fallback port is used (e.g., banner or status panel message) with a quick action to open Port Settings.
- Ensure the Status widget reflects the runtime port clearly, while still indicating the configured default.

## 2) Branding Consistency Sweep (Docs)
- Summary: Replace remaining references to “Tool Gating MCP” with “Hive MCP Gateway” in documentation where applicable.
- Scope:
  - Update docs under `docs/` and any markdowns mentioning the legacy name (e.g., `docs/MCP_PROXY_PRP.md`, `docs/configuration.md`, troubleshooting notes).
  - Avoid changing code imports/paths (project already uses `hive_mcp_gateway`).
  - Note integrated MCP exposure at `/mcp`; remove assumptions that an external mcp-proxy is required.
- Acceptance Criteria:
  - No misleading legacy branding remains in docs.
- README/ARCHITECTURE/USAGE remain accurate and consistent post-sweep.

## 3) MCP Tool Counts Display 0 in Main GUI
- Summary: The main GUI shows tool_count = 0 for all servers even when tools are discovered.
- Likely Areas:
  - GUI: `gui/service_manager.py#get_server_statuses` and `gui/main_window.py#update_servers_display` mapping of server statuses to cards.
  - Backend: `MCPServerRegistry` updates via client manager after discovery (`registry.update_server_tool_count(...)`) and the list endpoint `/api/mcp/servers`.
- Scope:
  - Verify `/api/mcp/servers` returns correct `tool_count` for each server after discovery.
  - Ensure `client_manager.connect_server()` populates `server_tools` and discovery pipeline calls `update_server_tool_count`.
  - Confirm GUI uses the returned `tool_count` when available, and refresh timing is adequate.
- Acceptance Criteria:
  - After service start/discovery, GUI shows non-zero tool counts matching API values.
  - Restarting/reconnecting a server updates counts within the GUI without full app restart.

## Tracking & Workflow
- Primary: GitHub Issues (preferred for assignment, labels, and discussion).
- Local: This `TASKS.md` stays concise with acceptance criteria and links to issues once created.
