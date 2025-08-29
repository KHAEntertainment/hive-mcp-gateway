"""Configuration injection system for IDE integration with backup and restore capabilities."""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .ide_detector import IDEDetector, IDEInfo, IDEType

logger = logging.getLogger(__name__)


class InjectionResult(Enum):
    """Results of configuration injection."""
    SUCCESS = "success"
    BACKUP_FAILED = "backup_failed"
    INJECTION_FAILED = "injection_failed"
    CONFIG_INVALID = "config_invalid"
    ACCESS_DENIED = "access_denied"
    CONFLICT = "conflict"


@dataclass
class InjectionOperation:
    """Represents a configuration injection operation."""
    ide_info: IDEInfo
    operation_type: str  # "inject", "update", "remove"
    server_name: str
    server_config: Dict[str, Any]
    backup_path: Optional[Path] = None
    timestamp: Optional[datetime] = None
    result: Optional[InjectionResult] = None
    error_message: Optional[str] = None


class ConfigInjector:
    """Handles configuration injection into IDE configs with backup/restore."""
    
    def __init__(self, backup_dir: Optional[Path] = None):
        """Initialize the config injector."""
        self.detector = IDEDetector()
        
        # Setup backup directory
        if backup_dir is None:
            backup_dir = Path.home() / ".hive-mcp-gateway" / "ide_backups"
        
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Track operations
        self.operation_history: List[InjectionOperation] = []
    
    def inject_hive_config(self, ide_info: IDEInfo, 
                          server_name: str = "hive-mcp-gateway",
                          force: bool = False) -> InjectionOperation:
        """
        Inject Hive MCP Gateway configuration into an IDE.
        
        Args:
            ide_info: IDE information
            server_name: Name for the MCP server entry
            force: Whether to overwrite existing server with same name
            
        Returns:
            InjectionOperation with results
        """
        operation = InjectionOperation(
            ide_info=ide_info,
            operation_type="inject",
            server_name=server_name,
            server_config=self._get_hive_config(ide_info),
            timestamp=datetime.now()
        )
        
        try:
            # Validate access
            can_access, access_msg = self.detector.validate_config_access(ide_info)
            if not can_access:
                operation.result = InjectionResult.ACCESS_DENIED
                operation.error_message = access_msg
                return operation
            
            # Check for conflicts
            if not force and server_name in ide_info.mcp_servers:
                operation.result = InjectionResult.CONFLICT
                operation.error_message = f"Server '{server_name}' already exists. Use force=True to overwrite."
                return operation
            
            # Create backup
            backup_path = self._create_backup(ide_info)
            if backup_path is None:
                operation.result = InjectionResult.BACKUP_FAILED
                operation.error_message = "Failed to create backup"
                return operation
            
            operation.backup_path = backup_path
            
            # Perform injection
            success = self._inject_config(ide_info, server_name, operation.server_config)
            if success:
                operation.result = InjectionResult.SUCCESS
                logger.info(f"Successfully injected Hive MCP Gateway config into {ide_info.name}")
            else:
                operation.result = InjectionResult.INJECTION_FAILED
                operation.error_message = "Failed to inject configuration"
                
                # Attempt to restore backup on failure
                self._restore_backup(ide_info, backup_path)
            
        except Exception as e:
            operation.result = InjectionResult.INJECTION_FAILED
            operation.error_message = str(e)
            logger.error(f"Configuration injection failed: {e}")
            
            # Attempt to restore backup on exception
            if operation.backup_path:
                self._restore_backup(ide_info, operation.backup_path)
        
        self.operation_history.append(operation)
        return operation
    
    def remove_hive_config(self, ide_info: IDEInfo, 
                          server_name: str = "hive-mcp-gateway") -> InjectionOperation:
        """
        Remove Hive MCP Gateway configuration from an IDE.
        
        Args:
            ide_info: IDE information
            server_name: Name of the MCP server entry to remove
            
        Returns:
            InjectionOperation with results
        """
        operation = InjectionOperation(
            ide_info=ide_info,
            operation_type="remove",
            server_name=server_name,
            server_config={},
            timestamp=datetime.now()
        )
        
        try:
            # Validate access
            can_access, access_msg = self.detector.validate_config_access(ide_info)
            if not can_access:
                operation.result = InjectionResult.ACCESS_DENIED
                operation.error_message = access_msg
                return operation
            
            # Check if server exists
            if server_name not in ide_info.mcp_servers:
                operation.result = InjectionResult.SUCCESS  # Already removed
                operation.error_message = f"Server '{server_name}' not found (already removed)"
                return operation
            
            # Create backup
            backup_path = self._create_backup(ide_info)
            if backup_path is None:
                operation.result = InjectionResult.BACKUP_FAILED
                operation.error_message = "Failed to create backup"
                return operation
            
            operation.backup_path = backup_path
            
            # Perform removal
            success = self._remove_config(ide_info, server_name)
            if success:
                operation.result = InjectionResult.SUCCESS
                logger.info(f"Successfully removed Hive MCP Gateway config from {ide_info.name}")
            else:
                operation.result = InjectionResult.INJECTION_FAILED
                operation.error_message = "Failed to remove configuration"
                
                # Attempt to restore backup on failure
                self._restore_backup(ide_info, backup_path)
            
        except Exception as e:
            operation.result = InjectionResult.INJECTION_FAILED
            operation.error_message = str(e)
            logger.error(f"Configuration removal failed: {e}")
            
            # Attempt to restore backup on exception
            if operation.backup_path:
                self._restore_backup(ide_info, operation.backup_path)
        
        self.operation_history.append(operation)
        return operation
    
    def _get_hive_config(self, ide_info: IDEInfo) -> Dict[str, Any]:
        """Get Hive MCP Gateway configuration for the specific IDE."""
        if ide_info.ide_type == IDEType.CLAUDE_DESKTOP:
            return {
                "command": "mcp-proxy",
                "args": ["http://localhost:8001/mcp"],
                "env": {}
            }
        elif ide_info.ide_type in [IDEType.VS_CODE, IDEType.VS_CODE_INSIDERS, IDEType.CURSOR]:
            # For VS Code/Cursor with Continue extension
            return {
                "command": "mcp-proxy",
                "args": ["http://localhost:8001/mcp"],
                "env": {}
            }
        
        return {}
    
    def _create_backup(self, ide_info: IDEInfo) -> Optional[Path]:
        """Create a backup of the IDE configuration."""
        try:
            config_path = ide_info.config_path
            
            if not config_path.exists():
                # Create empty config if it doesn't exist
                config_path.parent.mkdir(parents=True, exist_ok=True)
                
                if ide_info.ide_type == IDEType.CLAUDE_DESKTOP:
                    initial_config = {"mcpServers": {}}
                else:
                    initial_config = {}
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(initial_config, f, indent=2)
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ide_name = ide_info.ide_type.value
            backup_filename = f"{ide_name}_config_{timestamp}.json"
            backup_path = self.backup_dir / backup_filename
            
            # Copy the config file
            shutil.copy2(config_path, backup_path)
            
            logger.info(f"Created backup: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create backup for {ide_info.name}: {e}")
            return None
    
    def _inject_config(self, ide_info: IDEInfo, server_name: str, 
                      server_config: Dict[str, Any]) -> bool:
        """Inject configuration into the IDE config file."""
        try:
            config_path = ide_info.config_path
            
            # Load existing config
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # Inject based on IDE type
            if ide_info.ide_type == IDEType.CLAUDE_DESKTOP:
                if "mcpServers" not in config:
                    config["mcpServers"] = {}
                config["mcpServers"][server_name] = server_config
                
            elif ide_info.ide_type in [IDEType.VS_CODE, IDEType.VS_CODE_INSIDERS, IDEType.CURSOR]:
                # For Continue extension
                if "continue" not in config:
                    config["continue"] = {}
                if "mcpServers" not in config["continue"]:
                    config["continue"]["mcpServers"] = {}
                config["continue"]["mcpServers"][server_name] = server_config
            
            # Save updated config
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to inject config into {ide_info.name}: {e}")
            return False
    
    def _remove_config(self, ide_info: IDEInfo, server_name: str) -> bool:
        """Remove configuration from the IDE config file."""
        try:
            config_path = ide_info.config_path
            
            if not config_path.exists():
                return True  # Nothing to remove
            
            # Load existing config
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Remove based on IDE type
            removed = False
            if ide_info.ide_type == IDEType.CLAUDE_DESKTOP:
                if "mcpServers" in config and server_name in config["mcpServers"]:
                    del config["mcpServers"][server_name]
                    removed = True
                    
            elif ide_info.ide_type in [IDEType.VS_CODE, IDEType.VS_CODE_INSIDERS, IDEType.CURSOR]:
                if ("continue" in config and 
                    "mcpServers" in config["continue"] and 
                    server_name in config["continue"]["mcpServers"]):
                    del config["continue"]["mcpServers"][server_name]
                    removed = True
            
            if removed:
                # Save updated config
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove config from {ide_info.name}: {e}")
            return False
    
    def _restore_backup(self, ide_info: IDEInfo, backup_path: Path) -> bool:
        """Restore configuration from backup."""
        try:
            if not backup_path.exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            config_path = ide_info.config_path
            shutil.copy2(backup_path, config_path)
            
            logger.info(f"Restored backup from {backup_path} to {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False
    
    def list_backups(self, ide_type: Optional[IDEType] = None) -> List[Path]:
        """List available backups."""
        try:
            backups = []
            pattern = f"{ide_type.value}_config_*.json" if ide_type else "*_config_*.json"
            
            for backup_file in self.backup_dir.glob(pattern):
                backups.append(backup_file)
            
            return sorted(backups, key=lambda x: x.stat().st_mtime, reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
    
    def restore_from_backup(self, ide_info: IDEInfo, backup_path: Path) -> bool:
        """Restore configuration from a specific backup."""
        return self._restore_backup(ide_info, backup_path)
    
    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """
        Clean up old backup files, keeping only the most recent ones.
        
        Args:
            keep_count: Number of backups to keep per IDE
            
        Returns:
            Number of files deleted
        """
        deleted_count = 0
        
        try:
            # Group backups by IDE type
            ide_backups = {}
            for backup_file in self.backup_dir.glob("*_config_*.json"):
                parts = backup_file.stem.split('_')
                if len(parts) >= 3:
                    ide_name = parts[0]
                    if ide_name not in ide_backups:
                        ide_backups[ide_name] = []
                    ide_backups[ide_name].append(backup_file)
            
            # Clean up each IDE's backups
            for ide_name, backups in ide_backups.items():
                # Sort by modification time (newest first)
                backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                
                # Delete old backups beyond keep_count
                for old_backup in backups[keep_count:]:
                    try:
                        old_backup.unlink()
                        deleted_count += 1
                        logger.info(f"Deleted old backup: {old_backup}")
                    except Exception as e:
                        logger.error(f"Failed to delete backup {old_backup}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup backups: {e}")
        
        return deleted_count
    
    def get_injection_summary(self, ide_info: IDEInfo) -> Dict[str, Any]:
        """Get a summary of what would be injected."""
        hive_config = self._get_hive_config(ide_info)
        
        summary = {
            "ide_name": ide_info.name,
            "ide_type": ide_info.ide_type.value,
            "config_path": str(ide_info.config_path),
            "config_exists": ide_info.config_exists,
            "current_servers": list(ide_info.mcp_servers.keys()),
            "hive_config": hive_config,
            "backup_available": ide_info.backup_available,
            "conflicts": ["hive-mcp-gateway"] if "hive-mcp-gateway" in ide_info.mcp_servers else []
        }
        
        return summary
    
    def validate_injection(self, ide_info: IDEInfo) -> Tuple[bool, List[str]]:
        """
        Validate that injection can be performed.
        
        Returns:
            Tuple of (can_inject, list_of_issues)
        """
        issues = []
        
        # Check IDE installation
        if not ide_info.is_installed:
            issues.append(f"{ide_info.name} is not installed")
        
        # Check config access
        can_access, access_msg = self.detector.validate_config_access(ide_info)
        if not can_access:
            issues.append(f"Cannot access config: {access_msg}")
        
        # Check backup directory
        if not self.backup_dir.exists() or not self.backup_dir.is_dir():
            issues.append(f"Backup directory not accessible: {self.backup_dir}")
        
        # Check write permissions
        try:
            test_file = self.backup_dir / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
        except Exception:
            issues.append("Cannot write to backup directory")
        
        can_inject = len(issues) == 0
        return can_inject, issues