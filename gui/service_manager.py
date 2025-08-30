"""Service manager for Hive MCP Gateway backend service control and mcp-proxy monitoring."""

import subprocess
import psutil
import logging
import signal
import time
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
            cmd = self._get_start_command()
            
            if not cmd:
                logger.error("Failed to determine start command")
                return False
            
            # Start the process
            self.tool_gating_process = QProcess()
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
                self.status_changed.emit("running")
                return True
            else:
                logger.error("Failed to start Hive MCP Gateway service")
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
        return logs[-lines:] if logs else ["No logs available"]
    
    def check_mcp_proxy_status(self) -> bool:
        """Check if mcp-proxy service is running."""
        return self._is_port_in_use(self.mcp_proxy_port)
    
    def start_mcp_proxy(self) -> bool:
        """Start mcp-proxy service (if not running)."""
        try:
            if self.check_mcp_proxy_status():
                logger.info("mcp-proxy is already running")
                return True
            
            # Try to start mcp-proxy from the known installation
            mcp_proxy_binary = self.mcp_proxy_path / "mcp-proxy"
            
            if not mcp_proxy_binary.exists():
                logger.error(f"mcp-proxy binary not found at {mcp_proxy_binary}")
                return False
            
            # Start mcp-proxy in background
            cmd = [str(mcp_proxy_binary)]
            
            # Look for config file
            config_file = self.mcp_proxy_path / "config.json"
            if config_file.exists():
                cmd.extend(["--config", str(config_file)])
            
            subprocess.Popen(cmd, cwd=str(self.mcp_proxy_path))
            
            # Give it time to start
            time.sleep(3)
            
            return self.check_mcp_proxy_status()
            
        except Exception as e:
            logger.error(f"Failed to start mcp-proxy: {e}")
            return False
    
    def get_mcp_proxy_logs(self) -> List[str]:
        """Get mcp-proxy logs if available."""
        log_file = self.mcp_proxy_path / "mcp-proxy.log"
        
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    return [line.strip() for line in lines[-100:]]  # Last 100 lines
            except Exception as e:
                logger.error(f"Failed to read mcp-proxy logs: {e}")
        
        return ["No logs available"]
    
    def check_service_status(self):
        """Periodic status check (called by timer)."""
        try:
            current_running = self.is_service_running()
            
            # Emit status change if needed
            if current_running:
                self.status_changed.emit("running")
            else:
                if self.tool_gating_process:
                    self.status_changed.emit("stopped")
        
        except Exception as e:
            logger.error(f"Error during status check: {e}")
            self.status_changed.emit("error")
    
    def _get_start_command(self) -> List[str]:
        """Get the command to start the Hive MCP Gateway service."""
        # Try to find the hive-mcp-gateway command in PATH
        result = subprocess.run(["which", "hive-mcp-gateway"], 
                              capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return ["hive-mcp-gateway"]
        
        # Try to determine the best way to start the service
        
        # Method 1: Check if installed as package
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
    
    def _on_stdout(self):
        """Handle process stdout."""
        if self.tool_gating_process:
            data = self.tool_gating_process.readAllStandardOutput().data().decode()
            for line in data.strip().split('\n'):
                if line.strip():
                    self.log_message.emit(f"STDOUT: {line}")
    
    def _on_stderr(self):
        """Handle process stderr."""
        if self.tool_gating_process:
            data = self.tool_gating_process.readAllStandardError().data().decode()
            for line in data.strip().split('\n'):
                if line.strip():
                    self.log_message.emit(f"STDERR: {line}")
    
    def _on_process_finished(self, exit_code: int):
        """Handle process termination."""
        logger.info(f"Hive MCP Gateway process finished with exit code: {exit_code}")
        self.tool_gating_process = None
        self.tool_gating_pid = None
        self.status_changed.emit("stopped")


class ProcessMonitor(QThread):
    """Background thread for monitoring process status."""
    
    status_update = pyqtSignal(dict)
    
    def __init__(self, service_manager: ServiceManager):
        super().__init__()
        self.service_manager = service_manager
        self.running = True
    
    def run(self):
        """Monitor processes in background."""
        while self.running:
            try:
                status_info = {
                    "tool_gating": self.service_manager.get_service_status(),
                    "mcp_proxy": self.service_manager.check_mcp_proxy_status(),
                    "timestamp": datetime.now()
                }
                
                self.status_update.emit(status_info)
                
                # Sleep for 10 seconds
                self.msleep(10000)
                
            except Exception as e:
                logger.error(f"Error in process monitor: {e}")
                self.msleep(5000)
    
    def stop(self):
        """Stop monitoring."""
        self.running = False
        self.wait()
