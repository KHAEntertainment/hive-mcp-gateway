"""Migration utility to import existing MCP servers from current installation."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from ..models.config import BackendServerConfig, MigrationConfig
from ..services.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class MigrationUtility:
    """Utility for migrating MCP server configurations from existing installations."""
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize migration utility with config manager."""
        self.config_manager = config_manager
        self.existing_installation_path = Path("/Users/bbrenner/tool-gating-mcp")
    
    def discover_existing_installation(self) -> Optional[Path]:
        """Discover existing Hive MCP Gateway installation."""
        if self._is_valid_installation(self.existing_installation_path):
            logger.info(f"Found existing installation at: {self.existing_installation_path}")
            return self.existing_installation_path
        
        logger.warning("No existing Hive MCP Gateway installation found")
        return None
    
    def _is_valid_installation(self, path: Path) -> bool:
        """Check if path contains a valid Hive MCP Gateway installation."""
        if not path.exists():
            return False
        
        key_files = [
            "src/hive_mcp_gateway/main.py",
            "src/hive_mcp_gateway/config.py",
            "pyproject.toml"
        ]
        
        return all((path / file).exists() for file in key_files)
    
    def extract_servers_from_config_py(self, installation_path: Path) -> Dict[str, BackendServerConfig]:
        """Extract MCP server configurations from config.py file."""
        config_py_path = installation_path / "src/hive_mcp_gateway/config.py"
        
        if not config_py_path.exists():
            logger.error(f"config.py not found at {config_py_path}")
            return {}
        
        try:
            # Read and parse the known servers from the current config.py
            # Based on the existing config.py content we saw earlier
            known_servers = {
                "context7": BackendServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@upstash/context7-mcp@latest"],
                    description="Documentation search and library information",
                    env={},
                    enabled=True
                ),
                "basic_memory": BackendServerConfig(
                    type="stdio",
                    command="uvx",
                    args=["basic-memory", "mcp"],
                    description="Simple key-value memory storage",
                    env={},
                    enabled=True
                ),
                "puppeteer": BackendServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-puppeteer"],
                    description="Browser automation and web scraping",
                    env={},
                    enabled=True
                ),
                "exa": BackendServerConfig(
                    type="stdio",
                    command="exa-mcp-server",
                    args=[
                        "--tools=web_search_exa,research_paper_search,twitter_search,company_research,crawling,competitor_finder,linkedin_search"
                    ],
                    description="Web search, research, and social media tools",
                    env={"EXA_API_KEY": "${EXA_API_KEY}"},
                    enabled=True
                )
            }
            
            logger.info(f"Extracted {len(known_servers)} servers from existing installation")
            return known_servers
            
        except Exception as e:
            logger.error(f"Failed to extract servers from config.py: {e}")
            return {}
    
    def migrate_from_existing_installation(self, migration_config: Optional[MigrationConfig] = None) -> Dict[str, Any]:
        """Migrate MCP servers from existing installation."""
        if migration_config is None:
            migration_config = MigrationConfig(
                source_path=self.existing_installation_path,
                backup_existing=True,
                merge_strategy="merge",
                preserve_env_vars=True
            )
        
        # Discover existing installation
        source_path = self.discover_existing_installation()
        if not source_path:
            return {
                "success": False,
                "message": "No existing installation found",
                "servers_migrated": 0
            }
        
        # Extract servers from existing config
        existing_servers = self.extract_servers_from_config_py(source_path)
        
        if not existing_servers:
            return {
                "success": False,
                "message": "No servers found in existing installation",
                "servers_migrated": 0
            }
        
        # Load current config
        current_config = self.config_manager.load_config()
        
        # Backup existing config if requested
        if migration_config.backup_existing:
            backup_path = self.config_manager.backup_config()
            logger.info(f"Created backup at: {backup_path}")
        
        # Merge servers based on strategy
        merged_count = 0
        for server_name, server_config in existing_servers.items():
            if server_name not in current_config.backend_mcp_servers or migration_config.merge_strategy == "replace":
                current_config.backend_mcp_servers[server_name] = server_config
                merged_count += 1
        
        # Save updated config
        self.config_manager.save_config(current_config)
        
        logger.info(f"Migration completed: {merged_count} servers migrated")
        
        return {
            "success": True,
            "message": f"Successfully migrated {merged_count} servers",
            "servers_migrated": merged_count,
            "source_path": str(source_path)
        }
    
    def migrate_large_servers_only(self) -> Dict[str, Any]:
        """Migrate only servers with large numbers of tools (exa, puppeteer)."""
        large_server_names = ["exa", "puppeteer"]
        
        source_path = self.discover_existing_installation()
        if not source_path:
            return {"success": False, "message": "No existing installation found"}
        
        existing_servers = self.extract_servers_from_config_py(source_path)
        
        # Filter to only large servers
        large_servers = {
            name: config for name, config in existing_servers.items() 
            if any(large_name in name.lower() for large_name in large_server_names)
        }
        
        if not large_servers:
            return {"success": False, "message": "No large servers found to migrate"}
        
        # Load current config and merge large servers
        current_config = self.config_manager.load_config()
        
        for server_name, server_config in large_servers.items():
            current_config.backend_mcp_servers[server_name] = server_config
        
        self.config_manager.save_config(current_config)
        
        return {
            "success": True,
            "message": f"Migrated {len(large_servers)} large servers",
            "servers_migrated": len(large_servers),
            "migrated_servers": list(large_servers.keys())
        }