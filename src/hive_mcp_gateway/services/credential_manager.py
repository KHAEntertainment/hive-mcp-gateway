"""Dual-layer credential management with secure keyring storage for Hive MCP Gateway."""

import json
import re
import logging
from typing import Dict, Any, Optional, List, Tuple, Set
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

import keyring
from keyring.errors import KeyringError

logger = logging.getLogger(__name__)


class CredentialType(Enum):
    """Types of credentials."""
    ENVIRONMENT = "environment"  # Non-sensitive environment variables
    SECRET = "secret"           # Sensitive data stored in keyring
    ENV = "environment"         # Alias for ENVIRONMENT (backwards compatibility)


@dataclass
class CredentialEntry:
    """Represents a credential entry with metadata."""
    key: str
    value: str
    credential_type: CredentialType
    description: Optional[str] = None
    auto_detected: bool = False
    server_ids: Optional[Set[str]] = None  # Set of server IDs this credential is associated with
                                # None or empty set means SYSTEM (global credential)
    
    def __post_init__(self):
        """Initialize the server_ids as an empty set if None."""
        if self.server_ids is None:
            self.server_ids = set()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "key": self.key,
            "value": self.value if self.credential_type == CredentialType.ENVIRONMENT else "[MASKED]",
            "type": self.credential_type.value,
            "description": self.description,
            "auto_detected": self.auto_detected,
            "server_ids": list(self.server_ids) if self.server_ids else []
        }


class SensitivityDetector:
    """Detects whether a key-value pair contains sensitive information."""
    
    # Patterns that indicate sensitive data
    SENSITIVE_KEY_PATTERNS = [
        r'.*api[_-]?key.*',
        r'.*secret.*',
        r'.*password.*',
        r'.*passwd.*',
        r'.*token.*',
        r'.*auth.*',
        r'.*credential.*',
        r'.*private[_-]?key.*',
        r'.*access[_-]?key.*',
        r'.*client[_-]?secret.*',
        r'.*oauth.*',
        r'.*bearer.*',
        r'.*jwt.*',
        r'.*session[_-]?id.*',
        r'.*cookie.*',
        r'.*csrf.*',
        r'.*signature.*',
        r'.*hash.*',
        r'.*salt.*',
        r'.*nonce.*'
    ]
    
    # Patterns that indicate non-sensitive configuration
    NON_SENSITIVE_KEY_PATTERNS = [
        r'.*url.*',
        r'.*endpoint.*',
        r'.*host.*',
        r'.*port.*',
        r'.*timeout.*',
        r'.*region.*',
        r'.*zone.*',
        r'.*environment.*',
        r'.*debug.*',
        r'.*verbose.*',
        r'.*log[_-]?level.*',
        r'.*version.*',
        r'.*name.*',
        r'.*description.*',
        r'.*enabled.*',
        r'.*disabled.*',
        r'.*max[_-]?.*',
        r'.*min[_-]?.*',
        r'.*limit.*',
        r'.*retry.*',
        r'.*attempts.*'
    ]
    
    # Value patterns that indicate sensitive data
    SENSITIVE_VALUE_PATTERNS = [
        r'^[A-Za-z0-9+/]{40,}={0,2}$',  # Base64-like strings
        r'^[a-f0-9]{32,}$',             # Hex strings (API keys)
        r'^sk-[a-zA-Z0-9]{32,}$',       # OpenAI API key format
        r'^xoxb-[a-zA-Z0-9-]+$',        # Slack bot token
        r'^ghp_[a-zA-Z0-9]{36}$',       # GitHub personal access token
        r'^Bearer\s+.+$',               # Bearer tokens
        r'^Basic\s+.+$',                # Basic auth
    ]
    
    @classmethod
    def is_sensitive(cls, key: str, value: str) -> Tuple[bool, str]:
        """
        Determine if a key-value pair contains sensitive information.
        
        Returns:
            Tuple of (is_sensitive, reason)
        """
        key_lower = key.lower()
        
        # Check for explicit non-sensitive patterns first
        for pattern in cls.NON_SENSITIVE_KEY_PATTERNS:
            if re.match(pattern, key_lower, re.IGNORECASE):
                return False, f"Key matches non-sensitive pattern: {pattern}"
        
        # Check for sensitive key patterns
        for pattern in cls.SENSITIVE_KEY_PATTERNS:
            if re.match(pattern, key_lower, re.IGNORECASE):
                return True, f"Key matches sensitive pattern: {pattern}"
        
        # Check value patterns
        if value and isinstance(value, str):
            for pattern in cls.SENSITIVE_VALUE_PATTERNS:
                if re.match(pattern, value):
                    return True, f"Value matches sensitive pattern: {pattern}"
            
            # Check for long alphanumeric strings that might be keys
            if len(value) > 20 and re.match(r'^[A-Za-z0-9+/=_-]+$', value):
                return True, "Long alphanumeric string likely to be a key"
        
        return False, "No sensitive patterns detected"


class CredentialManager:
    """Manages credentials with dual-layer storage: environment variables and secure keyring."""
    
    SERVICE_NAME = "hive-mcp-gateway"
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the credential manager."""
        self.config_dir = config_dir or Path.home() / ".hive-mcp-gateway"
        self.config_dir.mkdir(exist_ok=True)
        
        self.env_file = self.config_dir / "environment.json"
        self.metadata_file = self.config_dir / "credential_metadata.json"
        
        self.detector = SensitivityDetector()
        
        # Cache for credentials
        self._env_cache: Dict[str, str] = {}
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        
        self._load_caches()
    
    def _load_caches(self):
        """Load environment variables and metadata from files."""
        # Load environment variables
        if self.env_file.exists():
            try:
                with open(self.env_file, 'r') as f:
                    self._env_cache = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load environment file: {e}")
                self._env_cache = {}
        
        # Load metadata
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    self._metadata_cache = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load metadata file: {e}")
                self._metadata_cache = {}
    
    def _save_caches(self):
        """Save environment variables and metadata to files."""
        try:
            # Save environment variables
            with open(self.env_file, 'w') as f:
                json.dump(self._env_cache, f, indent=2)
            
            # Save metadata
            with open(self.metadata_file, 'w') as f:
                json.dump(self._metadata_cache, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save credential files: {e}")
            raise
    
    def set_credential(self, key: str, value: str, 
                      credential_type: Optional[CredentialType] = None,
                      description: Optional[str] = None,
                      server_ids: Optional[Set[str]] = None) -> CredentialEntry:
        """
        Set a credential with automatic or manual type detection.
        
        Args:
            key: The credential key
            value: The credential value
            credential_type: Force a specific type, or None for auto-detection
            description: Optional description
            server_ids: Optional set of server IDs this credential is associated with
                        None or empty set means SYSTEM (global credential)
            
        Returns:
            CredentialEntry with the stored credential info
        """
        # Auto-detect sensitivity if not specified
        if credential_type is None:
            is_sensitive, reason = self.detector.is_sensitive(key, value)
            credential_type = CredentialType.SECRET if is_sensitive else CredentialType.ENVIRONMENT
            auto_detected = True
            if description is None:
                description = f"Auto-detected as {credential_type.value}: {reason}"
        else:
            auto_detected = False
        
        # Initialize server_ids if None
        if server_ids is None:
            server_ids = set()
            
        entry = CredentialEntry(
            key=key,
            value=value,
            credential_type=credential_type,
            description=description,
            auto_detected=auto_detected,
            server_ids=server_ids
        )
        
        # Store based on type
        if credential_type == CredentialType.SECRET:
            self._set_secret(key, value)
        else:
            self._set_environment(key, value)
        
        # Update metadata
        self._metadata_cache[key] = {
            "type": credential_type.value,
            "description": description,
            "auto_detected": auto_detected,
            "server_ids": list(server_ids) if server_ids else []
        }
        
        self._save_caches()
        
        logger.info(f"Stored credential '{key}' as {credential_type.value}")
        return entry
    
    def get_credential(self, key: str) -> Optional[CredentialEntry]:
        """Get a credential by key."""
        metadata = self._metadata_cache.get(key, {})
        credential_type_str = metadata.get("type", CredentialType.ENVIRONMENT.value)
        credential_type = CredentialType(credential_type_str)
        
        if credential_type == CredentialType.SECRET:
            value = self._get_secret(key)
        else:
            value = self._env_cache.get(key)
        
        if value is None:
            return None
        
        # Get server IDs from metadata
        server_ids_list = metadata.get("server_ids", [])
        server_ids = set(server_ids_list) if server_ids_list else set()
        
        return CredentialEntry(
            key=key,
            value=value,
            credential_type=credential_type,
            description=metadata.get("description"),
            auto_detected=metadata.get("auto_detected", False),
            server_ids=server_ids
        )
    
    def list_credentials(self) -> List[CredentialEntry]:
        """List all credentials."""
        credentials = []
        
        # Get all keys from both sources
        all_keys = set(self._env_cache.keys()) | set(self._metadata_cache.keys())
        
        for key in all_keys:
            entry = self.get_credential(key)
            if entry:
                credentials.append(entry)
        
        return sorted(credentials, key=lambda x: x.key)
    
    def delete_credential(self, key: str) -> bool:
        """Delete a credential."""
        metadata = self._metadata_cache.get(key, {})
        credential_type_str = metadata.get("type", CredentialType.ENVIRONMENT.value)
        credential_type = CredentialType(credential_type_str)
        
        success = False
        
        if credential_type == CredentialType.SECRET:
            success = self._delete_secret(key)
        else:
            if key in self._env_cache:
                del self._env_cache[key]
                success = True
        
        # Remove metadata
        if key in self._metadata_cache:
            del self._metadata_cache[key]
        
        if success:
            self._save_caches()
            logger.info(f"Deleted credential '{key}'")
        
        return success
    
    def get_all_for_export(self) -> Dict[str, str]:
        """Get all credentials as key-value pairs for export to environment."""
        result = {}
        
        # Add environment variables
        result.update(self._env_cache)
        
        # Add secrets from keyring
        for key, metadata in self._metadata_cache.items():
            if metadata.get("type") == CredentialType.SECRET.value:
                value = self._get_secret(key)
                if value:
                    result[key] = value
        
        return result
    
    def import_from_dict(self, credentials: Dict[str, str], 
                        auto_detect: bool = True) -> List[CredentialEntry]:
        """
        Import credentials from a dictionary.
        
        Args:
            credentials: Dictionary of key-value pairs
            auto_detect: Whether to auto-detect sensitivity
            
        Returns:
            List of created credential entries
        """
        entries = []
        
        for key, value in credentials.items():
            if auto_detect:
                entry = self.set_credential(key, value)
            else:
                # Default to environment for manual imports
                entry = self.set_credential(key, value, CredentialType.ENVIRONMENT)
            entries.append(entry)
        
        return entries
    
    def _set_secret(self, key: str, value: str):
        """Store a secret in the keyring."""
        try:
            keyring.set_password(self.SERVICE_NAME, key, value)
        except KeyringError as e:
            logger.error(f"Failed to store secret '{key}': {e}")
            raise
    
    def _get_secret(self, key: str) -> Optional[str]:
        """Get a secret from the keyring."""
        try:
            return keyring.get_password(self.SERVICE_NAME, key)
        except KeyringError as e:
            logger.error(f"Failed to retrieve secret '{key}': {e}")
            return None
    
    def _delete_secret(self, key: str) -> bool:
        """Delete a secret from the keyring."""
        try:
            keyring.delete_password(self.SERVICE_NAME, key)
            return True
        except KeyringError as e:
            logger.error(f"Failed to delete secret '{key}': {e}")
            return False
    
    def _set_environment(self, key: str, value: str):
        """Store an environment variable."""
        self._env_cache[key] = value
    
    def migrate_sensitivity(self, key: str, new_type: CredentialType) -> bool:
        """
        Migrate a credential from one type to another.
        
        Args:
            key: The credential key
            new_type: The new credential type
            
        Returns:
            True if migration successful
        """
        entry = self.get_credential(key)
        if not entry:
            return False
        
        if entry.credential_type == new_type:
            return True  # Already correct type
        
        # Delete from old location
        old_type = entry.credential_type
        if old_type == CredentialType.SECRET:
            self._delete_secret(key)
        else:
            if key in self._env_cache:
                del self._env_cache[key]
        
        # Store in new location
        if new_type == CredentialType.SECRET:
            self._set_secret(key, entry.value)
        else:
            self._set_environment(key, entry.value)
        
        # Update metadata
        self._metadata_cache[key]["type"] = new_type.value
        self._metadata_cache[key]["auto_detected"] = False  # Manual migration
        
        self._save_caches()
        
        logger.info(f"Migrated credential '{key}' from {old_type.value} to {new_type.value}")
        return True
    
    def validate_keyring_access(self) -> Tuple[bool, str]:
        """
        Test keyring access by storing and retrieving a test value.
        
        Returns:
            Tuple of (success, message)
        """
        test_key = "hive_mcp_gateway_test"
        test_value = "test_value_12345"
        
        try:
            # Test store
            keyring.set_password(self.SERVICE_NAME, test_key, test_value)
            
            # Test retrieve
            retrieved = keyring.get_password(self.SERVICE_NAME, test_key)
            if retrieved != test_value:
                return False, "Retrieved value doesn't match stored value"
            
            # Test delete
            keyring.delete_password(self.SERVICE_NAME, test_key)
            
            return True, "Keyring access validated successfully"
            
        except KeyringError as e:
            return False, f"Keyring error: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"

    def get_credentials_for_server(self, server_id: str) -> List[CredentialEntry]:
        """Get all credentials associated with a specific server or SYSTEM credentials.
        
        Args:
            server_id: ID of the server to get credentials for
            
        Returns:
            List of credentials for the specified server and all SYSTEM credentials
        """
        all_credentials = self.list_credentials()
        
        # Filter credentials that are either associated with this server or are SYSTEM credentials
        return [
            cred for cred in all_credentials 
            if not cred.server_ids or server_id in cred.server_ids
        ]
    
    def update_server_association(self, key: str, server_ids: Set[str]) -> bool:
        """Update the server associations for an existing credential.
        
        Args:
            key: The credential key
            server_ids: Set of server IDs this credential should be associated with
                       Empty set means SYSTEM (global credential)
                       
        Returns:
            True if successful, False if credential not found
        """
        if key not in self._metadata_cache:
            return False
        
        # Update metadata
        self._metadata_cache[key]["server_ids"] = list(server_ids) if server_ids else []
        self._save_caches()
        
        logger.info(f"Updated server associations for credential '{key}'")
        return True
    
    def add_server_association(self, key: str, server_id: str) -> bool:
        """Add a server association to an existing credential.
        
        Args:
            key: The credential key
            server_id: Server ID to associate with this credential
            
        Returns:
            True if successful, False if credential not found
        """
        if key not in self._metadata_cache:
            return False
        
        # Get current server IDs
        server_ids_list = self._metadata_cache[key].get("server_ids", [])
        server_ids = set(server_ids_list)
        
        # Add new association
        server_ids.add(server_id)
        
        # Update metadata
        self._metadata_cache[key]["server_ids"] = list(server_ids)
        self._save_caches()
        
        logger.info(f"Added server association '{server_id}' to credential '{key}'")
        return True
    
    def remove_server_association(self, key: str, server_id: str) -> bool:
        """Remove a server association from an existing credential.
        
        Args:
            key: The credential key
            server_id: Server ID to remove association from
            
        Returns:
            True if successful, False if credential not found
        """
        if key not in self._metadata_cache:
            return False
        
        # Get current server IDs
        server_ids_list = self._metadata_cache[key].get("server_ids", [])
        server_ids = set(server_ids_list)
        
        # Remove association if it exists
        if server_id in server_ids:
            server_ids.remove(server_id)
        
        # Update metadata
        self._metadata_cache[key]["server_ids"] = list(server_ids)
        self._save_caches()
        
        logger.info(f"Removed server association '{server_id}' from credential '{key}'")
        return True
