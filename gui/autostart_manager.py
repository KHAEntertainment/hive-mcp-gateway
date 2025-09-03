"""Cross-platform autostart manager for Hive MCP Gateway."""

import logging
import platform
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtCore import QObject

logger = logging.getLogger(__name__)


class AutoStartManager(QObject):
    """Cross-platform autostart manager for Hive MCP Gateway."""
    
    def __init__(self):
        """Initialize auto-start manager."""
        super().__init__()
        
        self.platform = platform.system()
        
        # Initialize platform-specific implementation
        if self.platform == "Darwin":  # macOS
            self._impl = MacOSAutoStartImpl()
        elif self.platform == "Windows":
            self._impl = WindowsAutoStartImpl()
        elif self.platform == "Linux":
            self._impl = LinuxAutoStartImpl()
        else:
            logger.warning(f"Unsupported platform: {self.platform}")
            self._impl = None
        
        logger.info(f"AutoStart manager initialized for {self.platform}")
    
    def enable_auto_start(self) -> bool:
        """Enable auto-start functionality."""
        if self._impl:
            return self._impl.enable_auto_start()
        return False
    
    def disable_auto_start(self) -> bool:
        """Disable auto-start functionality."""
        if self._impl:
            return self._impl.disable_auto_start()
        return False
    
    def is_auto_start_enabled(self) -> bool:
        """Check if auto-start is enabled."""
        if self._impl:
            return self._impl.is_auto_start_enabled()
        return False
    
    def get_auto_start_status(self) -> Dict[str, Any]:
        """Get detailed auto-start status."""
        if self._impl:
            status = self._impl.get_auto_start_status()
            status["platform"] = self.platform
            return status
        return {
            "platform": self.platform,
            "supported": False,
            "enabled": False,
            "error": f"Unsupported platform: {self.platform}"
        }


class AutoStartImplBase:
    """Base class for platform-specific autostart implementations."""
    
    def enable_auto_start(self) -> bool:
        """Enable auto-start functionality."""
        raise NotImplementedError
    
    def disable_auto_start(self) -> bool:
        """Disable auto-start functionality."""
        raise NotImplementedError
    
    def is_auto_start_enabled(self) -> bool:
        """Check if auto-start is enabled."""
        raise NotImplementedError
    
    def get_auto_start_status(self) -> Dict[str, Any]:
        """Get detailed auto-start status."""
        raise NotImplementedError


class MacOSAutoStartImpl(AutoStartImplBase):
    """macOS Launch Agent implementation for autostart."""
    
    def __init__(self):
        """Initialize macOS autostart implementation."""
        self.launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
        self.plist_filename = "com.hive.mcp-gateway.plist"
        self.plist_path = self.launch_agents_dir / self.plist_filename
        
        # Ensure launch agents directory exists
        self.launch_agents_dir.mkdir(parents=True, exist_ok=True)
    
    
    def enable_auto_start(self) -> bool:
        """Enable auto-start functionality."""
        if self.is_launch_agent_installed():
            logger.info("Launch agent already installed")
            if not self.is_launch_agent_loaded():
                return self.load_launch_agent()
            return True
        else:
            return self.create_launch_agent()
    
    def disable_auto_start(self) -> bool:
        """Disable auto-start functionality."""
        return self.remove_launch_agent()
    
    def is_auto_start_enabled(self) -> bool:
        """Check if auto-start is enabled."""
        return self.is_launch_agent_installed() and self.is_launch_agent_loaded()
    
    def get_auto_start_status(self) -> Dict[str, Any]:
        """Get detailed auto-start status."""
        return self.get_launch_agent_status()
    
    def create_launch_agent(self) -> bool:
        """Create macOS Launch Agent for auto-start."""
        try:
            app_path = self.get_app_bundle_path()
            
            if not app_path or not app_path.exists():
                logger.error(f"App bundle not found at {app_path}")
                return False
            
            # Create Launch Agent plist
            plist_data = {
                "Label": "com.hive.mcp-gateway",
                "ProgramArguments": [sys.executable, sys.argv[0]],
                "RunAtLoad": True,
                "KeepAlive": False,
                "LaunchOnlyOnce": True,
                "ProcessType": "Interactive",
                "StandardOutPath": str(Path.home() / "Library" / "Logs" / "HiveMCPGateway.log"),
                "StandardErrorPath": str(Path.home() / "Library" / "Logs" / "HiveMCPGateway_error.log"),
                "WorkingDirectory": str(Path.home()),
                "EnvironmentVariables": {
                    "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
                }
            }
            
            # Write plist file
            with open(self.plist_path, 'wb') as f:
                plistlib.dump(plist_data, f)
            
            # Load the launch agent
            result = subprocess.run(
                ["launchctl", "load", str(self.plist_path)],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Launch agent created and loaded: {self.plist_path}")
                return True
            else:
                logger.error(f"Failed to load launch agent: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to create launch agent: {e}")
            return False
    
    def remove_launch_agent(self) -> bool:
        """Remove auto-start launch agent."""
        try:
            # Unload if currently loaded
            if self.is_launch_agent_loaded():
                result = subprocess.run(
                    ["launchctl", "unload", str(self.plist_path)],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    logger.warning(f"Failed to unload launch agent: {result.stderr}")
            
            # Remove plist file
            if self.plist_path.exists():
                self.plist_path.unlink()
                logger.info("Launch agent removed")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove launch agent: {e}")
            return False
    
    def is_launch_agent_installed(self) -> bool:
        """Check if launch agent is installed."""
        return self.plist_path.exists()
    
    def is_launch_agent_loaded(self) -> bool:
        """Check if launch agent is currently loaded."""
        try:
            result = subprocess.run(
                ["launchctl", "list", "com.hive.mcp-gateway"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def get_launch_agent_status(self) -> Dict[str, Any]:
        """Get detailed status of the launch agent."""
        status = {
            "installed": self.is_launch_agent_installed(),
            "loaded": self.is_launch_agent_loaded(),
            "plist_path": str(self.plist_path),
            "app_bundle_path": None,
            "valid_app_bundle": False
        }
        
        # Check app bundle
        app_path = self.get_app_bundle_path()
        if app_path:
            status["app_bundle_path"] = str(app_path)
            status["valid_app_bundle"] = app_path.exists()
        
        return status
    
    def get_app_bundle_path(self) -> Optional[Path]:
        """Get the path to the app bundle."""
        # Check common locations for the app bundle
        possible_paths = [
            Path("/Applications/HiveMCPGateway.app"),
            Path.home() / "Applications" / "HiveMCPGateway.app",
            Path("/usr/local/bin/HiveMCPGateway.app"),
            # Development path
            Path.cwd() / "dist" / "HiveMCPGateway.app",
            # Additional common paths
            Path.home() / "Desktop" / "HiveMCPGateway.app",
            Path.home() / "Downloads" / "HiveMCPGateway.app"
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_dir():
                logger.info(f"Found app bundle at: {path}")
                return path
        
        # Try to find the app bundle using system utilities
        try:
            result = subprocess.run(
                ["mdfind", "kMDItemCFBundleIdentifier == 'com.hive.mcp-gateway'"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                app_path = Path(result.stdout.strip().split('\n')[0])
                if app_path.exists() and app_path.is_dir():
                    logger.info(f"Found app bundle via mdfind: {app_path}")
                    return app_path
        except Exception as e:
            logger.debug(f"Failed to find app bundle using mdfind: {e}")
        
        return None
    
    def load_launch_agent(self) -> bool:
        """Load an existing launch agent."""
        try:
            if not self.plist_path.exists():
                logger.error("Launch agent plist does not exist")
                return False
            
            result = subprocess.run(
                ["launchctl", "load", str(self.plist_path)],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("Launch agent loaded successfully")
                return True
            else:
                logger.error(f"Failed to load launch agent: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error loading launch agent: {e}")
            return False


class WindowsAutoStartImpl(AutoStartImplBase):
    """Windows Registry/Startup implementation for autostart."""
    
    def __init__(self):
        """Initialize Windows autostart implementation."""
        self.app_name = "HiveMCPGateway"
        self.startup_folder = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        self.shortcut_path = self.startup_folder / f"{self.app_name}.lnk"
        
        # Ensure startup folder exists
        self.startup_folder.mkdir(parents=True, exist_ok=True)
    
    def enable_auto_start(self) -> bool:
        """Enable auto-start functionality using startup folder."""
        try:
            app_path = self.get_app_executable_path()
            if not app_path or not app_path.exists():
                logger.error(f"Application executable not found at {app_path}")
                return False
            
            # Create shortcut in startup folder
            # Note: This is a simplified implementation
            # In production, you might want to use pywin32 or similar for proper shortcut creation
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(str(self.shortcut_path))
                shortcut.Targetpath = str(app_path)
                shortcut.WorkingDirectory = str(app_path.parent)
                shortcut.IconLocation = str(app_path)
                shortcut.save()
                
                logger.info(f"Startup shortcut created: {self.shortcut_path}")
                return True
                
            except ImportError:
                # Fallback: copy executable to startup folder (less elegant)
                import shutil
                startup_exe = self.startup_folder / f"{self.app_name}.exe"
                shutil.copy2(app_path, startup_exe)
                logger.info(f"Application copied to startup folder: {startup_exe}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to enable Windows autostart: {e}")
            return False
    
    def disable_auto_start(self) -> bool:
        """Disable auto-start functionality."""
        try:
            # Remove shortcut from startup folder
            if self.shortcut_path.exists():
                self.shortcut_path.unlink()
                logger.info("Startup shortcut removed")
            
            # Also remove copied executable if it exists
            startup_exe = self.startup_folder / f"{self.app_name}.exe"
            if startup_exe.exists():
                startup_exe.unlink()
                logger.info("Startup executable removed")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to disable Windows autostart: {e}")
            return False
    
    def is_auto_start_enabled(self) -> bool:
        """Check if auto-start is enabled."""
        return (self.shortcut_path.exists() or 
                (self.startup_folder / f"{self.app_name}.exe").exists())
    
    def get_auto_start_status(self) -> Dict[str, Any]:
        """Get detailed auto-start status."""
        return {
            "enabled": self.is_auto_start_enabled(),
            "shortcut_path": str(self.shortcut_path),
            "shortcut_exists": self.shortcut_path.exists(),
            "startup_folder": str(self.startup_folder),
            "app_executable_path": str(self.get_app_executable_path()) if self.get_app_executable_path() else None
        }
    
    def get_app_executable_path(self) -> Optional[Path]:
        """Get the path to the application executable."""
        possible_paths = [
            Path(f"C:/Program Files/HiveMCPGateway/{self.app_name}.exe"),
            Path.home() / "AppData" / "Local" / "Programs" / "HiveMCPGateway" / f"{self.app_name}.exe",
            # Development path
            Path.cwd() / "dist" / f"{self.app_name}.exe"
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_file():
                return path
        
        return None


class LinuxAutoStartImpl(AutoStartImplBase):
    """Linux Desktop Entry implementation for autostart."""
    
    def __init__(self):
        """Initialize Linux autostart implementation."""
        self.autostart_dir = Path.home() / ".config" / "autostart"
        self.desktop_file_name = "hive-mcp-gateway.desktop"
        self.desktop_file_path = self.autostart_dir / self.desktop_file_name
        
        # Ensure autostart directory exists
        self.autostart_dir.mkdir(parents=True, exist_ok=True)
    
    def enable_auto_start(self) -> bool:
        """Enable auto-start functionality using desktop entry."""
        try:
            app_path = self.get_app_executable_path()
            if not app_path or not app_path.exists():
                logger.error(f"Application executable not found at {app_path}")
                return False
            
            # Create desktop entry
            desktop_content = f"""[Desktop Entry]
Type=Application
Name=Hive MCP Gateway
Comment=Intelligent MCP gateway and tool management system
Exec={app_path}
Icon=hive-mcp-gateway
Terminal=false
NoDisplay=true
StartupNotify=false
X-GNOME-Autostart-enabled=true
X-KDE-autostart-after=panel
X-MATE-Autostart-enabled=true
"""
            
            # Write desktop file
            with open(self.desktop_file_path, 'w') as f:
                f.write(desktop_content)
            
            # Make executable
            self.desktop_file_path.chmod(0o755)
            
            logger.info(f"Desktop entry created: {self.desktop_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable Linux autostart: {e}")
            return False
    
    def disable_auto_start(self) -> bool:
        """Disable auto-start functionality."""
        try:
            if self.desktop_file_path.exists():
                self.desktop_file_path.unlink()
                logger.info("Desktop entry removed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disable Linux autostart: {e}")
            return False
    
    def is_auto_start_enabled(self) -> bool:
        """Check if auto-start is enabled."""
        return self.desktop_file_path.exists()
    
    def get_auto_start_status(self) -> Dict[str, Any]:
        """Get detailed auto-start status."""
        return {
            "enabled": self.is_auto_start_enabled(),
            "desktop_file_path": str(self.desktop_file_path),
            "desktop_file_exists": self.desktop_file_path.exists(),
            "autostart_dir": str(self.autostart_dir),
            "app_executable_path": str(self.get_app_executable_path()) if self.get_app_executable_path() else None
        }
    
    def get_app_executable_path(self) -> Optional[Path]:
        """Get the path to the application executable."""
        possible_paths = [
            Path("/usr/local/bin/hive-mcp-gateway"),
            Path("/usr/bin/hive-mcp-gateway"),
            Path.home() / ".local" / "bin" / "hive-mcp-gateway",
            # Development path
            Path.cwd() / "dist" / "hive-mcp-gateway"
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_file():
                return path
        
        return None