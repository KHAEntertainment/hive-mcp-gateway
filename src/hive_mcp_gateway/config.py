"""Configuration management for Hive MCP Gateway"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # API Keys
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-4-sonnet-latest"

    # File paths
    mcp_servers_path: str = "mcp-servers.json"
    api_keys_path: str = ".api-keys.json"

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8001

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    @property
    def has_anthropic_key(self) -> bool:
        """Check if Anthropic API key is configured"""
        return bool(self.anthropic_api_key)

    def get_api_key(self, service: str) -> str | None:
        """Get API key for a service from environment or secure storage"""
        # First check environment variables
        env_key = f"{service.upper()}_API_KEY"
        if env_value := os.getenv(env_key):
            return env_value

        # Then check API keys file
        api_keys_file = Path(self.api_keys_path)
        if api_keys_file.exists():
            import json

            with open(api_keys_file) as f:
                keys = json.load(f)
                return keys.get(service)

        return None


# Global settings instance
settings = Settings()


def get_config() -> Settings:
    """Get the global configuration instance."""
    return settings

# Note: Legacy MCP_SERVERS constant removed. Server definitions should come from
# the main configuration file (YAML/JSON) and/or via the GUI. Environment
# variables may be referenced in config using ${VAR} and will be substituted
# at load time by ConfigManager.
