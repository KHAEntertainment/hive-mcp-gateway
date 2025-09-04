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

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def reload(self, config_file: Path) -> bool:
        """Reload proxy config by restarting the process with the new config.

        mcp-proxy does not advertise hot-reload; we perform a fast restart.
        """
        # Stop existing process if running
        if self.is_running():
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.proc = None
        # Start again with new config
        return self.try_start(config_file)

    def update_config(self, cfg: ToolGatingConfig) -> bool:
        """Rebuild and apply a new proxy configuration.

        Returns True if proxy is running after update, False otherwise.
        """
        data = self.build_proxy_config(cfg)
        conf_file = self.write_config_file(data)
        if self.is_running():
            return self.reload(conf_file)
        else:
            return self.try_start(conf_file)

    def try_start(self, config_file: Path) -> bool:
        # Prefer bundled binary if available
        possible: list[Path] = []
        try:
            proj_root = Path(__file__).resolve().parents[2]
            possible.extend([
                proj_root / "Resources" / "bin" / "mcp-proxy",
                proj_root / "Resources" / "bin" / "mcp_proxy",
                proj_root / "bin" / "mcp-proxy",
                proj_root / "bin" / "mcp_proxy",
                self.run_dir / "bin" / "mcp-proxy",
                self.run_dir / "bin" / "mcp_proxy",
            ])
        except Exception:
            pass
        for p in possible:
            if p.exists():
                self.proc = subprocess.Popen([str(p), "--config", str(config_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return self._await_ready()
        # Then try PATH
        binary = shutil.which("mcp-proxy") or shutil.which("mcp_proxy")
        if binary:
            self.proc = subprocess.Popen([binary, "--config", str(config_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return self._await_ready()
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
            return self._await_ready()
        return False

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.proc = None

    # Internal helpers
    def _port_open(self, host: str = "127.0.0.1", port: int = 9090, timeout: float = 0.5) -> bool:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0

    def _await_ready(self, retries: int = 20, delay: float = 0.5) -> bool:
        """Wait for proxy to be fully functional, not just port binding.
        
        Performs multi-phase verification:
        1. Process is running
        2. Port is open
        3. HTTP service responds (health check or basic probe)
        """
        import time
        import urllib.request
        import urllib.error
        
        self.last_error = None
        
        for attempt in range(max(1, retries)):
            # Phase 1: Check process is still running
            if self.proc is None or self.proc.poll() is not None:
                self.last_error = "PROC_DIED: Proxy process terminated unexpectedly"
                if self.proc and self.proc.stderr:
                    try:
                        stderr_output = self.proc.stderr.read(1000).decode('utf-8', errors='ignore')
                        if stderr_output:
                            self.last_error += f" - stderr: {stderr_output[:200]}"
                    except:
                        pass
                self._cleanup_proc()
                return False
            
            # Phase 2: Check port is open
            if not self._port_open():
                if attempt == retries - 1:
                    self.last_error = "PORT_TIMEOUT: Port 9090 not available after 10s"
                time.sleep(delay)
                continue
            
            # Phase 3: Functional verification via HTTP
            try:
                # Try health endpoint first
                for endpoint in ['/health', '/status', '/', '/servers']:
                    try:
                        url = f"http://127.0.0.1:9090{endpoint}"
                        req = urllib.request.Request(url, method='GET')
                        with urllib.request.urlopen(req, timeout=2) as resp:
                            # Any HTTP response (200, 404, etc) means proxy is responding
                            if resp.status in [200, 404, 501]:
                                return True
                    except urllib.error.HTTPError as e:
                        # HTTP errors still mean the proxy is responding
                        if e.code in [404, 501, 405]:
                            return True
                    except:
                        continue
            except Exception as e:
                if attempt == retries - 1:
                    self.last_error = f"HTTP_CHECK_FAILED: Proxy not responding to HTTP after {retries * delay}s"
            
            time.sleep(delay)
        
        # Not ready after all retries
        self.last_error = self.last_error or f"TIMEOUT: Proxy readiness check timed out after {retries * delay}s"
        self._cleanup_proc()
        return False
    
    def _cleanup_proc(self):
        """Clean up the proxy process."""
        try:
            if self.proc:
                self.proc.terminate()
        except Exception:
            pass
        self.proc = None
    
    def get_last_error(self) -> Optional[str]:
        """Get the last error message from startup/readiness checks."""
        return getattr(self, 'last_error', None)
