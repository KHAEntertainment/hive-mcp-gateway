"""Automatic orchestrator for MCP Proxy (TBXark/mcp-proxy or container).

Writes a proxy config based on our YAML and tries to run a local mcp-proxy
binary or Docker image. On success, exposes a local base URL for SSE endpoints.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from ..models.config import ToolGatingConfig, BackendServerConfig


class MCPProxyOrchestrator:
    def __init__(self, config_path: str, run_dir: Path) -> None:
        self.config_path = config_path
        self.run_dir = run_dir
        self.proc: Optional[subprocess.Popen] = None
        self.base_url = "http://127.0.0.1:9090"

    def build_proxy_config(self, cfg: ToolGatingConfig) -> Dict[str, Any]:
        servers: Dict[str, Any] = {}
        for name, s in cfg.backend_mcp_servers.items():
            if s.type == "stdio":
                entry: Dict[str, Any] = {
                    "command": s.command,
                    "args": s.args or [],
                    "env": s.env or {},
                }
                # Map tool filter if present
                if s.options and s.options.tool_filter and s.options.tool_filter.list:
                    mode = s.options.tool_filter.mode
                    # mcp-proxy uses allow/block wording in README; tolerate synonyms
                    mode_mapped = "allow" if mode == "allow" else ("block" if mode == "deny" else mode)
                    entry.setdefault("options", {})["toolFilter"] = {
                        "mode": mode_mapped,
                        "list": s.options.tool_filter.list,
                    }
                servers[name] = entry
            elif s.type in ("sse", "streamable-http"):
                entry: Dict[str, Any] = {"url": s.url}
                if s.headers:
                    entry["headers"] = s.headers
                servers[name] = entry
        proxy_conf = {
            "mcpProxy": {
                "addr": ":9090",
                "name": "MCP Proxy",
                "version": "1.0.0",
                "type": "sse",
                "options": {"logEnabled": True},
            },
            "mcpServers": servers,
        }
        return proxy_conf

    def write_config_file(self, data: Dict[str, Any]) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path = self.run_dir / "mcp_proxy_config.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def try_start(self, config_file: Path) -> bool:
        # Prefer native binary if available
        binary = shutil.which("mcp-proxy") or shutil.which("mcp_proxy")
        if binary:
            self.proc = subprocess.Popen([binary, "--config", str(config_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        # Try docker if present
        docker = shutil.which("docker")
        if docker:
            self.proc = subprocess.Popen([
                docker,
                "run",
                "-p",
                "9090:9090",
                "-v",
                f"{config_file}:/config/config.json",
                "ghcr.io/tbxark/mcp-proxy:latest",
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        return False

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.proc = None

