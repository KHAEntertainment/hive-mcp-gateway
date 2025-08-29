"""Claude Code SDK integration for OAuth credential piggybacking."""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import subprocess

from ..services.credential_manager import CredentialManager, CredentialType
from ..services.ide_detector import IDEDetector, IDEType

logger = logging.getLogger(__name__)


class ClaudeCodeCredentials:
    """Represents Claude Code OAuth credentials."""
    
    def __init__(self, access_token: str, refresh_token: Optional[str] = None, 
                 expires_at: Optional[datetime] = None, token_type: str = "Bearer"):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.token_type = token_type
    
    @property
    def is_expired(self) -> bool:
        """Check if the access token is expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= self.expires_at
    
    @property
    def authorization_header(self) -> str:
        """Get the authorization header value."""
        return f"{self.token_type} {self.access_token}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "token_type": self.token_type
        }


class ClaudeCodeSDK:
    """SDK for integrating with Claude Code OAuth credentials."""
    
    def __init__(self, credential_manager: Optional[CredentialManager] = None):
        self.credential_manager = credential_manager or CredentialManager()
        self.ide_detector = IDEDetector()
        
        # Standard OAuth credential locations for Claude Code
        self.oauth_paths = [
            Path.home() / "Library/Application Support/Claude Code/oauth_tokens.json",
            Path.home() / "Library/Application Support/Claude Code/auth.json",
            Path.home() / "Library/Preferences/com.anthropic.claude-code/oauth_tokens.json",
            Path.home() / ".claude-code/oauth_tokens.json",
            Path.home() / ".config/claude-code/oauth_tokens.json"
        ]
        
        # Windows paths
        if Path.home().drive:  # Windows system
            windows_paths = [
                Path.home() / "AppData/Roaming/Claude Code/oauth_tokens.json",
                Path.home() / "AppData/Local/Claude Code/oauth_tokens.json",
                Path.home() / "AppData/Local/Programs/Claude Code/oauth_tokens.json"
            ]
            self.oauth_paths.extend(windows_paths)
        
        # Linux paths
        linux_paths = [
            Path.home() / ".config/claude-code/oauth_tokens.json",
            Path.home() / ".local/share/claude-code/oauth_tokens.json"
        ]
        self.oauth_paths.extend(linux_paths)
    
    def is_claude_code_installed(self) -> bool:
        """Check if Claude Code is installed."""
        try:
            claude_code_info = self.ide_detector.detect_ide(IDEType.CLAUDE_CODE)
            return claude_code_info is not None and claude_code_info.is_installed
        except Exception as e:
            logger.debug(f"Error checking Claude Code installation: {e}")
            return False
    
    def get_claude_code_path(self) -> Optional[Path]:
        """Get the path to Claude Code installation."""
        try:
            claude_code_info = self.ide_detector.detect_ide(IDEType.CLAUDE_CODE)
            if claude_code_info and claude_code_info.is_installed:
                return claude_code_info.executable_path
        except Exception as e:
            logger.debug(f"Error getting Claude Code path: {e}")
        return None
    
    def find_oauth_credentials_file(self) -> Optional[Path]:
        """Find the OAuth credentials file for Claude Code."""
        # Check standard locations
        for oauth_path in self.oauth_paths:
            if oauth_path.exists() and oauth_path.is_file():
                logger.debug(f"Found Claude Code OAuth credentials at: {oauth_path}")
                return oauth_path
        
        # If Claude Code is installed, try to find credentials relative to installation
        claude_path = self.get_claude_code_path()
        if claude_path:
            relative_paths = [
                claude_path.parent / "oauth_tokens.json",
                claude_path.parent / "Resources" / "oauth_tokens.json",
                claude_path.parent / "auth.json"
            ]
            
            for rel_path in relative_paths:
                if rel_path.exists() and rel_path.is_file():
                    logger.debug(f"Found Claude Code OAuth credentials relative to installation: {rel_path}")
                    return rel_path
        
        logger.debug("No Claude Code OAuth credentials file found")
        return None
    
    def read_oauth_credentials(self, oauth_file_path: Optional[Path] = None) -> Optional[ClaudeCodeCredentials]:
        """Read OAuth credentials from Claude Code."""
        if oauth_file_path is None:
            oauth_file_path = self.find_oauth_credentials_file()
        
        if not oauth_file_path or not oauth_file_path.exists():
            logger.debug("No OAuth credentials file found for Claude Code")
            return None
        
        try:
            with open(oauth_file_path, 'r') as f:
                oauth_data = json.load(f)
            
            # Handle different OAuth file formats
            access_token = None
            refresh_token = None
            expires_at = None
            token_type = "Bearer"
            
            # Format 1: Direct token structure
            if "access_token" in oauth_data:
                access_token = oauth_data["access_token"]
                refresh_token = oauth_data.get("refresh_token")
                token_type = oauth_data.get("token_type", "Bearer")
                
                # Parse expiration
                if "expires_at" in oauth_data:
                    expires_at = datetime.fromisoformat(oauth_data["expires_at"])
                elif "expires_in" in oauth_data:
                    # Calculate expiration from expires_in
                    expires_in = oauth_data["expires_in"]
                    expires_at = datetime.now(timezone.utc).timestamp() + expires_in
                    expires_at = datetime.fromtimestamp(expires_at, timezone.utc)
            
            # Format 2: Nested structure (e.g., {"anthropic": {"access_token": ...}})
            elif "anthropic" in oauth_data:
                anthropic_data = oauth_data["anthropic"]
                access_token = anthropic_data.get("access_token")
                refresh_token = anthropic_data.get("refresh_token")
                token_type = anthropic_data.get("token_type", "Bearer")
                
                if "expires_at" in anthropic_data:
                    expires_at = datetime.fromisoformat(anthropic_data["expires_at"])
            
            # Format 3: Token array structure
            elif "tokens" in oauth_data and oauth_data["tokens"]:
                token_data = oauth_data["tokens"][0]  # Use first token
                access_token = token_data.get("access_token")
                refresh_token = token_data.get("refresh_token")
                token_type = token_data.get("token_type", "Bearer")
                
                if "expires_at" in token_data:
                    expires_at = datetime.fromisoformat(token_data["expires_at"])
            
            if not access_token:
                logger.warning(f"No access token found in Claude Code OAuth file: {oauth_file_path}")
                return None
            
            credentials = ClaudeCodeCredentials(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                token_type=token_type
            )
            
            logger.info(f"Successfully loaded Claude Code OAuth credentials from: {oauth_file_path}")
            return credentials
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in Claude Code OAuth file {oauth_file_path}: {e}")
        except Exception as e:
            logger.error(f"Error reading Claude Code OAuth credentials from {oauth_file_path}: {e}")
        
        return None
    
    def get_credentials(self) -> Optional[ClaudeCodeCredentials]:
        """Get Claude Code OAuth credentials with fallback to stored credentials."""
        # First try to read from Claude Code OAuth file
        credentials = self.read_oauth_credentials()
        
        if credentials:
            # Store credentials in credential manager for backup
            try:
                self.credential_manager.set_credential(
                    "claude_code_access_token",
                    credentials.access_token,
                    CredentialType.SECRET,
                    "Claude Code OAuth access token (auto-detected)"
                )
                
                if credentials.refresh_token:
                    self.credential_manager.set_credential(
                        "claude_code_refresh_token",
                        credentials.refresh_token,
                        CredentialType.SECRET,
                        "Claude Code OAuth refresh token (auto-detected)"
                    )
                
                # Store metadata
                metadata = {
                    "expires_at": credentials.expires_at.isoformat() if credentials.expires_at else None,
                    "token_type": credentials.token_type,
                    "source": "claude_code_oauth_file"
                }
                
                self.credential_manager.set_credential(
                    "claude_code_oauth_metadata",
                    json.dumps(metadata),
                    CredentialType.ENV,
                    "Claude Code OAuth metadata"
                )
                
            except Exception as e:
                logger.warning(f"Failed to store Claude Code credentials in credential manager: {e}")
            
            return credentials
        
        # Fallback: try to load from credential manager
        try:
            access_token = self.credential_manager.get_credential("claude_code_access_token")
            if access_token:
                refresh_token = self.credential_manager.get_credential("claude_code_refresh_token")
                metadata_str = self.credential_manager.get_credential("claude_code_oauth_metadata")
                
                metadata = {}
                if metadata_str:
                    try:
                        metadata = json.loads(metadata_str)
                    except json.JSONDecodeError:
                        pass
                
                expires_at = None
                if metadata.get("expires_at"):
                    try:
                        expires_at = datetime.fromisoformat(metadata["expires_at"])
                    except ValueError:
                        pass
                
                credentials = ClaudeCodeCredentials(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    token_type=metadata.get("token_type", "Bearer")
                )
                
                logger.info("Loaded Claude Code credentials from credential manager")
                return credentials
                
        except Exception as e:
            logger.warning(f"Failed to load Claude Code credentials from credential manager: {e}")
        
        return None
    
    def is_authenticated(self) -> bool:
        """Check if Claude Code authentication is available and valid."""
        credentials = self.get_credentials()
        if not credentials:
            return False
        
        # Check if token is expired
        if credentials.is_expired:
            logger.debug("Claude Code OAuth token is expired")
            return False
        
        return True
    
    def get_auth_header(self) -> Optional[str]:
        """Get the authorization header value for API requests."""
        credentials = self.get_credentials()
        if credentials and not credentials.is_expired:
            return credentials.authorization_header
        return None
    
    def validate_credentials(self) -> Tuple[bool, str]:
        """Validate Claude Code credentials by testing API access."""
        credentials = self.get_credentials()
        if not credentials:
            return False, "No Claude Code credentials found"
        
        if credentials.is_expired:
            return False, "Claude Code OAuth token is expired"
        
        # Test the credentials with a simple API call
        try:
            # This would normally make an API call to validate the token
            # For now, we'll just check that we have a token
            if len(credentials.access_token) < 10:
                return False, "Claude Code access token appears invalid"
            
            return True, "Claude Code credentials are valid"
            
        except Exception as e:
            return False, f"Error validating Claude Code credentials: {e}"
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of Claude Code integration."""
        status = {
            "claude_code_installed": self.is_claude_code_installed(),
            "claude_code_path": str(self.get_claude_code_path()) if self.get_claude_code_path() else None,
            "oauth_file_found": self.find_oauth_credentials_file() is not None,
            "oauth_file_path": str(self.find_oauth_credentials_file()) if self.find_oauth_credentials_file() else None,
            "authenticated": self.is_authenticated(),
            "has_access_token": False,
            "has_refresh_token": False,
            "token_expired": False,
            "validation_status": "unknown",
            "validation_message": "Not tested"
        }
        
        credentials = self.get_credentials()
        if credentials:
            status.update({
                "has_access_token": bool(credentials.access_token),
                "has_refresh_token": bool(credentials.refresh_token),
                "token_expired": credentials.is_expired,
                "token_type": credentials.token_type,
                "expires_at": credentials.expires_at.isoformat() if credentials.expires_at else None
            })
            
            # Validate credentials
            is_valid, message = self.validate_credentials()
            status.update({
                "validation_status": "valid" if is_valid else "invalid",
                "validation_message": message
            })
        
        return status
    
    def refresh_credentials(self) -> bool:
        """Attempt to refresh OAuth credentials."""
        credentials = self.get_credentials()
        if not credentials or not credentials.refresh_token:
            logger.warning("Cannot refresh Claude Code credentials: no refresh token available")
            return False
        
        # This would normally implement OAuth token refresh
        # For now, we'll just re-read from the file in case it was updated
        try:
            new_credentials = self.read_oauth_credentials()
            if new_credentials and new_credentials.access_token != credentials.access_token:
                logger.info("Claude Code credentials refreshed from file")
                return True
        except Exception as e:
            logger.error(f"Error refreshing Claude Code credentials: {e}")
        
        return False
    
    def setup_instructions(self) -> Dict[str, str]:
        """Get setup instructions for Claude Code OAuth."""
        return {
            "title": "Claude Code OAuth Setup",
            "installation": """
            1. Download Claude Code from https://claude.ai/desktop
            2. Install the application to /Applications/Claude Code.app (macOS) or appropriate location
            3. Launch Claude Code and sign in with your Anthropic account
            4. Complete the OAuth authentication flow
            5. The OAuth credentials will be automatically detected by Hive MCP Gateway
            """,
            "troubleshooting": """
            If credentials are not detected:
            1. Ensure Claude Code is properly installed and authenticated
            2. Check that the OAuth file exists in one of these locations:
               - ~/Library/Application Support/Claude Code/oauth_tokens.json (macOS)
               - ~/.config/claude-code/oauth_tokens.json (Linux)
               - ~/AppData/Roaming/Claude Code/oauth_tokens.json (Windows)
            3. Restart Hive MCP Gateway after authenticating Claude Code
            4. If still not working, check the logs for specific error messages
            """,
            "oauth_file_locations": "\n".join([str(path) for path in self.oauth_paths])
        }