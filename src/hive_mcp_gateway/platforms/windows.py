"""Windows platform manager implementation."""

import platform
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .base import (
    PlatformManagerBase, 
    PlatformInfo, 
    ApplicationPaths, 
    BuildConfiguration, 
    SupportedPlatform
)


class WindowsPlatformManager(PlatformManagerBase):
    """Windows-specific platform manager."""
    
    def get_platform_info(self) -> PlatformInfo:
        """Get Windows platform information."""
        return PlatformInfo(
            platform=SupportedPlatform.WINDOWS,
            version=platform.version(),
            architecture=platform.machine(),
            python_version=sys.version,
            is_supported=True
        )
    
    def get_application_paths(self) -> ApplicationPaths:
        """Get Windows-specific application paths."""
        import os
        
        # Use Windows environment variables
        appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        localappdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        programfiles = Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
        temp = Path(os.environ.get("TEMP", "C:/Windows/Temp"))
        
        return ApplicationPaths(
            executable_path=programfiles / "HiveMCPGateway" / "HiveMCPGateway.exe",
            config_dir=appdata / "HiveMCPGateway",
            data_dir=localappdata / "HiveMCPGateway" / "Data",
            cache_dir=localappdata / "HiveMCPGateway" / "Cache",
            log_dir=localappdata / "HiveMCPGateway" / "Logs",
            temp_dir=temp / "HiveMCPGateway"
        )
    
    def get_build_configuration(self) -> BuildConfiguration:
        """Get Windows build configuration."""
        return BuildConfiguration(
            output_format=".exe",
            build_command=[
                "uv", "run", "pyinstaller",
                "--windowed",
                "--onefile", 
                "--name", "HiveMCPGateway",
                "--icon", "gui/assets/icon.ico",
                "--add-data", "gui/assets;assets",
                "--add-data", "config;config",
                "--clean",
                "--noconfirm",
                "run_gui.py"
            ],
            package_command=[
                "makensis",
                "/DVERSION=0.3.0",
                "/DOUTFILE=dist/HiveMCPGateway-Setup.exe",
                "installer.nsi"
            ],
            installer_command=None,  # NSIS script handles installation
            required_tools=["uv", "pyinstaller", "makensis"],
            icon_format=".ico",
            executable_extension=".exe"
        )
    
    def setup_autostart(self, app_path: Path, enabled: bool = True) -> bool:
        """Setup Windows autostart using registry or startup folder."""
        try:
            if enabled:
                return self._add_to_startup(app_path)
            else:
                return self._remove_from_startup()
                
        except Exception as e:
            print(f"Error setting up autostart: {e}")
            return False
    
    def _add_to_startup(self, app_path: Path) -> bool:
        """Add application to Windows startup."""
        try:
            import winreg
            
            # Use registry method (preferred)
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            
            winreg.SetValueEx(
                key,
                "HiveMCPGateway",
                0,
                winreg.REG_SZ,
                str(app_path)
            )
            
            winreg.CloseKey(key)
            return True
            
        except ImportError:
            # Fallback: use startup folder
            return self._add_to_startup_folder(app_path)
        except Exception as e:
            print(f"Registry method failed: {e}")
            return self._add_to_startup_folder(app_path)
    
    def _add_to_startup_folder(self, app_path: Path) -> bool:
        """Add shortcut to startup folder."""
        try:
            import win32com.client
            
            startup_folder = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            startup_folder.mkdir(parents=True, exist_ok=True)
            
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut_path = startup_folder / "HiveMCPGateway.lnk"
            shortcut = shell.CreateShortCut(str(shortcut_path))
            shortcut.Targetpath = str(app_path)
            shortcut.WorkingDirectory = str(app_path.parent)
            shortcut.IconLocation = str(app_path)
            shortcut.save()
            
            return True
            
        except ImportError:
            print("pywin32 not available, cannot create startup shortcut")
            return False
        except Exception as e:
            print(f"Error creating startup shortcut: {e}")
            return False
    
    def _remove_from_startup(self) -> bool:
        """Remove application from Windows startup."""
        try:
            # Remove from registry
            try:
                import winreg
                
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
                    0,
                    winreg.KEY_SET_VALUE
                )
                
                winreg.DeleteValue(key, "HiveMCPGateway")
                winreg.CloseKey(key)
                
            except Exception:
                pass  # Key might not exist
            
            # Remove from startup folder
            startup_folder = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            shortcut_path = startup_folder / "HiveMCPGateway.lnk"
            
            if shortcut_path.exists():
                shortcut_path.unlink()
            
            return True
            
        except Exception as e:
            print(f"Error removing from startup: {e}")
            return False
    
    def is_autostart_enabled(self) -> bool:
        """Check if autostart is enabled."""
        try:
            # Check registry
            try:
                import winreg
                
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
                    0,
                    winreg.KEY_READ
                )
                
                winreg.QueryValueEx(key, "HiveMCPGateway")
                winreg.CloseKey(key)
                return True
                
            except Exception:
                pass
            
            # Check startup folder
            startup_folder = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            shortcut_path = startup_folder / "HiveMCPGateway.lnk"
            
            return shortcut_path.exists()
            
        except Exception:
            return False
    
    def get_system_dependencies(self) -> Dict[str, bool]:
        """Get Windows system dependencies status."""
        dependencies = {
            "python": self._check_tool_available("python"),
            "uv": self._check_tool_available("uv"),
            "node": self._check_tool_available("node"),
            "npm": self._check_tool_available("npm"),
            "npx": self._check_tool_available("npx"),
            "git": self._check_tool_available("git"),
            "pyinstaller": self._check_tool_available("pyinstaller"),
            "makensis": self._check_tool_available("makensis"),  # NSIS
            "signtool": self._check_tool_available("signtool")  # Code signing
        }
        
        return dependencies
    
    def install_system_dependencies(self) -> bool:
        """Install Windows system dependencies using winget or chocolatey."""
        try:
            # Try winget first (Windows 11/10 newer versions)
            if self._check_tool_available("winget"):
                dependencies = ["Python.Python.3.12", "Git.Git", "OpenJS.NodeJS"]
                
                for dep in dependencies:
                    try:
                        subprocess.run(
                            ["winget", "install", dep, "--silent"],
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                    except subprocess.TimeoutExpired:
                        print(f"Timeout installing {dep}")
                        
            # Try chocolatey as fallback
            elif self._check_tool_available("choco"):
                dependencies = ["python", "git", "nodejs"]
                
                for dep in dependencies:
                    try:
                        subprocess.run(
                            ["choco", "install", dep, "-y"],
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                    except subprocess.TimeoutExpired:
                        print(f"Timeout installing {dep}")
            else:
                print("Neither winget nor chocolatey found. Please install dependencies manually.")
                return False
            
            # Install Python packages
            subprocess.run(["pip", "install", "uv"], check=False)
            subprocess.run(["uv", "add", "--dev", "pyinstaller"], check=False)
            
            return True
            
        except Exception as e:
            print(f"Error installing dependencies: {e}")
            return False
    
    def create_application_bundle(self, source_dir: Path, output_dir: Path) -> bool:
        """Create Windows executable using PyInstaller."""
        try:
            build_config = self.get_build_configuration()
            
            # Run PyInstaller
            result = subprocess.run(
                build_config.build_command,
                cwd=source_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"PyInstaller failed: {result.stderr}")
                return False
            
            # Move the .exe to output directory
            exe_file = source_dir / "dist" / "HiveMCPGateway.exe"
            if exe_file.exists():
                output_exe = output_dir / "HiveMCPGateway.exe"
                exe_file.rename(output_exe)
                return True
            
            return False
            
        except Exception as e:
            print(f"Error creating executable: {e}")
            return False
    
    def create_installer(self, bundle_path: Path, output_dir: Path) -> bool:
        """Create NSIS installer for Windows."""
        try:
            # This would require an NSIS script file
            # For now, just indicate support is available
            print("NSIS installer creation not yet implemented")
            return False
            
        except Exception as e:
            print(f"Error creating installer: {e}")
            return False
    
    def get_ide_integration_paths(self) -> Dict[str, List[Path]]:
        """Get Windows IDE integration paths."""
        appdata = Path.home() / "AppData" / "Roaming"
        
        return {
            "claude_desktop": [
                appdata / "Claude" / "claude_desktop_config.json"
            ],
            "vscode": [
                appdata / "Code" / "User" / "settings.json",
                Path.home() / ".vscode" / "extensions"
            ],
            "cursor": [
                appdata / "Cursor" / "User" / "settings.json"
            ]
        }
    
    def setup_file_associations(self, extensions: List[str]) -> bool:
        """Setup file type associations on Windows."""
        try:
            # This would involve registry modifications
            # For now, return True as placeholder
            return True
            
        except Exception as e:
            print(f"Error setting up file associations: {e}")
            return False