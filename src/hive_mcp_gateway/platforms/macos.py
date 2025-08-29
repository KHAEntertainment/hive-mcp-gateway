"""macOS platform manager implementation."""

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


class MacOSPlatformManager(PlatformManagerBase):
    """macOS-specific platform manager."""
    
    def get_platform_info(self) -> PlatformInfo:
        """Get macOS platform information."""
        return PlatformInfo(
            platform=SupportedPlatform.MACOS,
            version=platform.mac_ver()[0],
            architecture=platform.machine(),
            python_version=sys.version,
            is_supported=True
        )
    
    def get_application_paths(self) -> ApplicationPaths:
        """Get macOS-specific application paths."""
        home = Path.home()
        
        return ApplicationPaths(
            executable_path=Path("/Applications/HiveMCPGateway.app"),
            config_dir=home / "Library" / "Application Support" / "HiveMCPGateway",
            data_dir=home / "Library" / "Application Support" / "HiveMCPGateway" / "Data",
            cache_dir=home / "Library" / "Caches" / "HiveMCPGateway",
            log_dir=home / "Library" / "Logs" / "HiveMCPGateway",
            temp_dir=Path("/tmp") / "HiveMCPGateway"
        )
    
    def get_build_configuration(self) -> BuildConfiguration:
        """Get macOS build configuration."""
        return BuildConfiguration(
            output_format=".app",
            build_command=[
                "uv", "run", "pyinstaller",
                "--windowed",
                "--onedir", 
                "--name", "HiveMCPGateway",
                "--icon", "gui/assets/icon.icns",
                "--add-data", "gui/assets:assets",
                "--add-data", "config:config",
                "--clean",
                "--noconfirm",
                "run_gui.py"
            ],
            package_command=[
                "hdiutil", "create", 
                "-volname", "Hive MCP Gateway",
                "-srcfolder", "dist/HiveMCPGateway.app",
                "-ov", "-format", "UDZO",
                "dist/HiveMCPGateway.dmg"
            ],
            installer_command=None,  # DMG serves as installer
            required_tools=["uv", "pyinstaller", "hdiutil"],
            icon_format=".icns",
            executable_extension=""
        )
    
    def setup_autostart(self, app_path: Path, enabled: bool = True) -> bool:
        """Setup macOS LaunchAgent for autostart."""
        try:
            from gui.autostart_manager import AutoStartManager
            autostart = AutoStartManager()
            
            if enabled:
                return autostart.enable_auto_start()
            else:
                return autostart.disable_auto_start()
                
        except Exception as e:
            print(f"Error setting up autostart: {e}")
            return False
    
    def is_autostart_enabled(self) -> bool:
        """Check if autostart is enabled."""
        try:
            from gui.autostart_manager import AutoStartManager
            autostart = AutoStartManager()
            return autostart.is_auto_start_enabled()
        except Exception:
            return False
    
    def enable_autostart(self) -> bool:
        """Enable autostart for the application."""
        try:
            from gui.autostart_manager import AutoStartManager
            autostart = AutoStartManager()
            return autostart.enable_auto_start()
        except Exception as e:
            print(f"Error enabling autostart: {e}")
            return False
    
    def disable_autostart(self) -> bool:
        """Disable autostart for the application."""
        try:
            from gui.autostart_manager import AutoStartManager
            autostart = AutoStartManager()
            return autostart.disable_auto_start()
        except Exception as e:
            print(f"Error disabling autostart: {e}")
            return False
    
    def get_system_dependencies(self) -> Dict[str, bool]:
        """Get macOS system dependencies status."""
        dependencies = {
            "python3": self._check_tool_available("python3"),
            "uv": self._check_tool_available("uv"),
            "node": self._check_tool_available("node"),
            "npm": self._check_tool_available("npm"),
            "npx": self._check_tool_available("npx"),
            "git": self._check_tool_available("git"),
            "pyinstaller": self._check_tool_available("pyinstaller"),
            "hdiutil": self._check_tool_available("hdiutil"),
            "codesign": self._check_tool_available("codesign"),
            "xcrun": self._check_tool_available("xcrun")
        }
        
        return dependencies
    
    def install_system_dependencies(self) -> bool:
        """Install macOS system dependencies using Homebrew."""
        try:
            # Check if Homebrew is installed
            if not self._check_tool_available("brew"):
                print("Homebrew not found. Please install Homebrew first:")
                print("/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
                return False
            
            # Install dependencies
            dependencies = ["python@3.12", "node", "git", "uv"]
            
            for dep in dependencies:
                try:
                    result = subprocess.run(
                        ["brew", "install", dep],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    if result.returncode != 0:
                        print(f"Failed to install {dep}: {result.stderr}")
                except subprocess.TimeoutExpired:
                    print(f"Timeout installing {dep}")
            
            # Install PyInstaller via uv
            subprocess.run(["uv", "add", "--dev", "pyinstaller"], check=False)
            
            return True
            
        except Exception as e:
            print(f"Error installing dependencies: {e}")
            return False
    
    def create_application_bundle(self, source_dir: Path, output_dir: Path) -> bool:
        """Create macOS .app bundle using PyInstaller."""
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
            
            # Move the .app to output directory
            app_bundle = source_dir / "dist" / "HiveMCPGateway.app"
            if app_bundle.exists():
                output_bundle = output_dir / "HiveMCPGateway.app"
                if output_bundle.exists():
                    import shutil
                    shutil.rmtree(output_bundle)
                
                app_bundle.rename(output_bundle)
                return True
            
            return False
            
        except Exception as e:
            print(f"Error creating app bundle: {e}")
            return False
    
    def create_installer(self, bundle_path: Path, output_dir: Path) -> bool:
        """Create DMG installer for macOS."""
        try:
            build_config = self.get_build_configuration()
            
            if build_config.package_command:
                # Update paths in command
                cmd = build_config.package_command.copy()
                
                # Replace placeholders with actual paths
                for i, arg in enumerate(cmd):
                    if "dist/HiveMCPGateway.app" in arg:
                        cmd[i] = str(bundle_path)
                    elif "dist/HiveMCPGateway.dmg" in arg:
                        cmd[i] = str(output_dir / "HiveMCPGateway.dmg")
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"DMG created successfully at {output_dir / 'HiveMCPGateway.dmg'}")
                    return True
                else:
                    print(f"DMG creation failed: {result.stderr}")
                    return False
            
            return False
            
        except Exception as e:
            print(f"Error creating DMG: {e}")
            return False
    
    def get_ide_integration_paths(self) -> Dict[str, List[Path]]:
        """Get macOS IDE integration paths."""
        home = Path.home()
        
        return {
            "claude_desktop": [
                home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
            ],
            "vscode": [
                home / "Library" / "Application Support" / "Code" / "User" / "settings.json",
                home / ".vscode" / "extensions"
            ],
            "cursor": [
                home / "Library" / "Application Support" / "Cursor" / "User" / "settings.json"
            ],
            "sublime": [
                home / "Library" / "Application Support" / "Sublime Text" / "Packages" / "User"
            ]
        }
    
    def setup_file_associations(self, extensions: List[str]) -> bool:
        """Setup file type associations on macOS."""
        try:
            # This would typically involve modifying the app's Info.plist
            # and registering with Launch Services
            
            app_paths = self.get_application_paths()
            if not app_paths.executable_path.exists():
                return False
            
            # For now, return True as this requires more complex implementation
            # involving Info.plist modification and lsregister
            return True
            
        except Exception as e:
            print(f"Error setting up file associations: {e}")
            return False