"""Platform-specific implementations for Hive MCP Gateway."""

from .base import PlatformManagerBase
from .detection import get_platform_manager

__all__ = ["PlatformManagerBase", "get_platform_manager"]