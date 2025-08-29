"""Platform detection and manager factory."""

import platform
import sys
from typing import Optional

from .base import PlatformManagerBase, SupportedPlatform


def get_current_platform() -> SupportedPlatform:
    """Get the current platform."""
    system = platform.system()
    
    if system == "Darwin":
        return SupportedPlatform.MACOS
    elif system == "Windows":
        return SupportedPlatform.WINDOWS
    elif system == "Linux":
        return SupportedPlatform.LINUX
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def get_platform_manager() -> PlatformManagerBase:
    """Get the appropriate platform manager for the current system."""
    current_platform = get_current_platform()
    
    if current_platform == SupportedPlatform.MACOS:
        from .macos import MacOSPlatformManager
        return MacOSPlatformManager()
    elif current_platform == SupportedPlatform.WINDOWS:
        from .windows import WindowsPlatformManager
        return WindowsPlatformManager()
    elif current_platform == SupportedPlatform.LINUX:
        from .linux import LinuxPlatformManager
        return LinuxPlatformManager()
    else:
        raise RuntimeError(f"No platform manager available for {current_platform.value}")


def is_platform_supported(platform_name: Optional[str] = None) -> bool:
    """Check if a platform is supported."""
    if platform_name is None:
        platform_name = platform.system()
    
    try:
        supported_platforms = [p.value for p in SupportedPlatform]
        return platform_name in supported_platforms
    except Exception:
        return False


def get_platform_capabilities() -> dict:
    """Get capabilities for all supported platforms."""
    return {
        "macos": {
            "autostart": True,
            "system_tray": True,
            "file_associations": True,
            "app_bundle": True,
            "installer": True,  # DMG
            "code_signing": True,
            "notarization": True
        },
        "windows": {
            "autostart": True,
            "system_tray": True,
            "file_associations": True,
            "app_bundle": False,
            "installer": True,  # MSI/NSIS
            "code_signing": True,
            "notarization": False
        },
        "linux": {
            "autostart": True,
            "system_tray": True,
            "file_associations": True,
            "app_bundle": True,  # AppImage
            "installer": True,  # DEB/RPM
            "code_signing": False,
            "notarization": False
        }
    }