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
            "mcp-proxy": {
                "port": 9090,
                "install_paths": [
                    # Current working directory and common project locations
                    Path.cwd(),
                    Path.cwd().parent,
                    Path.home() / "Documents/Scripting Projects/tool-gating-mcp",
                    Path("/Users/bbrenner/Documents/Scripting Projects/tool-gating-mcp"),
                    # Standard installation paths
                    Path.home() / ".local/bin",
                    Path("/usr/local/bin"),
                    Path("/opt/homebrew/bin"),
                    # NPM global installation paths
                    Path.home() / ".npm/bin",
                    Path("/usr/local/lib/node_modules/@anthropic/mcp-proxy/bin"),
                    # Cargo installation paths
                    Path.home() / ".cargo/bin"
                ],
                "binary_name": "mcp-proxy",
                "description": "MCP proxy service for Claude Desktop integration"
            },
            "claude-desktop": {
                "app_paths": [
                    Path("/Applications/Claude.app"),
                    Path.home() / "Applications/Claude.app",
                    # Additional possible locations
                    Path("/System/Applications/Claude.app"),
                    Path("/Applications/Utilities/Claude.app")
                ],
                "config_path": Path.home() / "Library/Application Support/Claude/claude_desktop_config.json",
                "process_names": ["Claude", "claude", "Claude Desktop"],
                "description": "Claude Desktop application"
            },
            "node": {
                "binary_name": "node",
                "description": "Node.js runtime for NPX-based MCP servers"
            },
            "npx": {
                "binary_name": "npx",
                "description": "NPX package runner for MCP servers"
            },
            "python": {
                "binary_name": "python3",
                "description": "Python runtime"
            },
            "uv": {
                "binary_name": "uv",
                "description": "Python package manager"
            }
        }
        
        # Status tracking
        self.dependency_status: Dict[str, DependencyInfo] = {}
        self.monitoring_active = False
        
        # Monitoring timer
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.check_all_dependencies)
        
        logger.info("Dependency checker initialized")
    
    def check_all_dependencies(self) -> Dict[str, bool]:
        """Check all dependencies and return their status."""
        results = {}
        
        for name, config in self.dependencies.items():
            try:
                if name == "mcp-proxy":
                    is_running = self.check_mcp_proxy()
                elif name == "claude-desktop":
                    is_running = self.check_claude_desktop()
                else:
                    is_running = self.check_binary_available(config["binary_name"])
                
                results[name] = is_running
                
                # Update stored status
                previous_status = self.dependency_status.get(name)
                current_status = DependencyInfo(
                    name=name,
                    path=self._find_dependency_path(name, config),
                    version=self._get_dependency_version(name, config),
                    is_running=is_running,
                    port=config.get("port"),
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
                    port=config.get("port"),
                    process_id=None,
                    last_check=datetime.now(),
                    error_message=str(e)
                )
        
        return results
    
    def check_mcp_proxy(self) -> bool:
        """Check if mcp-proxy service is running or installed."""
        try:
            logger.debug("Checking mcp-proxy status...")
            
            # First check if port 9090 is in use (indicating running service)
            # Use socket-based port checking instead of psutil.net_connections() to avoid permissions issues
            port_in_use = self._is_port_in_use(9090)
            if port_in_use:
                logger.debug("Found process listening on port 9090")
            
            # Check if process exists by name or command line
            process_found = False
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_info = proc.info
                    name = proc_info.get('name', '') or ''  # Handle None values safely
                    cmdline = proc_info.get('cmdline', []) or []  # Handle None values safely
                    
                    # Check process name
                    if 'mcp-proxy' in name.lower():
                        logger.debug(f"Found mcp-proxy process by name: {name} (PID: {proc_info['pid']})")
                        process_found = True
                        break
                    
                    # Check command line arguments
                    if cmdline and any('mcp-proxy' in str(arg).lower() for arg in cmdline):
                        logger.debug(f"Found mcp-proxy process by cmdline: {' '.join(map(str, cmdline))} (PID: {proc_info['pid']})")
                        process_found = True
                        break
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, TypeError):
                    continue
            
            # If we found either port usage or process, consider it running
            if port_in_use or process_found:
                logger.debug("mcp-proxy detected as running")
                return True
            
            # Check if binary exists in known installation paths
            config = self.dependencies.get("mcp-proxy", {})
            install_paths = config.get("install_paths", [])
            
            for install_path in install_paths:
                if not install_path.exists():
                    continue
                    
                # Check for direct binary
                binary_path = install_path / "mcp-proxy"
                if binary_path.exists() and binary_path.is_file():
                    logger.debug(f"Found mcp-proxy binary at: {binary_path}")
                    return True
                    
                # Also check for mcp-proxy in subdirectories
                for subdir in ["bin", "node_modules/.bin", "target/release", ".bin", "Scripts"]:
                    sub_binary = install_path / subdir / "mcp-proxy"
                    if sub_binary.exists() and sub_binary.is_file():
                        logger.debug(f"Found mcp-proxy binary at: {sub_binary}")
                        return True
            
            # Check if available in PATH
            if self.check_binary_available("mcp-proxy"):
                logger.debug("Found mcp-proxy in PATH")
                return True
            
            logger.debug("mcp-proxy not found")
            return False
            
        except Exception as e:
            logger.error(f"Error checking mcp-proxy: {e}")
            return False
    
    def check_claude_desktop(self) -> bool:
        """Check if Claude Desktop is installed and/or running."""
        try:
            logger.debug("Checking Claude Desktop status...")
            config = self.dependencies.get("claude-desktop", {})
            app_paths = config.get("app_paths", [])
            process_names = config.get("process_names", ["Claude", "claude", "Claude Desktop"])
            
            # Check if Claude Desktop app exists
            app_found = False
            for app_path in app_paths:
                if app_path.exists() and app_path.is_dir():
                    # Check if it's a valid app bundle
                    info_plist = app_path / "Contents/Info.plist"
                    if info_plist.exists():
                        logger.debug(f"Found Claude Desktop app at: {app_path}")
                        app_found = True
                        break
            
            # Check if Claude Desktop is currently running
            process_found = False
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    proc_info = proc.info
                    # Handle None values safely
                    name = proc_info.get('name', '') or ''
                    exe_path = proc_info.get('exe', '') or ''
                    
                    # Convert to lowercase safely
                    name_lower = name.lower()
                    exe_path_lower = exe_path.lower()
                    
                    # Check against known process names
                    for process_name in process_names:
                        process_name_lower = process_name.lower()
                        if process_name_lower in name_lower or process_name_lower in exe_path_lower:
                            # Additional validation for Claude app
                            if 'claude' in exe_path_lower and ('.app' in exe_path_lower or 'claude' in name_lower):
                                logger.debug(f"Found running Claude process: {name} (PID: {proc_info['pid']}, exe: {exe_path})")
                                process_found = True
                                break
                    
                    if process_found:
                        break
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, TypeError):
                    continue
            
            # Return True if either app is installed OR process is running
            result = app_found or process_found
            logger.debug(f"Claude Desktop check result: app_found={app_found}, process_found={process_found}, result={result}")
            return result
            
        except Exception as e:
            logger.error(f"Error checking Claude Desktop: {e}")
            return False
    
    def check_binary_available(self, binary_name: str) -> bool:
        """Check if a binary is available in PATH."""
        try:
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
    
    def diagnose_mcp_proxy(self) -> Dict[str, Any]:
        """Diagnose mcp-proxy installation and configuration."""
        try:
            diagnosis = {
                "found": False,
                "path": None,
                "version": None,
                "config_file": None,
                "logs": []
            }
            
            # Check if mcp-proxy is installed
            mcp_proxy_path = self._find_binary_path("mcp-proxy")
            if mcp_proxy_path:
                diagnosis["found"] = True
                diagnosis["path"] = mcp_proxy_path
                
                # Get version
                version = self._get_binary_version("mcp-proxy")
                if version:
                    diagnosis["version"] = version
            
            # Check for config file
            config_path = Path.home() / ".mcp-proxy" / "config.json"
            if config_path.exists():
                diagnosis["config_file"] = str(config_path)
            
            # Check logs
            log_path = Path.home() / ".mcp-proxy" / "mcp-proxy.log"
            if log_path.exists():
                try:
                    with open(log_path, 'r') as f:
                        lines = f.readlines()
                        diagnosis["logs"] = [line.strip() for line in lines[-20:]]  # Last 20 lines
                except Exception:
                    pass
            
            return diagnosis
        except Exception as e:
            logger.error(f"Error diagnosing mcp-proxy: {e}")
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
        
        if dependency_name == "mcp-proxy":
            guidance.update({
                "description": "MCP Proxy is required to bridge communication between Claude Desktop and MCP servers.",
                "methods": [
                    "Install via npm (recommended for most users)",
                    "Build from source (for developers)",
                    "Install via cargo (if using Rust version)"
                ],
                "commands": [
                    "# Method 1: Install via npm",
                    "npm install -g @anthropic/mcp-proxy",
                    "",
                    "# Method 2: Build from source",
                    "git clone https://github.com/anthropic/mcp-proxy.git",
                    "cd mcp-proxy",
                    "npm install && npm run build",
                    "",
                    "# Method 3: Install via cargo (Rust)",
                    "cargo install mcp-proxy"
                ],
                "links": [
                    "https://github.com/anthropic/mcp-proxy",
                    "https://docs.anthropic.com/mcp"
                ]
            })
        
        elif dependency_name == "claude-desktop":
            guidance.update({
                "description": "Claude Desktop is the official Anthropic client that integrates with MCP servers.",
                "methods": [
                    "Download from official website",
                    "Install via Homebrew (macOS)"
                ],
                "commands": [
                    "# Method 1: Download from website",
                    "# Visit https://claude.ai/desktop and download for your platform",
                    "",
                    "# Method 2: Install via Homebrew (macOS)",
                    "brew install --cask claude"
                ],
                "links": [
                    "https://claude.ai/desktop",
                    "https://docs.anthropic.com/claude/desktop"
                ]
            })
        
        elif dependency_name == "node":
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
            if service_name == "mcp-proxy":
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if 'mcp-proxy' in proc.info['name'] or \
                           any('mcp-proxy' in arg for arg in proc.info['cmdline'] or []):
                            return proc.info['pid']
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
        except Exception as e:
            logger.error(f"Error getting process ID for {service_name}: {e}")
        
        return None
    
    def _find_dependency_path(self, dep_name: str, config: dict) -> Optional[str]:
        """Find the path to a dependency."""
        try:
            if dep_name == "mcp-proxy":
                install_paths = config.get("install_paths", [])
                for install_path in install_paths:
                    binary_path = install_path / "mcp-proxy"
                    if binary_path.exists():
                        return str(binary_path)
                    
                    # Check subdirectories
                    for subdir in ["bin", "node_modules/.bin", "target/release"]:
                        sub_binary = install_path / subdir / "mcp-proxy"
                        if sub_binary.exists():
                            return str(sub_binary)
                
                # Check PATH
                return self._find_binary_path("mcp-proxy")
                
            elif dep_name == "claude-desktop":
                app_paths = config.get("app_paths", [])
                for app_path in app_paths:
                    if app_path.exists():
                        return str(app_path)
                return None
                
            else:
                # Regular binary
                binary_name = config.get("binary_name")
                if binary_name:
                    return self._find_binary_path(binary_name)
                    
        except Exception as e:
            logger.error(f"Error finding path for {dep_name}: {e}")
        
        return None
    
    def _get_dependency_version(self, dep_name: str, config: dict) -> Optional[str]:
        """Get version of a dependency."""
        try:
            if dep_name == "claude-desktop":
                # Try to get Claude Desktop version from Info.plist
                app_paths = config.get("app_paths", [])
                for app_path in app_paths:
                    if app_path.exists():
                        info_plist = app_path / "Contents/Info.plist"
                        if info_plist.exists():
                            # Simple version extraction - could be enhanced with plistlib
                            try:
                                content = info_plist.read_text()
                                if "CFBundleShortVersionString" in content:
                                    # Extract version using simple text parsing
                                    lines = content.split('\n')
                                    for i, line in enumerate(lines):
                                        if "CFBundleShortVersionString" in line and i + 1 < len(lines):
                                            next_line = lines[i + 1].strip()
                                            if "<string>" in next_line:
                                                version = next_line.replace("<string>", "").replace("</string>", "").strip()
                                                return version
                            except Exception:
                                pass
                        return "Unknown"
                return None
                
            else:
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