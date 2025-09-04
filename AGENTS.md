# Repository Guidelines

## Project Structure & Module Organization
- `src/hive_mcp_gateway/`: FastAPI app and core logic
  - `api/` (routers), `services/` (business logic), `platforms/` (macOS/Windows/Linux), `main.py` (app entry)
- `gui/`: PyQt6 UI launcher and related assets
- `config/`: Default YAML config (`config/tool_gating_config.yaml`)
- `tool_gating_config.json`: Legacy/alternate JSON config
- `tests/`: Pytest suite and fixtures
- `scripts/`: Utilities (e.g., config migration)
- `build/`, `dist/`: Packaging artifacts
- `docker/`: Docker assets (headless/server use)
- `docs/`, `examples/`: Additional guides and samples
- Integrated MCP: HTTP MCP endpoint mounted at `/mcp` (no external mcp-proxy required)

## Documentation Location
- All repository documentation lives under `docs/` to keep the root clean.
- Root keeps only core entry docs: `README.md`, `AGENTS.md`, and `CLAUDE.md`.
- Recently relocated files (now under `docs/`):
  - `ARCHITECTURE.md`, `BUILD.md`, `DEPLOYMENT.md`, `ROADMAP.md`, `TASKS.md`, `USAGE.md`, `CLAUDE_INTEGRATION.md`, `tool-gating-mcp-troubleshooting-notes.md`.
- Docker docs live under `docker/` (headless usage). GUI is native-only (see README and docs).
- When adding new docs, place them in `docs/` and link from `README.md` or `AGENTS.md` as needed.

## Build, Test, and Development Commands
- Install deps: `uv sync`
- Run API (+ HTTP MCP at `/mcp`): `uv run hive-mcp-gateway` or `uv run python -m hive_mcp_gateway.main`
- Tests: `uv run pytest -m "not slow"`
- Lint/format/type-check: `uv run ruff check .` • `uv run black .` • `uv run mypy src`
- macOS bundle: `./build/build_macos.sh`
- Docker (local, headless): `docker compose -f docker/docker-compose.yml up --build`
- Env overrides: `HOST`, `PORT` (default 8001), `CONFIG_PATH`

## Coding Style & Naming Conventions
- Python 3.12, 4-space indent. Type hints required (mypy strict on `src/`).
- Formatting: Black, line length 88. Lint: Ruff (E,F,W,I,N,B,A,C4,UP).
- Naming: modules/files `snake_case.py`, classes `CapWords`, functions/vars `snake_case`, constants `UPPER_CASE`.
- Keep functions small, async-safe, and place domain logic under `services/`.

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio`. Tests live in `tests/`, named `test_*.py` with `test_*` functions.
- Use markers: `@pytest.mark.unit`, `integration`, `slow`. Prefer unit tests for services and API endpoints; mark long-running flows as `slow`.
- Run specific suites: `uv run pytest -m unit` or exclude slow by default as above.

## Commit & Pull Request Guidelines
- Commit style: Prefer Conventional Commits (e.g., `feat:`, `fix:`, `docs:`, `refactor:`). Keep messages imperative and scoped.
- PRs: concise title, what/why/how, linked issues, testing notes. Include screenshots for GUI changes and example requests for API changes.
- Quality gates: linters, mypy, and tests must pass; update relevant docs (`README.md`, `docs/USAGE.md`, `docs/ARCHITECTURE.md`) when behavior changes.

## Security & Configuration Tips
- Never hardcode secrets; use env vars (see `.env.example`). Override config via `CONFIG_PATH` when needed.
- Prefer YAML at `config/tool_gating_config.yaml`; keep JSON in sync only if required.
- Validate changes against sample configs and avoid expanding MCP surface area unnecessarily.

## Runtime Configuration (Ports)
- Default port: `8001`. The GUI can change this (Status tab → Port → Save; restart required).
- If `8001` is occupied, no automatic fallback is performed today. Set a free port via GUI or `PORT` env.
- API and MCP endpoint are available on `http://<host>:<port>/` and `http://<host>:<port>/mcp`.

## Repository
- GitHub: https://github.com/KHAEntertainment/hive-mcp-gateway
