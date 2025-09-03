# FastAPI application for tool gating MCP
# Main module initialization

import sys

from .main import app as app

__version__ = "0.2.0"


def _is_port_in_use(port: int) -> bool:
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def _find_available_port(start_port: int, tries: int = 10) -> int | None:
    try:
        import socket
        for port in range(start_port, start_port + max(1, tries)):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
    except Exception:
        return None
    return None


def main() -> None:
    """CLI entry point for the application (with dynamic port fallback)."""
    import os
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    env_port = os.getenv("PORT")

    if env_port is not None:
        # Respect explicit env PORT (no auto-fallback)
        try:
            port = int(env_port)
        except ValueError:
            raise SystemExit(f"Invalid PORT env value: {env_port}")
        if _is_port_in_use(port):
            raise SystemExit(f"PORT {port} is already in use and was explicitly set. Aborting.")
    else:
        # Default desired port aligns with GUI default
        desired = 8001
        port = desired
        if _is_port_in_use(desired):
            fallback = _find_available_port(desired, tries=10)
            if fallback is None:
                raise SystemExit(f"No available port found near {desired}. Aborting.")
            port = fallback

    uvicorn.run("hive_mcp_gateway.main:app", host=host, port=port, reload=False)
