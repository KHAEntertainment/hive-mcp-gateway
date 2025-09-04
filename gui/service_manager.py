"""Service manager for Hive MCP Gateway backend service control and mcp-proxy monitoring."""

import subprocess
import psutil
import logging
import signal
import time
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread, QProcess, QProcessEnvironment
from PyQt6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


@dataclass
class ServiceStatus:
    """Service status information."""
    name: str
    is_running: bool
    pid: Optional[int] = None
    port: Optional[int] = None
    start_time: Optional[datetime] = None
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None
    last_check: Optional[datetime] = None


class ServiceManager(QObject):
    """Manages Hive MCP Gateway backend service and monitors mcp-proxy."""
    
    # Signals for status updates
    status_changed = pyqtSignal(str)  # Service status signal
    log_message = pyqtSignal(str)     # Log message signal
    
    def __init__(self, config_manager: Optional["ConfigManager"] = None):
        """Initialize service manager.

        Args:
            config_manager: Optional shared ConfigManager to read runtime settings (e.g., port).
        """
        super().__init__()

        # Hold a reference to the config manager if provided (lazy import type)
        self._config_manager = config_manager

        # Service configuration
        self.tool_gating_port = 8001  # Default; may be overridden by config
        # Prefer configured port if available
        try:
            if self._config_manager is not None:
                cfg = self._config_manager.load_config()
                if getattr(cfg, "tool_gating", None) and getattr(cfg.tool_gating, "port", None):
                    self.tool_gating_port = int(cfg.tool_gating.port)
        except Exception as e:
            logger.debug(f"Could not load configured port from config manager: {e}")
        self.mcp_proxy_port = 9090
        self.mcp_proxy_path = Path("/Users/bbrenner/hive-mcp-gateway")
        
        # Process tracking
        self.tool_gating_process: Optional[QProcess] = None
        self.tool_gating_pid: Optional[int] = None
        
        # Status monitoring
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.check_service_status)
        self.status_timer.start(5000)  # Check every 5 seconds

        logger.info("Service manager initialized")
        # Diagnostics for banner updates
        self.last_api_base: Optional[str] = None
        self.last_status_error: Optional[str] = None
    
    def start_service(self) -> bool:
        """Start the Hive MCP Gateway backend service."""
        try:
            if self.is_service_running():
                logger.warning("Hive MCP Gateway service is already running")
                return True

            # Prepare command to start the service
            # If configured port is occupied, find a temporary free port (do not persist)
            try:
                if self._is_port_in_use(self.tool_gating_port):
                    original_port = self.tool_gating_port
                    fallback_port = self._find_available_port(start_port=original_port, tries=10)
                    if fallback_port is None:
                        logger.error(
                            f"No available port found near {original_port}. Unable to start service."
                        )
                        self.status_changed.emit("error")
                        return False
                    # Use fallback runtime port
                    self.tool_gating_port = fallback_port
                    msg = (
                        f"Configured port {original_port} is in use. "
                        f"Starting temporarily on {fallback_port} (GUI will continue to show configured port)."
                    )
                    logger.info(msg)
                    try:
                        self.log_message.emit(msg)
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"Port availability check failed: {e}")

            cmd = self._get_start_command()
            
            if not cmd:
                logger.error("Failed to determine start command")
                return False
            
            # Start the process
            self.tool_gating_process = QProcess()
            
            if self.tool_gating_process: # Add check here
                self.tool_gating_process.setProgram(cmd[0])
                self.tool_gating_process.setArguments(cmd[1:])

                # Ensure working directory is project root (where config/ lives)
                try:
                    project_root = Path(__file__).resolve().parent.parent
                    if (project_root / "config").exists():
                        self.tool_gating_process.setWorkingDirectory(str(project_root))
                except Exception:
                    pass

                # Inject environment for explicit host/config (avoid forcing PORT to allow backend fallback)
                try:
                    env = QProcessEnvironment.systemEnvironment()
                    env.insert("CONFIG_PATH", "config/tool_gating_config.yaml")
                    env.insert("HOST", "0.0.0.0")
                    env.insert("LOG_LEVEL", "info")
                    self.tool_gating_process.setProcessEnvironment(env)
                except Exception:
                    pass
                
                # Connect signals
                self.tool_gating_process.readyReadStandardOutput.connect(self._on_stdout)
                self.tool_gating_process.readyReadStandardError.connect(self._on_stderr)
                # Capture exit code/status for debugging
                try:
                    self.tool_gating_process.finished[int, QProcess.ExitStatus].connect(self._on_process_finished)
                except Exception:
                    # Fallback: connect without explicit signature
                    self.tool_gating_process.finished.connect(self._on_process_finished)
                
                # Start the process
                self.tool_gating_process.start()
                
                if self.tool_gating_process.waitForStarted(5000):
                    self.tool_gating_pid = self.tool_gating_process.processId()
                    logger.info(f"Started Hive MCP Gateway service (PID: {self.tool_gating_pid})")
                    # Inform which port we're using at runtime
                    try:
                        self.log_message.emit(f"Service running on http://localhost:{self.tool_gating_port}")
                    except Exception:
                        pass
                    self.status_changed.emit("running")
                    return True
                else:
                    logger.error("Failed to start Hive MCP Gateway service")
                    self.status_changed.emit("error")
                    return False
            else:
                logger.error("Failed to create QProcess object.")
                self.status_changed.emit("error")
                return False
                
        except Exception as e:
            logger.error(f"Error starting service: {e}")
            self.status_changed.emit("error")
            return False
    
    def stop_service(self) -> bool:
        """Stop the Hive MCP Gateway backend service."""
        try:
            if not self.is_service_running():
                logger.info("Hive MCP Gateway service is not running")
                self.status_changed.emit("stopped")
                return True
            
            stopped = False
            # If we own the process, try QProcess first
            if self.tool_gating_process and self.tool_gating_process.state() == QProcess.ProcessState.Running:
                self.tool_gating_process.terminate()
                if self.tool_gating_process.waitForFinished(8000):
                    logger.info("Hive MCP Gateway service stopped gracefully")
                    stopped = True
                else:
                    logger.warning("Graceful shutdown failed, force killing process")
                    self.tool_gating_process.kill()
                    self.tool_gating_process.waitForFinished(4000)
                    stopped = True
                self.tool_gating_process = None
                self.tool_gating_pid = None
            else:
                # Attempt PID-file-based shutdown when we don't own the process
                try:
                    proj_root = Path(__file__).resolve().parent.parent
                    pid_path = proj_root / 'run' / 'backend.pid'
                    if pid_path.exists():
                        pid = int(pid_path.read_text().strip())
                        import os, signal, time as _time
                        logger.info(f"Attempting to terminate backend PID {pid} from PID file")
                        os.kill(pid, signal.SIGTERM)
                        # wait up to 10s
                        for _ in range(20):
                            try:
                                os.kill(pid, 0)
                                _time.sleep(0.5)
                            except OSError:
                                stopped = True
                                break
                        if not stopped:
                            logger.warning("SIGTERM failed, sending SIGKILL")
                            try:
                                os.kill(pid, signal.SIGKILL)
                                stopped = True
                            except Exception as e:
                                logger.error(f"SIGKILL failed: {e}")
                        # cleanup pid file
                        try:
                            pid_path.unlink()
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"PID-file stop failed: {e}")
            
            # Verify service is stopped
            if stopped or not self.is_service_running():
                logger.info("Hive MCP Gateway service stopped successfully")
                self.status_changed.emit("stopped")
                return True
            else:
                logger.error("Failed to stop Hive MCP Gateway service")
                self.status_changed.emit("error")
                return False
                
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
            self.status_changed.emit("error")
            return False
    
    def restart_service(self) -> bool:
        """Restart the Hive MCP Gateway backend service."""
        logger.info("Restarting Hive MCP Gateway service...")
        
        # Stop the service
        if not self.stop_service():
            return False
        
        # Wait a moment for cleanup
        time.sleep(2)
        
        # Start the service
        return self.start_service()
    
    def is_service_running(self) -> bool:
        """Check if Hive MCP Gateway service is running.

        Detects a running server on the configured port first, then falls back to common defaults.
        Updates the active port if it finds the server on an alternate port.
        """
        # Check by process
        if self.tool_gating_process and self.tool_gating_process.state() == QProcess.ProcessState.Running:
            return True

        # Probe candidate ports
        # If backend wrote a selected port file, prefer it first
        try:
            port_file = Path(__file__).resolve().parent.parent / "run" / "hmg_port"
            if port_file.exists():
                contents = port_file.read_text(encoding="utf-8").strip()
                if contents.isdigit():
                    hinted = int(contents)
                    if hinted and hinted != self.tool_gating_port:
                        self.tool_gating_port = hinted
        except Exception:
            pass
        
        for port in self._candidate_ports():
            if self._is_port_in_use(port):
                if port != self.tool_gating_port:
                    logger.info(f"Detected running backend on port {port}; updating ServiceManager port")
                    self.tool_gating_port = port
                return True
        return False
    
    def get_service_status(self) -> ServiceStatus:
        """Get detailed service status information."""
        is_running = self.is_service_running()
        
        status = ServiceStatus(
            name="hive-mcp-gateway",
            is_running=is_running,
            port=self.tool_gating_port,
            last_check=datetime.now()
        )
        
        if is_running and self.tool_gating_pid:
            try:
                process = psutil.Process(self.tool_gating_pid)
                status.pid = self.tool_gating_pid
                status.start_time = datetime.fromtimestamp(process.create_time())
                status.memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                status.cpu_usage = process.cpu_percent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process no longer exists
                self.tool_gating_pid = None
                status.is_running = False
        
        return status
    
    def get_service_logs(self, lines: int = 100) -> List[str]:
        """Get recent service logs."""
        logs: List[str] = []
        # Prefer live QProcess buffers if we own the process
        try:
            if self.tool_gating_process and self.tool_gating_process.state() == QProcess.ProcessState.Running:
                stdout = self.tool_gating_process.readAllStandardOutput().data().decode()
                stderr = self.tool_gating_process.readAllStandardError().data().decode()
                if stdout:
                    logs.extend(stdout.split('\n'))
                if stderr:
                    logs.extend(stderr.split('\n'))
        except Exception:
            pass
        # Fallback: tail run/backend.log if present (when GUI didn't spawn process)
        try:
            project_root = Path(__file__).resolve().parent.parent
            log_path = project_root / "run" / "backend.log"
            if log_path.exists():
                content = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                logs = content if not logs else (logs + ["", "--- tail backend.log ---", *content[-lines:]])
        except Exception:
            pass
        # HTTP fallback if file read produced nothing
        if not logs and self.is_service_running():
            try:
                # Use last known base if set
                bases: List[str] = []
                if self.last_api_base:
                    bases.append(self.last_api_base)
                bases.extend([
                    f"http://localhost:{self.tool_gating_port}",
                    f"http://127.0.0.1:{self.tool_gating_port}",
                ])
                for base in bases:
                    try:
                        resp = requests.get(f"{base}/api/mcp/logs", params={"lines": lines}, timeout=5)
                        if resp.status_code == 200:
                            data = resp.json() or {}
                            arr = data.get("lines") or []
                            if arr:
                                self.last_api_base = base
                                return arr
                    except Exception:
                        continue
            except Exception:
                pass
        return logs[-lines:] if len(logs) > lines else logs

    def get_proxy_status(self) -> Optional[Dict[str, Any]]:
        """Get proxy status from backend API."""
        if not self.is_service_running():
            return None
        try:
            for port in self._candidate_ports():
                for host in ("localhost", "127.0.0.1"):
                    base = f"http://{host}:{port}"
                    try:
                        resp = requests.get(f"{base}/api/mcp/proxy_status", timeout=3)
                        if resp.status_code == 200:
                            self.last_api_base = base
                            return resp.json()
                    except Exception:
                        continue
        except Exception:
            return None
        return None
    
    def _get_start_command(self) -> Optional[List[str]]:
        """Get command to start the service.

        Prefer the current interpreter and module execution for stability.
        """
        # Method 1: Dedicated CLI if available
        try:
            result = subprocess.run(["which", "tool-gating-mcp"], capture_output=True, text=True)
            if result.returncode == 0:
                return ["tool-gating-mcp"]
        except Exception:
            pass

        # Method 2: Python module execution with current interpreter
        try:
            import sys
            return [sys.executable, "-m", "hive_mcp_gateway.main"]
        except Exception:
            return ["python", "-m", "hive_mcp_gateway.main"]
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use using socket connection test."""
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                return result == 0
        except Exception as e:
            logger.error(f"Error checking port {port}: {e}")
            return False

    def _find_available_port(self, start_port: int, tries: int = 10) -> Optional[int]:
        """Find an available port starting from start_port, trying sequentially.

        Returns the first free port number, or None if none found within range.
        """
        try:
            import socket
            for port in range(start_port, start_port + max(1, tries)):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    if s.connect_ex(("127.0.0.1", port)) != 0:
                        return port
        except Exception as e:
            logger.debug(f"Failed to probe for free port near {start_port}: {e}")
        return None

    def _candidate_ports(self) -> List[int]:
        """Return a short list of candidate ports to probe for the backend.

        Policy: prefer current/configured port, then 8001, then 8002-8025.
        """
        candidates: List[int] = []
        # Current runtime port first
        if self.tool_gating_port:
            candidates.append(self.tool_gating_port)
        # Configured port if different
        try:
            if self._config_manager is not None:
                cfg = self._config_manager.load_config()
                cfg_port = int(getattr(getattr(cfg, "tool_gating", object()), "port", 0) or 0)
                if cfg_port and cfg_port not in candidates:
                    candidates.append(cfg_port)
        except Exception:
            pass
        # Default and fallback range
        if 8001 not in candidates:
            candidates.append(8001)
        for p in range(8002, 8026):
            if p not in candidates:
                candidates.append(p)
        return candidates
    
    def _on_stdout(self):
        """Handle stdout from the process."""
        if self.tool_gating_process:
            data = self.tool_gating_process.readAllStandardOutput().data()
            if data:
                message = data.decode().strip()
                if message:
                    self.log_message.emit(message)
    
    def _on_stderr(self):
        """Handle stderr from the process."""
        if self.tool_gating_process:
            data = self.tool_gating_process.readAllStandardError().data()
            if data:
                message = data.decode().strip()
                if message:
                    self.log_message.emit(f"ERROR: {message}")
    
    def _on_process_finished(self, exit_code: int = 0, exit_status=None):
        """Handle process finished event with diagnostics."""
        try:
            logger.info(
                f"Hive MCP Gateway service process finished (exit_code={exit_code}, exit_status={exit_status})"
            )
        except Exception:
            logger.info("Hive MCP Gateway service process finished")
        self.tool_gating_process = None
        self.tool_gating_pid = None
        self.status_changed.emit("stopped")
    
    def check_service_status(self):
        """Periodic status check (called by timer)."""
        try:
            current_running = self.is_service_running()
            
            # Emit status change if needed
            if current_running:
                self.status_changed.emit("running")
            else:
                self.status_changed.emit("stopped")
                
        except Exception as e:
            logger.error(f"Error in status check: {e}")
    
    def get_server_statuses(self) -> List[Dict[str, Any]]:
        """
        Get server statuses from the running service.
        
        Returns:
            List of server status dictionaries, or empty list if service is not running
        """
        if not self.is_service_running():
            return []
        
        try:
            # Try candidate ports and return the first successful response
            for port in self._candidate_ports():
                for host in ("localhost", "127.0.0.1"):
                    base = f"http://{host}:{port}"
                    try:
                        response = requests.get(f"{base}/api/mcp/servers", timeout=5)
                        if response.status_code == 200:
                            if port != self.tool_gating_port:
                                self.tool_gating_port = port
                            self.last_api_base = base
                            self.last_status_error = None
                            return response.json()
                    except Exception:
                        continue

            logger.warning("Failed to get server statuses from all candidate URLs")
            self.last_status_error = "No reachable /api/mcp/servers"
            return []
        except Exception as e:
            logger.error(f"Error getting server statuses: {e}")
            return []
    
    def restart_backend_server(self, server_id: str) -> bool:
        """
        Restart a specific backend MCP server.
        
        Args:
            server_id (str): ID of the server to restart
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_service_running():
            logger.error(f"Cannot restart server {server_id}: service not running")
            return False

        # Call the API to reconnect the server using discovered/active port
        try:
            bases: List[str] = []
            if self.last_api_base:
                bases.append(self.last_api_base)
            bases.extend([
                f"http://localhost:{self.tool_gating_port}",
                f"http://127.0.0.1:{self.tool_gating_port}",
            ])
            for base in bases:
                try:
                    resp = requests.post(
                        f"{base}/api/mcp/reconnect",
                        json={"server_id": server_id},
                        timeout=20,
                    )
                    if resp.status_code == 200:
                        logger.info(f"Successfully reconnected server {server_id}")
                        self.last_api_base = base
                        return True
                    else:
                        try:
                            logger.error(f"Reconnect {server_id} via {base} failed: {resp.status_code} {resp.text}")
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug(f"Reconnect via {base} failed: {e}")
                    continue
            logger.error(f"Failed to reconnect server {server_id} on all candidate bases")
            return False
        except Exception as e:
            logger.error(f"Error restarting server {server_id}: {e}")
            return False

    def reconnect_all_servers(self) -> bool:
        """Reconnect all backend MCP servers via the API.

        Returns True if at least one reconnect succeeded.
        """
        if not self.is_service_running():
            logger.error("Cannot reconnect servers: service not running")
            return False

        try:
            statuses = self.get_server_statuses()
            if not statuses:
                return False

            any_success = False
            for st in statuses:
                name = st.get("name")
                if not name:
                    continue
                try:
                    ok = self.restart_backend_server(name)
                    any_success = any_success or ok
                except Exception as e:
                    logger.error(f"Error reconnecting {name}: {e}")
            return any_success
        except Exception as e:
            logger.error(f"Error reconnecting all servers: {e}")
            return False

    def discover_tools(self, server_id: str) -> bool:
        """Call API to force discovery of tools for a server."""
        if not self.is_service_running():
            logger.error("Cannot discover tools: service not running")
            return False
        try:
            bases: List[str] = []
            if self.last_api_base:
                bases.append(self.last_api_base)
            bases.extend([
                f"http://localhost:{self.tool_gating_port}",
                f"http://127.0.0.1:{self.tool_gating_port}",
            ])
            for base in bases:
                try:
                    resp = requests.post(
                        f"{base}/api/mcp/discover_tools",
                        json={"server_id": server_id},
                        timeout=20,
                    )
                    if resp.status_code == 200:
                        logger.info(f"Discover tools succeeded for {server_id}")
                        self.last_api_base = base
                        return True
                    else:
                        try:
                            logger.error(f"Discover tools {server_id} via {base} failed: {resp.status_code} {resp.text}")
                        except Exception:
                            pass
                except Exception:
                    continue
            logger.error("Failed to discover tools on all candidate bases")
            return False
        except Exception as e:
            logger.error(f"Error discovering tools for {server_id}: {e}")
            return False
