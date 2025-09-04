"""Dependency checker for monitoring mcp-proxy and other critical dependencies."""

import logging
import subprocess
import time
import psutil
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread

logger = logging.getLogger(__name__)


@dataclass
class DependencyInfo:
    """Information about a dependency."""
    name: str
    path: Optional[str]
    version: Optional[str]
    is_running: bool
    port: Optional[int]
    process_id: Optional[int]
    last_check: datetime
    error_message: Optional[str] = None


class DependencyChecker(QObject):
    """Monitors critical dependencies for Hive MCP Gateway."""
    
    dependency_status_changed = pyqtSignal(str, bool)  # service_name, is_running
    
    def __init__(self):
        """Initialize dependency checker."""
        super().__init__()
        
        # Known dependency configurations
        self.dependencies = {
            "node": {
                "binary_name": "node",
                "description": "Node.js runtime for NPX-based MCP servers",
                "dependency_type": "runtime"
            },
            "npx": {
                "binary_name": "npx",
                "description": "NPX package runner for MCP servers",
                "dependency_type": "runtime"
            },
            "python": {
                "binary_name": "python3",
                "description": "Python runtime",
                "dependency_type": "runtime"
            },
            "uv": {
                "binary_name": "uv",
                "description": "Python package manager",
                "dependency_type": "build_tool"
            },
            "claude_desktop": {
                "binary_name": "Claude Desktop",
                "description": "Claude Desktop application",
                "dependency_type": "client"
            },
            "mcp-proxy": {
                "binary_name": "mcp-proxy",
                "description": "MCP Proxy supervisor (bundled or PATH)",
                "dependency_type": "runtime"
            }
        }
        
        # Status tracking
        self.dependency_status: Dict[str, DependencyInfo] = {}
        self.monitoring_active = False
        
        # Monitoring timer
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.check_all_dependencies)
        
        # Clean up any existing client entries from dependency status
        self._cleanup_client_entries()
        
        logger.info("Dependency checker initialized")
    
    def _cleanup_client_entries(self):
        """Remove client entries from dependency status to ensure they're not tracked as dependencies."""
        client_names = [
            name for name, config in self.dependencies.items()
            if config.get("dependency_type") == "client"
        ]
        
        for client_name in client_names:
            if client_name in self.dependency_status:
                del self.dependency_status[client_name]
                logger.info(f"Removed client '{client_name}' from dependency tracking")
    
    def check_all_dependencies(self) -> Dict[str, bool]:
        """Check all dependencies and return their status."""
        results = {}
        
        for name, config in self.dependencies.items():
            # Skip clients completely - they are not dependencies
            if config.get("dependency_type") == "client":
                continue
                
            try:
                is_running = self.check_binary_available(config["binary_name"])
                
                results[name] = is_running
                
                # Update stored status
                previous_status = self.dependency_status.get(name)
                current_status = DependencyInfo(
                    name=name,
                    path=self._find_dependency_path(name, config),
                    version=self._get_dependency_version(name, config),
                    is_running=is_running,
                    port=None,
                    process_id=self._get_process_id(name) if is_running else None,
                    last_check=datetime.now()
                )
                
                self.dependency_status[name] = current_status
                
                # Emit signal if status changed
                if previous_status is None or previous_status.is_running != is_running:
                    self.dependency_status_changed.emit(name, is_running)
                    
            except Exception as e:
                logger.error(f"Error checking dependency {name}: {e}")
                results[name] = False
                
                # Update with error
                self.dependency_status[name] = DependencyInfo(
                    name=name,
                    path=None,
                    version=None,
                    is_running=False,
                    port=None,
                    process_id=None,
                    last_check=datetime.now(),
                    error_message=str(e)
                )
        
        return results
    
    def get_actual_dependencies(self) -> Dict[str, DependencyInfo]:
        """Get only actual dependencies, excluding clients."""
        return {
            name: info for name, info in self.dependency_status.items()
            if name in self.dependencies and self.dependencies[name].get("dependency_type") != "client"
        }
    
    def check_binary_available(self, binary_name: str) -> bool:
        """Check if a binary is available in PATH."""
        try:
            # Special handling for mcp-proxy: check bundled paths as well
            if binary_name == "mcp-proxy":
                try:
                    proj_root = Path(__file__).resolve().parent.parent
                    candidates = [
                        proj_root / "dist" / "ToolGatingMCP.app" / "Contents" / "Resources" / "bin" / "mcp-proxy",
                        proj_root / "Resources" / "bin" / "mcp-proxy",
                        proj_root / "bin" / "mcp-proxy",
                        proj_root / "run" / "bin" / "mcp-proxy",
                    ]
                    for c in candidates:
                        if c.exists():
                            return True
                except Exception:
                    pass
            result = subprocess.run(
                ["which", binary_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Binary {binary_name} not found: {e}")
            return False
    
    def get_dependency_info(self, service_name: str) -> Optional[DependencyInfo]:
        """Get detailed information about a dependency."""
        return self.dependency_status.get(service_name)
    
    def start_dependency_monitoring(self) -> None:
        """Start continuous dependency monitoring."""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitor_timer.start(30000)  # Check every 30 seconds
            logger.info("Started dependency monitoring")
            
            # Do initial check
            self.check_all_dependencies()
    
    def stop_dependency_monitoring(self) -> None:
        """Stop dependency monitoring."""
        if self.monitoring_active:
            self.monitoring_active = False
            self.monitor_timer.stop()
            logger.info("Stopped dependency monitoring")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information for diagnostics."""
        try:
            return {
                "platform": "macOS" if psutil.MACOS else "Windows" if psutil.WINDOWS else "Linux" if psutil.LINUX else "Unknown",
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {}
    

    
    def get_installation_guidance(self, dependency_name: str) -> Dict[str, Any]:
        """Get installation guidance for a missing dependency."""
        guidance = {
            "name": dependency_name,
            "description": "",
            "methods": [],
            "commands": [],
            "links": []
        }
        
        if dependency_name == "node":
            guidance.update({
                "description": "Node.js runtime is required for NPX-based MCP servers.",
                "methods": [
                    "Install via Node Version Manager (recommended)",
                    "Download from official website",
                    "Install via package manager"
                ],
                "commands": [
                    "# Method 1: Install via NVM (recommended)",
                    "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash",
                    "nvm install node",
                    "",
                    "# Method 2: Install via Homebrew (macOS)",
                    "brew install node",
                    "",
                    "# Method 3: Download from website",
                    "# Visit https://nodejs.org and download LTS version"
                ],
                "links": [
                    "https://nodejs.org",
                    "https://github.com/nvm-sh/nvm"
                ]
            })
        
        elif dependency_name == "uv":
            guidance.update({
                "description": "uv is a fast Python package manager and project manager.",
                "methods": [
                    "Install via curl (recommended)",
                    "Install via pip",
                    "Install via Homebrew"
                ],
                "commands": [
                    "# Method 1: Install via curl (recommended)",
                    "curl -LsSf https://astral.sh/uv/install.sh | sh",
                    "",
                    "# Method 2: Install via pip",
                    "pip install uv",
                    "",
                    "# Method 3: Install via Homebrew (macOS)",
                    "brew install uv"
                ],
                "links": [
                    "https://docs.astral.sh/uv/",
                    "https://github.com/astral-sh/uv"
                ]
            })
        
        return guidance
    
    def _find_binary_path(self, binary_name: str) -> Optional[str]:
        """Find the full path to a binary."""
        try:
            result = subprocess.run(
                ["which", binary_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
    
    def _get_binary_version(self, binary_name: str) -> Optional[str]:
        """Get version of a binary."""
        try:
            # Try common version flags
            for flag in ["--version", "-v", "-V", "version"]:
                try:
                    result = subprocess.run(
                        [binary_name, flag],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        # Extract version from output
                        output = result.stdout.strip()
                        if output:
                            return output.split('\n')[0]  # First line
                except Exception:
                    continue
        except Exception:
            pass
        return None
    
    def _get_process_id(self, service_name: str) -> Optional[int]:
        """Get process ID for a service."""
        try:
            # No special process ID handling needed for current dependencies
            pass
        except Exception as e:
            logger.error(f"Error getting process ID for {service_name}: {e}")
        
        return None
    
    def _find_dependency_path(self, dep_name: str, config: dict) -> Optional[str]:
        """Find the path to a dependency."""
        try:
            # Regular binary
            binary_name = config.get("binary_name")
            if binary_name:
                # For mcp-proxy, also return bundled path if found
                if binary_name == "mcp-proxy":
                    try:
                        proj_root = Path(__file__).resolve().parent.parent
                        candidates = [
                            proj_root / "dist" / "ToolGatingMCP.app" / "Contents" / "Resources" / "bin" / "mcp-proxy",
                            proj_root / "Resources" / "bin" / "mcp-proxy",
                            proj_root / "bin" / "mcp-proxy",
                            proj_root / "run" / "bin" / "mcp-proxy",
                        ]
                        for c in candidates:
                            if c.exists():
                                return str(c)
                    except Exception:
                        pass
                return self._find_binary_path(binary_name)
                
        except Exception as e:
            logger.error(f"Error finding path for {dep_name}: {e}")
        
        return None
    
    def _get_dependency_version(self, dep_name: str, config: dict) -> Optional[str]:
        """Get version of a dependency."""
        try:
            # Regular binary version
            binary_name = config.get("binary_name")
            if binary_name:
                return self._get_binary_version(binary_name)
                
        except Exception as e:
            logger.error(f"Error getting version for {dep_name}: {e}")
        
        return None
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use using socket connection test."""
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                return result == 0
        except Exception:
            return False


class DependencyMonitorThread(QThread):
    """Background thread for continuous dependency monitoring."""
    
    status_update = pyqtSignal(dict)
    
    def __init__(self, dependency_checker: DependencyChecker):
        super().__init__()
        self.dependency_checker = dependency_checker
        self.running = True
        self.check_interval = 30  # seconds
    
    def run(self):
        """Monitor dependencies in background."""
        while self.running:
            try:
                # Check all dependencies
                status = self.dependency_checker.check_all_dependencies()
                
                # Get detailed info
                detailed_status = {}
                for name in status.keys():
                    detailed_status[name] = self.dependency_checker.get_dependency_info(name)
                
                # Emit update
                self.status_update.emit({
                    "status": status,
                    "detailed": detailed_status,
                    "timestamp": datetime.now(),
                    "system_info": self.dependency_checker.get_system_info()
                })
                
                # Sleep for check interval
                self.msleep(self.check_interval * 1000)
                
            except Exception as e:
                logger.error(f"Error in dependency monitor thread: {e}")
                self.msleep(5000)  # Sleep 5 seconds on error
    
    def stop(self):
        """Stop monitoring."""
        self.running = False
        self.wait()
