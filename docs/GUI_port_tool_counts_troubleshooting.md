Title: GUI tool counts show 0, backend instability, and port coordination — changes and diagnostics

Summary
- Issue: GUI shows 0 tools and cards flip status; backend service often exits shortly after launch; port mismatches between GUI and backend cause connection failures.
- Goal: Make the GUI reflect actual tool_count from `/api/mcp/servers`, keep the backend stable, and ensure GUI/backend ports stay aligned automatically.

Changes Implemented
- Backend auto‑port fallback (first free port):
  - File: `src/hive_mcp_gateway/main.py`
  - Behavior: Try configured port (default `8001`). If busy, select first available in `8002–8025`. Logs: “Selected available port: <port>”.

- GUI config alignment and stable launcher:
  - File: `gui/main_app.py`
    - Use YAML config explicitly: `ConfigManager("config/tool_gating_config.yaml")`.
    - Auto‑start backend shortly after GUI init via `QTimer.singleShot`.
  - File: `gui/service_manager.py`
    - Accepts optional `ConfigManager` in constructor; reads `toolGating.port` for initial port.
    - Start command uses current interpreter: `[sys.executable, -m, hive_mcp_gateway.main]` (avoids uvicorn `--reload` churn).
    - Sets working directory to repo root and injects env: `CONFIG_PATH`, `HOST`, `PORT`, `LOG_LEVEL`.
    - Autodiscovery of backend port: probes configured port → `8001` → `8002–8025`; adopts detected port for all API calls.
    - `get_server_statuses()` now iterates candidate ports/hosts and updates `tool_gating_port` on success.
    - Reconnect uses the adopted base URL.
    - Added `_candidate_ports()` helper and improved `_is_port_in_use()`/`_find_available_port()` utilities.
    - Enhanced process diagnostics: `_on_process_finished(exit_code, exit_status)` logs exit details.

- GUI refresh and UI fixes:
  - File: `gui/main_window.py`
    - On service status Running: schedules `update_servers_display` and `update_all_server_tool_counts` and updates the Port input with active detected port.
    - Fixed missing local imports of `ServerCard` in three methods which previously caused silent exceptions and prevented count updates.
    - Added API banner, Refresh button, and new Reconnect All button to force an immediate reconnect across all servers.
    - Server cards now show any backend `error_message` in their tooltip to make failures visible (e.g., connection timeout, command not found).

What This Achieves
- Default binding to `8001`; if occupied, backend picks a free port in `8002–8025` automatically.
- GUI discovers and switches to whichever port the backend chose.
- Counts refresh when the service transitions to Running and periodically thereafter.

Observed Runtime Behavior (from user logs)
- Prior to changes: bind errors (“address already in use”) and GUI polling failures. After fallback logic, backend still exits early with `exit_code=1` (NormalExit), suggesting an application‑level error during/after startup; the GUI can’t fetch `/api/mcp/servers` and shows 0.

Diagnostics — How to Confirm Health
1) Start backend manually to capture logs:
   - `uv run python -m hive_mcp_gateway.main`
2) Validate endpoints (substitute the bound port if not `8001`):
   - `curl http://localhost:8001/health`
   - `curl http://localhost:8001/api/mcp/servers`
3) If the process exits, capture terminal output or enable more logs in the GUI (stdout/stderr are forwarded to the Logs tab via `ServiceManager._on_stdout/_on_stderr`).

Potential Remaining Causes of Early Exit
- Port collision persists despite fallback (all ports busy). Verify with `lsof -nP -iTCP:8001-8025 -sTCP:LISTEN`.
- Startup pipeline exceptions (e.g., during MCP registration or discovery). Manual run output will reveal the stacktrace.
- Environment dependencies for configured servers (e.g., `npx`, `uvx`, external servers like `exa` expected at `http://localhost:8002/exa`). If those fail hard on startup, the process can exit.

Operational Guidance
- Use YAML as the single source of truth: `config/tool_gating_config.yaml`.
- Keep gateway on `8001` whenever possible to avoid conflicts with servers like `exa` that might use `8002`.
- Let GUI auto‑start the backend; it will auto‑detect the active port and update the Port field once the backend reaches Running.

Next Proposed Enhancements (optional)
- Status banner in GUI: show “Active API: http://localhost:<port>” and last refresh result + a “Refresh now” button.
- Persist the auto‑selected port back to config (feature‑flagged) to survive restarts.
- Write backend stdout/stderr to a rotating file for post‑mortem when it exits early via QProcess.
- Add “Reconnect All” and “Discover tools now” buttons — Reconnect All has been implemented.

Files Touched (summary)
- `src/hive_mcp_gateway/main.py`: add fallback port selection.
- `gui/main_app.py`: use YAML config; auto‑start backend.
- `gui/service_manager.py`: config‑aware port init; stable start command; working dir/env injection; autodiscovery; enhanced status fetching; reconnect; process finish diagnostics; utility helpers.
- `gui/main_window.py`: refresh on running; reflect active port; fix `ServerCard` imports.

Open Items / Requests
- Need backend stdout/stderr from a manual run at the moment of exit to pinpoint the `exit_code=1` cause.
- If desired, enable the GUI status banner + refresh button for quicker visibility of API base and errors.
