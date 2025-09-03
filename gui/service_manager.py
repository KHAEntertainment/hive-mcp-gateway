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

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread, QProcess
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
    
    def __init__(self):
        """Initialize service manager."""
        super().__init__()
        
        # Service configuration
        self.tool_gating_port = 8001  # Non-interfering port
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
                
                # Connect signals
                self.tool_gating_process.readyReadStandardOutput.connect(self._on_stdout)
                self.tool_gating_process.readyReadStandardError.connect(self._on_stderr)
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
            
            # Try graceful shutdown first
            if self.tool_gating_process and self.tool_gating_process.state() == QProcess.ProcessState.Running:
                self.tool_gating_process.terminate()
                
                # Wait for graceful shutdown
                if self.tool_gating_process.waitForFinished(10000):
                    logger.info("Hive MCP Gateway service stopped gracefully")
                else:
                    # Force kill if graceful shutdown fails
                    logger.warning("Graceful shutdown failed, force killing process")
                    self.tool_gating_process.kill()
                    self.tool_gating_process.waitForFinished(5000)
            
            # Clean up process tracking
            self.tool_gating_process = None
            self.tool_gating_pid = None
            
            # Verify service is stopped
            if not self.is_service_running():
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
        """Check if Hive MCP Gateway service is running."""
        # Check by process
        if self.tool_gating_process and self.tool_gating_process.state() == QProcess.ProcessState.Running:
            return True
        
        # Check by port
        return self._is_port_in_use(self.tool_gating_port)
    
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
        logs = []
        
        if self.tool_gating_process:
            # Get stdout and stderr from process
            stdout = self.tool_gating_process.readAllStandardOutput().data().decode()
            stderr = self.tool_gating_process.readAllStandardError().data().decode()
            
            if stdout:
                logs.extend(stdout.split('\n'))
            if stderr:
                logs.extend(stderr.split('\n'))
        
        # Return last N lines
        return logs[-lines:] if len(logs) > lines else logs
    
    def _get_start_command(self) -> Optional[List[str]]:
        """Get command to start the service."""
        # Method 1: Try to find tool-gating-mcp in PATH
        try:
            result = subprocess.run(["which", "tool-gating-mcp"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return ["tool-gating-mcp"]
        except:
            pass
        
        # Method 2: Run from current directory using uvicorn
        current_dir = Path.cwd()
        main_py = current_dir / "src" / "hive_mcp_gateway" / "main.py"
        
        if main_py.exists():
            return [
                "uvicorn", 
                "hive_mcp_gateway.main:app",
                "--host", "0.0.0.0",
                "--port", str(self.tool_gating_port),
                "--reload"
            ]
        
        # Method 3: Python module execution
        return [
            "python", "-m", "hive_mcp_gateway.main"
        ]
    
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
    
    def _on_process_finished(self):
        """Handle process finished event."""
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
            # Make HTTP request to get server statuses
            response = requests.get(f"http://localhost:{self.tool_gating_port}/api/mcp/servers", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get server statuses: {response.status_code}")
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
            
        try:
            # Call the API to reconnect the server
            # First make sure it's enabled
            response = requests.post(
                f"http://localhost:{self.tool_gating_port}/api/mcp/reconnect",
                json={"server_id": server_id},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully restarted server {server_id}")
                return True
            else:
                logger.error(f"Failed to restart server {server_id}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error restarting server {server_id}: {e}")
            return False
