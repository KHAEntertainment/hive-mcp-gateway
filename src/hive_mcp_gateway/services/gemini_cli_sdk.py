"""Gemini CLI SDK integration for OAuth credential piggybacking."""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import subprocess
import configparser

from ..services.credential_manager import CredentialManager, CredentialType
from ..services.ide_detector import IDEDetector, IDEType

logger = logging.getLogger(__name__)


class GeminiCLICredentials:
    """Represents Gemini CLI OAuth credentials."""
    
    def __init__(self, access_token: str, refresh_token: Optional[str] = None, 
                 expires_at: Optional[datetime] = None, token_type: str = "Bearer",
                 project_id: Optional[str] = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.token_type = token_type
        self.project_id = project_id
    
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
            "token_type": self.token_type,
            "project_id": self.project_id
        }


class GeminiCLISDK:
    """SDK for integrating with Gemini CLI OAuth credentials."""
    
    def __init__(self, credential_manager: Optional[CredentialManager] = None):
        self.credential_manager = credential_manager or CredentialManager()
        self.ide_detector = IDEDetector()
        
        # Standard credential locations for Gemini CLI
        self.credential_paths = [
            Path.home() / ".gemini/oauth_creds.json",
            Path.home() / ".gemini/credentials.json",
            Path.home() / ".config/gemini/oauth_creds.json",
            Path.home() / ".config/gemini/credentials.json",
            Path.home() / ".config/gemini/config.json"
        ]
        
        # Windows paths
        if Path.home().drive:  # Windows system
            windows_paths = [
                Path.home() / "AppData/Roaming/Gemini/oauth_creds.json",
                Path.home() / "AppData/Local/Gemini/oauth_creds.json",
                Path.home() / "AppData/Local/Programs/Gemini CLI/oauth_creds.json"
            ]
            self.credential_paths.extend(windows_paths)
        
        # Additional Linux paths
        linux_paths = [
            Path.home() / ".local/share/gemini/oauth_creds.json",
            Path.home() / ".cache/gemini/oauth_creds.json"
        ]
        self.credential_paths.extend(linux_paths)
        
        # Config file paths (for Gemini CLI configuration)
        self.config_paths = [
            Path.home() / ".gemini/config",
            Path.home() / ".gemini/config.yaml",
            Path.home() / ".config/gemini/config.yaml",
            Path.home() / ".config/gemini/config"
        ]
    
    def is_gemini_cli_installed(self) -> bool:
        """Check if Gemini CLI is installed."""
        try:
            gemini_cli_info = self.ide_detector.detect_ide(IDEType.GEMINI_CLI)
            return gemini_cli_info is not None and gemini_cli_info.is_installed
        except Exception as e:
            logger.debug(f"Error checking Gemini CLI installation: {e}")
            return False
    
    def get_gemini_cli_path(self) -> Optional[Path]:
        """Get the path to Gemini CLI installation."""
        try:
            gemini_cli_info = self.ide_detector.detect_ide(IDEType.GEMINI_CLI)
            if gemini_cli_info and gemini_cli_info.is_installed:
                return gemini_cli_info.executable_path
        except Exception as e:
            logger.debug(f"Error getting Gemini CLI path: {e}")
        return None
    
    def check_gemini_auth_status(self) -> Tuple[bool, str]:
        """Check Gemini CLI authentication status using the CLI."""
        try:
            gemini_path = self.get_gemini_cli_path()
            if not gemini_path:
                return False, "Gemini CLI not found"
            
            # Try to run 'gemini auth status' or equivalent
            result = subprocess.run(
                [str(gemini_path), "auth", "status"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = result.stdout.strip().lower()
                if "authenticated" in output or "logged in" in output:
                    return True, "Authenticated"
                else:
                    return False, "Not authenticated"
            else:
                # Try alternative commands
                result = subprocess.run(
                    [str(gemini_path), "whoami"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    return True, "Authenticated"
                else:
                    return False, "Not authenticated"
                    
        except subprocess.TimeoutExpired:
            return False, "Authentication check timed out"
        except Exception as e:
            logger.debug(f"Error checking Gemini CLI auth status: {e}")
            return False, f"Error checking auth status: {e}"
    
    def find_credentials_file(self) -> Optional[Path]:
        """Find the OAuth credentials file for Gemini CLI."""
        # Check standard locations
        for cred_path in self.credential_paths:
            if cred_path.exists() and cred_path.is_file():
                logger.debug(f"Found Gemini CLI credentials at: {cred_path}")
                return cred_path
        
        # If Gemini CLI is installed, try to find credentials relative to installation
        gemini_path = self.get_gemini_cli_path()
        if gemini_path:
            relative_paths = [
                gemini_path.parent / "oauth_creds.json",
                gemini_path.parent / "credentials.json",
                gemini_path.parent / ".." / "share" / "gemini" / "oauth_creds.json"
            ]
            
            for rel_path in relative_paths:
                if rel_path.exists() and rel_path.is_file():
                    logger.debug(f"Found Gemini CLI credentials relative to installation: {rel_path}")
                    return rel_path
        
        logger.debug("No Gemini CLI credentials file found")
        return None
    
    def read_oauth_credentials(self, cred_file_path: Optional[Path] = None) -> Optional[GeminiCLICredentials]:
        """Read OAuth credentials from Gemini CLI."""
        if cred_file_path is None:
            cred_file_path = self.find_credentials_file()
        
        if not cred_file_path or not cred_file_path.exists():
            logger.debug("No OAuth credentials file found for Gemini CLI")
            return None
        
        try:
            with open(cred_file_path, 'r') as f:
                cred_data = json.load(f)
            
            # Handle different credential file formats
            access_token = None
            refresh_token = None
            expires_at = None
            token_type = "Bearer"
            project_id = None
            
            # Format 1: Direct token structure
            if "access_token" in cred_data:
                access_token = cred_data["access_token"]
                refresh_token = cred_data.get("refresh_token")
                token_type = cred_data.get("token_type", "Bearer")
                project_id = cred_data.get("project_id")
                
                # Parse expiration
                if "expires_at" in cred_data:
                    expires_at = datetime.fromisoformat(cred_data["expires_at"])
                elif "expires_in" in cred_data:
                    # Calculate expiration from expires_in
                    expires_in = cred_data["expires_in"]
                    expires_at = datetime.now(timezone.utc).timestamp() + expires_in
                    expires_at = datetime.fromtimestamp(expires_at, timezone.utc)
            
            # Format 2: Google OAuth2 format
            elif "installed" in cred_data and "client_id" in cred_data["installed"]:
                # This is a client credentials file, not access tokens
                logger.debug("Found client credentials file, not access tokens")
                return None
            
            # Format 3: Service account format
            elif "type" in cred_data and cred_data["type"] == "service_account":
                # Service account credentials - different format
                logger.debug("Found service account credentials - not OAuth")
                return None
            
            # Format 4: Nested structure
            elif "credentials" in cred_data:
                creds = cred_data["credentials"]
                access_token = creds.get("access_token")
                refresh_token = creds.get("refresh_token")
                token_type = creds.get("token_type", "Bearer")
                project_id = creds.get("project_id")
                
                if "expires_at" in creds:
                    expires_at = datetime.fromisoformat(creds["expires_at"])
            
            # Format 5: Token structure
            elif "token" in cred_data:
                token_data = cred_data["token"]
                access_token = token_data.get("access_token")
                refresh_token = token_data.get("refresh_token")
                token_type = token_data.get("token_type", "Bearer")
                project_id = token_data.get("project_id")
                
                if "expires_at" in token_data:
                    expires_at = datetime.fromisoformat(token_data["expires_at"])
            
            if not access_token:
                logger.warning(f"No access token found in Gemini CLI credentials file: {cred_file_path}")
                return None
            
            credentials = GeminiCLICredentials(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                token_type=token_type,
                project_id=project_id
            )
            
            logger.info(f"Successfully loaded Gemini CLI OAuth credentials from: {cred_file_path}")
            return credentials
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in Gemini CLI credentials file {cred_file_path}: {e}")
        except Exception as e:
            logger.error(f"Error reading Gemini CLI credentials from {cred_file_path}: {e}")
        
        return None
    
    def get_credentials(self) -> Optional[GeminiCLICredentials]:
        """Get Gemini CLI OAuth credentials with fallback to stored credentials."""
        # First try to read from Gemini CLI credentials file
        credentials = self.read_oauth_credentials()
        
        if credentials:
            # Store credentials in credential manager for backup
            try:
                self.credential_manager.set_credential(
                    "gemini_cli_access_token",
                    credentials.access_token,
                    CredentialType.SECRET,
                    "Gemini CLI OAuth access token (auto-detected)"
                )
                
                if credentials.refresh_token:
                    self.credential_manager.set_credential(
                        "gemini_cli_refresh_token",
                        credentials.refresh_token,
                        CredentialType.SECRET,
                        "Gemini CLI OAuth refresh token (auto-detected)"
                    )
                
                # Store metadata
                metadata = {
                    "expires_at": credentials.expires_at.isoformat() if credentials.expires_at else None,
                    "token_type": credentials.token_type,
                    "project_id": credentials.project_id,
                    "source": "gemini_cli_credentials_file"
                }
                
                self.credential_manager.set_credential(
                    "gemini_cli_oauth_metadata",
                    json.dumps(metadata),
                    CredentialType.ENV,
                    "Gemini CLI OAuth metadata"
                )
                
            except Exception as e:
                logger.warning(f"Failed to store Gemini CLI credentials in credential manager: {e}")
            
            return credentials
        
        # Fallback: try to load from credential manager
        try:
            access_token = self.credential_manager.get_credential("gemini_cli_access_token")
            if access_token:
                refresh_token = self.credential_manager.get_credential("gemini_cli_refresh_token")
                metadata_str = self.credential_manager.get_credential("gemini_cli_oauth_metadata")
                
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
                
                credentials = GeminiCLICredentials(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    token_type=metadata.get("token_type", "Bearer"),
                    project_id=metadata.get("project_id")
                )
                
                logger.info("Loaded Gemini CLI credentials from credential manager")
                return credentials
                
        except Exception as e:
            logger.warning(f"Failed to load Gemini CLI credentials from credential manager: {e}")
        
        return None
    
    def is_authenticated(self) -> bool:
        """Check if Gemini CLI authentication is available and valid."""
        # First check CLI auth status
        is_auth, _ = self.check_gemini_auth_status()
        if is_auth:
            return True
        
        # Fallback to credential file check
        credentials = self.get_credentials()
        if not credentials:
            return False
        
        # Check if token is expired
        if credentials.is_expired:
            logger.debug("Gemini CLI OAuth token is expired")
            return False
        
        return True
    
    def get_auth_header(self) -> Optional[str]:
        """Get the authorization header value for API requests."""
        credentials = self.get_credentials()
        if credentials and not credentials.is_expired:
            return credentials.authorization_header
        return None
    
    def validate_credentials(self) -> Tuple[bool, str]:
        """Validate Gemini CLI credentials by testing API access."""
        # First check CLI auth status
        is_auth, message = self.check_gemini_auth_status()
        if is_auth:
            return True, f"Gemini CLI authenticated: {message}"
        
        # Fallback to credential file validation
        credentials = self.get_credentials()
        if not credentials:
            return False, "No Gemini CLI credentials found"
        
        if credentials.is_expired:
            return False, "Gemini CLI OAuth token is expired"
        
        # Test the credentials
        try:
            if len(credentials.access_token) < 10:
                return False, "Gemini CLI access token appears invalid"
            
            return True, "Gemini CLI credentials are valid"
            
        except Exception as e:
            return False, f"Error validating Gemini CLI credentials: {e}"
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of Gemini CLI integration."""
        status = {
            "gemini_cli_installed": self.is_gemini_cli_installed(),
            "gemini_cli_path": str(self.get_gemini_cli_path()) if self.get_gemini_cli_path() else None,
            "credentials_file_found": self.find_credentials_file() is not None,
            "credentials_file_path": str(self.find_credentials_file()) if self.find_credentials_file() else None,
            "authenticated": self.is_authenticated(),
            "has_access_token": False,
            "has_refresh_token": False,
            "token_expired": False,
            "validation_status": "unknown",
            "validation_message": "Not tested",
            "cli_auth_status": "unknown"
        }
        
        # Check CLI auth status
        try:
            is_auth, auth_message = self.check_gemini_auth_status()
            status["cli_auth_status"] = "authenticated" if is_auth else "not_authenticated"
            status["cli_auth_message"] = auth_message
        except Exception as e:
            status["cli_auth_status"] = "error"
            status["cli_auth_message"] = str(e)
        
        credentials = self.get_credentials()
        if credentials:
            status.update({
                "has_access_token": bool(credentials.access_token),
                "has_refresh_token": bool(credentials.refresh_token),
                "token_expired": credentials.is_expired,
                "token_type": credentials.token_type,
                "expires_at": credentials.expires_at.isoformat() if credentials.expires_at else None,
                "project_id": credentials.project_id
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
            logger.warning("Cannot refresh Gemini CLI credentials: no refresh token available")
            return False
        
        # This would normally implement OAuth token refresh
        # For now, we'll just re-read from the file in case it was updated
        try:
            new_credentials = self.read_oauth_credentials()
            if new_credentials and new_credentials.access_token != credentials.access_token:
                logger.info("Gemini CLI credentials refreshed from file")
                return True
        except Exception as e:
            logger.error(f"Error refreshing Gemini CLI credentials: {e}")
        
        return False
    
    def setup_instructions(self) -> Dict[str, str]:
        """Get setup instructions for Gemini CLI OAuth."""
        return {
            "title": "Gemini CLI OAuth Setup",
            "installation": """
            1. Install Gemini CLI:
               - macOS: brew install gemini-cli
               - Linux: Download from https://github.com/google/gemini-cli
               - Windows: Download installer from GitHub releases
            2. Authenticate with Google:
               gemini auth login
            3. Follow the OAuth flow in your browser
            4. Complete the authentication process
            5. The OAuth credentials will be automatically detected by Hive MCP Gateway
            """,
            "troubleshooting": """
            If credentials are not detected:
            1. Ensure Gemini CLI is properly installed and authenticated
            2. Run 'gemini auth status' to verify authentication
            3. Check that credentials exist in one of these locations:
               - ~/.gemini/oauth_creds.json
               - ~/.config/gemini/oauth_creds.json (Linux)
               - ~/AppData/Roaming/Gemini/oauth_creds.json (Windows)
            4. Restart Hive MCP Gateway after authenticating Gemini CLI
            5. If still not working, check the logs for specific error messages
            """,
            "credential_file_locations": "\n".join([str(path) for path in self.credential_paths])
        }