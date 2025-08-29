"""Base platform manager abstract classes for cross-platform functionality."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class SupportedPlatform(Enum):
    """Supported platforms for Hive MCP Gateway."""
    MACOS = "Darwin"
    WINDOWS = "Windows" 
    LINUX = "Linux"


@dataclass
class PlatformInfo:
    """Information about the current platform."""
    platform: SupportedPlatform
    version: str
    architecture: str
    python_version: str
    is_supported: bool


@dataclass
class ApplicationPaths:
    """Platform-specific application paths."""
    executable_path: Optional[Path]
    config_dir: Path
    data_dir: Path
    cache_dir: Path
    log_dir: Path
    temp_dir: Path


@dataclass
class BuildConfiguration:
    """Platform-specific build configuration."""
    output_format: str  # .app, .exe, .AppImage, etc.
    build_command: List[str]
    package_command: Optional[List[str]]
    installer_command: Optional[List[str]]
    required_tools: List[str]
    icon_format: str
    executable_extension: str


class PlatformManagerBase(ABC):
    """Abstract base class for platform-specific managers."""
    
    def __init__(self):
        """Initialize platform manager."""
        self.platform_info = self.get_platform_info()
    
    @abstractmethod
    def get_platform_info(self) -> PlatformInfo:
        """Get information about the current platform."""
        pass
    
    @abstractmethod
    def get_application_paths(self) -> ApplicationPaths:
        """Get platform-specific application paths."""
        pass
    
    @abstractmethod
    def get_build_configuration(self) -> BuildConfiguration:
        """Get platform-specific build configuration."""
        pass
    
    @abstractmethod
    def setup_autostart(self, app_path: Path, enabled: bool = True) -> bool:
        """Setup application autostart functionality."""
        pass
    
    @abstractmethod
    def is_autostart_enabled(self) -> bool:
        """Check if autostart is enabled."""
        pass
    
    @abstractmethod
    def get_system_dependencies(self) -> Dict[str, bool]:
        """Get platform-specific system dependencies status."""
        pass
    
    @abstractmethod
    def install_system_dependencies(self) -> bool:
        """Install platform-specific system dependencies."""
        pass
    
    @abstractmethod
    def create_application_bundle(self, source_dir: Path, output_dir: Path) -> bool:
        """Create platform-specific application bundle."""
        pass
    
    @abstractmethod
    def create_installer(self, bundle_path: Path, output_dir: Path) -> bool:
        """Create platform-specific installer."""
        pass
    
    @abstractmethod
    def get_ide_integration_paths(self) -> Dict[str, List[Path]]:
        """Get paths for IDE integration."""
        pass
    
    @abstractmethod
    def setup_file_associations(self, extensions: List[str]) -> bool:
        """Setup file type associations."""
        pass
    
    def validate_platform_support(self) -> Tuple[bool, List[str]]:
        """Validate platform support and return issues."""
        issues = []
        
        if not self.platform_info.is_supported:
            issues.append(f"Platform {self.platform_info.platform.value} is not officially supported")
        
        # Check required tools
        build_config = self.get_build_configuration()
        missing_tools = []
        
        for tool in build_config.required_tools:
            if not self._check_tool_available(tool):
                missing_tools.append(tool)
        
        if missing_tools:
            issues.append(f"Missing required tools: {', '.join(missing_tools)}")
        
        return len(issues) == 0, issues
    
    def _check_tool_available(self, tool: str) -> bool:
        """Check if a tool is available in PATH."""
        import subprocess
        try:
            subprocess.run([tool, "--version"], capture_output=True, timeout=5)
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return False
    
    def get_recommended_installation_path(self) -> Path:
        """Get recommended installation path for this platform."""
        paths = self.get_application_paths()
        return paths.executable_path.parent if paths.executable_path else Path("/usr/local/bin")
    
    def get_platform_specific_config(self) -> Dict[str, Any]:
        """Get platform-specific configuration options."""
        return {
            "platform": self.platform_info.platform.value,
            "version": self.platform_info.version,
            "architecture": self.platform_info.architecture,
            "paths": {
                "config": str(self.get_application_paths().config_dir),
                "data": str(self.get_application_paths().data_dir),
                "cache": str(self.get_application_paths().cache_dir),
                "logs": str(self.get_application_paths().log_dir)
            },
            "build": {
                "output_format": self.get_build_configuration().output_format,
                "executable_extension": self.get_build_configuration().executable_extension,
                "icon_format": self.get_build_configuration().icon_format
            }
        }