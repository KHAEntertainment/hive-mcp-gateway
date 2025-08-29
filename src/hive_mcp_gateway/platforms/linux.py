"""Linux platform manager implementation."""

import os
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


class LinuxPlatformManager(PlatformManagerBase):
    """Linux-specific platform manager."""
    
    def get_platform_info(self) -> PlatformInfo:
        """Get Linux platform information."""
        return PlatformInfo(
            platform=SupportedPlatform.LINUX,
            version=platform.release(),
            architecture=platform.machine(),
            python_version=sys.version,
            is_supported=True
        )
    
    def get_application_paths(self) -> ApplicationPaths:
        """Get Linux-specific application paths."""
        home = Path.home()
        
        # Follow XDG Base Directory Specification
        xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
        xdg_data = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
        xdg_cache = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))
        
        return ApplicationPaths(
            executable_path=Path("/usr/local/bin/hive-mcp-gateway"),
            config_dir=xdg_config / "hive-mcp-gateway",
            data_dir=xdg_data / "hive-mcp-gateway",
            cache_dir=xdg_cache / "hive-mcp-gateway",
            log_dir=home / ".local" / "share" / "hive-mcp-gateway" / "logs",
            temp_dir=Path("/tmp") / "hive-mcp-gateway"
        )
    
    def get_build_configuration(self) -> BuildConfiguration:
        """Get Linux build configuration."""
        return BuildConfiguration(
            output_format=".AppImage",
            build_command=[
                "uv", "run", "pyinstaller",
                "--onefile", 
                "--name", "hive-mcp-gateway",
                "--icon", "gui/assets/icon.png",
                "--add-data", "gui/assets:assets",
                "--add-data", "config:config",
                "--clean",
                "--noconfirm",
                "run_gui.py"
            ],
            package_command=[
                "appimagetool",
                "AppDir",
                "hive-mcp-gateway.AppImage"
            ],
            installer_command=[
                "fpm", "-s", "dir", "-t", "deb",
                "--name", "hive-mcp-gateway",
                "--version", "0.3.0",
                "--description", "Intelligent MCP gateway and tool management system",
                "--url", "https://github.com/KHAEntertainment/hive-mcp-gateway",
                "--maintainer", "KHAEntertainment <contact@khaentertainment.com>",
                "--depends", "python3",
                "--depends", "python3-pip",
                "dist/=/usr/local/bin/"
            ],
            required_tools=["uv", "pyinstaller", "appimagetool", "fpm"],
            icon_format=".png",
            executable_extension=""
        )
    
    def setup_autostart(self, app_path: Path, enabled: bool = True) -> bool:
        """Setup Linux autostart using desktop entry."""
        try:
            autostart_dir = Path.home() / ".config" / "autostart"
            desktop_file = autostart_dir / "hive-mcp-gateway.desktop"
            
            if enabled:
                autostart_dir.mkdir(parents=True, exist_ok=True)
                
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
                
                with open(desktop_file, 'w') as f:
                    f.write(desktop_content)
                
                desktop_file.chmod(0o755)
                return True
            else:
                if desktop_file.exists():
                    desktop_file.unlink()
                return True
                
        except Exception as e:
            print(f"Error setting up autostart: {e}")
            return False
    
    def is_autostart_enabled(self) -> bool:
        """Check if autostart is enabled."""
        autostart_file = Path.home() / ".config" / "autostart" / "hive-mcp-gateway.desktop"
        return autostart_file.exists()
    
    def get_system_dependencies(self) -> Dict[str, bool]:
        """Get Linux system dependencies status."""
        dependencies = {
            "python3": self._check_tool_available("python3"),
            "pip3": self._check_tool_available("pip3"),
            "uv": self._check_tool_available("uv"),
            "node": self._check_tool_available("node"),
            "npm": self._check_tool_available("npm"),
            "npx": self._check_tool_available("npx"),
            "git": self._check_tool_available("git"),
            "pyinstaller": self._check_tool_available("pyinstaller"),
            "appimagetool": self._check_tool_available("appimagetool"),
            "fpm": self._check_tool_available("fpm"),
            "gcc": self._check_tool_available("gcc"),
            "make": self._check_tool_available("make")
        }
        
        return dependencies
    
    def install_system_dependencies(self) -> bool:
        """Install Linux system dependencies."""
        try:
            # Detect package manager
            if self._check_tool_available("apt"):
                # Debian/Ubuntu
                dependencies = [
                    "python3", "python3-pip", "python3-dev",
                    "nodejs", "npm", "git", "gcc", "make",
                    "ruby-dev", "build-essential"
                ]
                
                subprocess.run(["sudo", "apt", "update"], check=False)
                
                for dep in dependencies:
                    subprocess.run(
                        ["sudo", "apt", "install", "-y", dep],
                        capture_output=True,
                        text=True
                    )
                    
            elif self._check_tool_available("dnf"):
                # Fedora/RHEL
                dependencies = [
                    "python3", "python3-pip", "python3-devel",
                    "nodejs", "npm", "git", "gcc", "make",
                    "ruby-devel", "rpm-build"
                ]
                
                for dep in dependencies:
                    subprocess.run(
                        ["sudo", "dnf", "install", "-y", dep],
                        capture_output=True,
                        text=True
                    )
                    
            elif self._check_tool_available("pacman"):
                # Arch Linux
                dependencies = [
                    "python", "python-pip", "nodejs", "npm",
                    "git", "gcc", "make", "ruby", "base-devel"
                ]
                
                for dep in dependencies:
                    subprocess.run(
                        ["sudo", "pacman", "-S", "--noconfirm", dep],
                        capture_output=True,
                        text=True
                    )
            else:
                print("Unknown package manager. Please install dependencies manually.")
                return False
            
            # Install Python packages
            subprocess.run(["pip3", "install", "--user", "uv"], check=False)
            subprocess.run(["uv", "add", "--dev", "pyinstaller"], check=False)
            
            # Install fpm for package creation
            subprocess.run(["gem", "install", "fpm"], check=False)
            
            return True
            
        except Exception as e:
            print(f"Error installing dependencies: {e}")
            return False
    
    def create_application_bundle(self, source_dir: Path, output_dir: Path) -> bool:
        """Create Linux executable and AppImage."""
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
            
            # Move the executable to output directory
            exe_file = source_dir / "dist" / "hive-mcp-gateway"
            if exe_file.exists():
                output_exe = output_dir / "hive-mcp-gateway"
                exe_file.rename(output_exe)
                output_exe.chmod(0o755)
                return True
            
            return False
            
        except Exception as e:
            print(f"Error creating executable: {e}")
            return False
    
    def create_installer(self, bundle_path: Path, output_dir: Path) -> bool:
        """Create DEB/RPM packages for Linux."""
        try:
            build_config = self.get_build_configuration()
            
            if build_config.installer_command and self._check_tool_available("fpm"):
                # Create DEB package
                cmd = build_config.installer_command.copy()
                cmd.extend([str(bundle_path)])
                
                result = subprocess.run(
                    cmd,
                    cwd=output_dir,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print(f"DEB package created successfully")
                    return True
                else:
                    print(f"Package creation failed: {result.stderr}")
                    return False
            
            return False
            
        except Exception as e:
            print(f"Error creating package: {e}")
            return False
    
    def get_ide_integration_paths(self) -> Dict[str, List[Path]]:
        """Get Linux IDE integration paths."""
        home = Path.home()
        config = home / ".config"
        
        return {
            "claude_desktop": [
                config / "Claude" / "claude_desktop_config.json"
            ],
            "vscode": [
                config / "Code" / "User" / "settings.json",
                home / ".vscode" / "extensions"
            ],
            "cursor": [
                config / "Cursor" / "User" / "settings.json"
            ],
            "sublime": [
                config / "sublime-text" / "Packages" / "User"
            ],
            "vim": [
                home / ".vimrc"
            ],
            "neovim": [
                config / "nvim" / "init.lua",
                config / "nvim" / "init.vim"
            ]
        }
    
    def setup_file_associations(self, extensions: List[str]) -> bool:
        """Setup file type associations on Linux."""
        try:
            # Create desktop entry for file associations
            apps_dir = Path.home() / ".local" / "share" / "applications"
            apps_dir.mkdir(parents=True, exist_ok=True)
            
            desktop_file = apps_dir / "hive-mcp-gateway.desktop"
            
            mime_types = []
            for ext in extensions:
                # Map extensions to MIME types
                if ext == ".json":
                    mime_types.append("application/json")
                elif ext == ".yaml" or ext == ".yml":
                    mime_types.append("application/x-yaml")
            
            if mime_types:
                app_paths = self.get_application_paths()
                desktop_content = f"""[Desktop Entry]
Type=Application
Name=Hive MCP Gateway
Comment=Intelligent MCP gateway and tool management system
Exec={app_paths.executable_path} %f
Icon=hive-mcp-gateway
Terminal=false
MimeType={';'.join(mime_types)};
Categories=Development;
"""
                
                with open(desktop_file, 'w') as f:
                    f.write(desktop_content)
                
                desktop_file.chmod(0o755)
                
                # Update MIME database
                subprocess.run(["update-desktop-database", str(apps_dir)], check=False)
                
            return True
            
        except Exception as e:
            print(f"Error setting up file associations: {e}")
            return False