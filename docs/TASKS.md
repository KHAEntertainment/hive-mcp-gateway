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

## 12) Hybrid stdio via MCP Proxy with Gateway Tool Gating
- Summary: Preserve minimal tool exposure (tool gating) while gaining robust stdio lifecycle by optionally delegating stdio process management to MCP Proxy, keeping the gateway as the single client-facing MCP server that filters/publishes a curated subset of tools.
- Approach:
  - Gateway remains the MCP surface. It intercepts `listTools` and returns only the currently “published” tools (deny-by-default policy), and enforces gating on `callTool`.
  - Backends:
    - HTTP/SSE servers continue directly (e.g., exa).
    - stdio servers can run either directly (current path) or via MCP Proxy (`via: proxy`) per server in YAML.
  - Discovery runs in background (proxy/direct) and populates a registry; publication is a separate step driven by config and provisioning.
- Config (YAML):
  - `toolGating.defaultPolicy: deny|allow`
  - Per-server `options.toolFilter` (allow/deny lists, wildcards, tags).
  - Optional `proxy.url` and per-server `via: proxy|direct`.
- API additions:
  - `POST /api/tools/provision` to publish a set (ids/tags/patterns, optional `max_tools`).
  - `GET /api/tools/published` to inspect current exposure.
- Gateway changes:
  - Add `GatingService` managing discovered vs published sets.
  - Intercept `listTools` to return only published subset; validate in `callTool`.
  - Add `proxy-http` transport in `MCPClientManager` to talk to MCP Proxy for stdio.
- GUI changes:
  - Show Discovered vs Published counts per server.
  - Add simple “Publish Selected” flow (MVP: publish all from a server; later: select by tag/name).
  - Respect `via: proxy` by directing Discover/Reconnect to Proxy endpoints.
- Acceptance Criteria:
  - With `via: proxy`, stdio servers remain stable even under slow start; GUI shows connected quickly and tool counts update after discovery.
  - `listTools` from the gateway returns only the published set (<= configured `max_tools`).
  - `callTool` only executes for published tools; others return a clear gating error or guidance to provision.
  - Disabling proxy mode preserves current direct-stdio behavior.
- Notes:
  - Reference donor project intent (tool-gating) while integrating optional MCP Proxy: https://github.com/ajbmachon/tool-gating-mcp
  - Optional migration path; proxy can be enabled per server for A/B testing.

## Tracking & Workflow
- Primary: GitHub Issues (preferred for assignment, labels, and discussion).
- Local: This `TASKS.md` stays concise with acceptance criteria and links to issues once created.

---

## 4) Stabilize Deterministic Enumeration and Proxy Execution (GUI E2E)
- Summary: Validate the default deterministic tool enumeration and proxy execution flow end‑to‑end using the GUI.
- Scope:
  - GUI: Add MCP server → enumerate tools (deterministic) → discover → execute via proxy.
  - Backend: Confirm `MCPClientManager.connect_server` populates tools; `discover_tools` returns relevant tools; `proxy.execute_tool` routes by `server_toolname`.
  - Verify macOS app and dev run (`run_gui.py`); confirm `/mcp` works with a single client config.
- Acceptance Criteria:
  - Register ≥2 backend servers; see tools from both in discovery.
  - Execute ≥1 tool per server via `POST /api/proxy/execute`.
  - GUI/logs clearly show deterministic enumeration steps; README GUI quickstart suffices.

## 5) Enforce Per‑Server toolFilter During Registration
- Summary: Apply allow/deny lists from `BackendServerConfig.options.toolFilter` during ingestion.
- Scope:
  - Enforce in `api/mcp.add_server` when registering discovered tools (or earlier in `MCPClientManager`).
  - Case‑insensitive name match; consider simple wildcards; update docs with YAML examples.
- Acceptance Criteria:
  - Deny mode excludes configured tools; allow mode includes only configured tools.
  - Unit + integration tests through `POST /api/mcp/add_server`.

## 6) Add Optional Provisioning Path and Enforcement for execute_tool
- Summary: Add `/api/tools/provision` using `GatingService` and a flag to require provisioning prior to execution.
- Scope:
  - Endpoint accepts `tool_ids`, `max_tools`, `context_tokens`; stores provisioned set.
  - Feature flag `HMG_REQUIRE_PROVISION=1` gates `execute_tool`.
  - Docs updated with examples.
- Acceptance Criteria:
  - Default unchanged; with flag on, non‑provisioned tools rejected (400).
  - Unit tests for provision/enforcement; update API contract tests.

## 7) Wire LLM‑Assisted Enumeration Behind Feature Flag (Fallback)
- Summary: Implement `HMG_ENABLE_LLM_ENUM` to optionally run LLM enumeration with Anthropic, with automatic fallback.
- Scope:
  - On flag + keys, call `services/mcp_connector.discover_via_anthropic_api` during `add_server`.
  - Merge/enrich with deterministic; de‑dup by name; add timing logs.
  - Document behavior and flag usage.
- Acceptance Criteria:
  - Flag off: unchanged. Flag on + keys: LLM path attempts and succeeds; response indicates path. Errors fall back deterministically.
  - Tests with mocks for both paths.

## 8) Update GUI Copy/Tooltips for LLM Optionality and Flags
- Summary: Clarify that LLM config is optional/disabled by default; show UI only when `HMG_ENABLE_LLM_UI=1`.
- Scope:
  - Adjust texts/tooltips; add contextual help linking to docs; avoid dead buttons.
- Acceptance Criteria:
  - Default GUI does not imply a required internal LLM.
  - With flag, UI appears and clearly labels optional/experimental status.

## 9) Observability: Basic Metrics/Timing for Discovery and Execution
- Summary: Add lightweight metrics/timing and structured logs for key stages.
- Scope:
  - Timings for connect + enumeration, discovery requests, execute routing; request IDs in logs; optional `/metrics` later.
- Acceptance Criteria:
  - Timings visible in logs; negligible overhead; comparable runs feasible.

## 10) Integration Tests for Proxy Execution, Filters, and Flags
- Summary: Cover `execute_tool` routing, toolFilter enforcement, and feature flags.
- Scope:
  - Valid/invalid tool_id formats; cross‑server routing; allow/deny tests; flags for LLM enum and provisioning (mocked).
- Acceptance Criteria:
  - Tests run under `uv run pytest -m "not slow"`; cover success/error paths; stable CI.

## 11) Documentation Polish & Screenshots (GUI‑First)
- Summary: Replace README screenshot placeholders and emphasize GUI‑first flow.
- Scope:
  - Real screenshots, optional demo GIF, client setup snippets; cross‑link `TOOL_ENUMERATION.md` and LLM sections.
- Acceptance Criteria:
  - README GUI section complete and accurate; docs reflect flags and current defaults.
