"""OAuth manager service for coordinating OAuth flows and token management."""

import asyncio
import logging
import secrets
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
import base64

from oauthlib.oauth2 import WebApplicationClient
from requests_oauthlib import OAuth2Session
import requests

from .credential_manager import CredentialManager, CredentialType

logger = logging.getLogger(__name__)


class OAuthFlowState(Enum):
    """OAuth flow states."""
    INITIATED = "initiated"
    AUTHORIZATION_PENDING = "authorization_pending"
    TOKEN_RECEIVED = "token_received"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class OAuthConfig:
    """OAuth configuration for a service."""
    client_id: str
    client_secret: Optional[str]
    authorization_url: str
    token_url: str
    scope: List[str]
    redirect_uri: str
    service_name: str
    use_pkce: bool = True
    extra_params: Optional[Dict[str, Any]] = None


@dataclass
class OAuthFlow:
    """Represents an OAuth flow session."""
    flow_id: str
    service_name: str
    config: OAuthConfig
    state: OAuthFlowState
    created_at: datetime
    expires_at: datetime
    state_parameter: str
    code_verifier: Optional[str]  # For PKCE
    code_challenge: Optional[str]  # For PKCE
    authorization_url: Optional[str]
    access_token: Optional[str]
    refresh_token: Optional[str]
    token_expires_at: Optional[datetime]
    error_message: Optional[str]
    metadata: Dict[str, Any]


@dataclass
class TokenInfo:
    """Token information."""
    access_token: str
    refresh_token: Optional[str]
    expires_at: Optional[datetime]
    scope: List[str]
    token_type: str = "Bearer"


@dataclass
class OAuthResult:
    """Result of an OAuth operation."""
    success: bool
    token_data: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    error: Optional[str] = None


class OAuthManager:
    """Manages OAuth flows and token lifecycle."""
    
    def __init__(self, credential_manager: Optional[CredentialManager] = None):
        """Initialize the OAuth manager."""
        self.credential_manager = credential_manager or CredentialManager()
        
        # Active flows
        self.active_flows: Dict[str, OAuthFlow] = {}
        
        # OAuth configurations for known services
        self.oauth_configs: Dict[str, OAuthConfig] = {}
        
        # Callbacks for flow events
        self.flow_callbacks: List[Callable[[OAuthFlow], None]] = []
        
        # Default flow expiry (15 minutes)
        self.flow_expiry_minutes = 15
        
        # Load built-in OAuth configs
        self._load_builtin_configs()
    
    def _load_builtin_configs(self):
        """Load built-in OAuth configurations for common services."""
        # Google OAuth
        self.oauth_configs["google"] = OAuthConfig(
            client_id="",  # To be configured by user
            client_secret="",  # To be configured by user
            authorization_url="https://accounts.google.com/o/oauth2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scope=["openid", "email", "profile"],
            redirect_uri="http://localhost:8001/oauth/callback",
            service_name="Google",
            use_pkce=True
        )
        
        # GitHub OAuth
        self.oauth_configs["github"] = OAuthConfig(
            client_id="",  # To be configured by user
            client_secret="",  # To be configured by user
            authorization_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scope=["read:user", "user:email"],
            redirect_uri="http://localhost:8001/oauth/callback",
            service_name="GitHub",
            use_pkce=False  # GitHub doesn't support PKCE
        )
        
        # Microsoft OAuth
        self.oauth_configs["microsoft"] = OAuthConfig(
            client_id="",  # To be configured by user
            client_secret="",  # To be configured by user
            authorization_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            scope=["openid", "profile", "email"],
            redirect_uri="http://localhost:8001/oauth/callback",
            service_name="Microsoft",
            use_pkce=True
        )
        
        # Generic OAuth template
        self.oauth_configs["generic"] = OAuthConfig(
            client_id="",
            client_secret="",
            authorization_url="",
            token_url="",
            scope=[],
            redirect_uri="http://localhost:8001/oauth/callback",
            service_name="Generic OAuth Service",
            use_pkce=True
        )
        
        # Claude Code OAuth (Anthropic)
        self.oauth_configs["claude_code"] = OAuthConfig(
            client_id="",  # To be configured by user
            client_secret="",  # To be configured by user
            authorization_url="https://claude.ai/oauth/authorize",
            token_url="https://api.anthropic.com/oauth/token",
            scope=["claude:read", "claude:write"],
            redirect_uri="http://localhost:8001/oauth/callback",
            service_name="Claude Code",
            use_pkce=True,
            extra_params={
                "response_type": "code",
                "grant_type": "authorization_code"
            }
        )
        
        # Gemini CLI OAuth (Google AI Studio)
        self.oauth_configs["gemini_cli"] = OAuthConfig(
            client_id="",  # To be configured by user
            client_secret="",  # To be configured by user
            authorization_url="https://accounts.google.com/o/oauth2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scope=["https://www.googleapis.com/auth/generative-language"],
            redirect_uri="http://localhost:8001/oauth/callback",
            service_name="Gemini CLI",
            use_pkce=True,
            extra_params={
                "access_type": "offline",  # Request refresh token
                "prompt": "consent"  # Force consent screen
            }
        )
    
    def add_flow_callback(self, callback: Callable[[OAuthFlow], None]):
        """Add a callback for flow state changes."""
        self.flow_callbacks.append(callback)
    
    def configure_service(self, service_name: str, client_id: str, 
                         client_secret: Optional[str] = None,
                         custom_config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Configure OAuth settings for a service.
        
        Args:
            service_name: Name of the service
            client_id: OAuth client ID
            client_secret: OAuth client secret (optional for PKCE)
            custom_config: Custom configuration overrides
            
        Returns:
            True if configuration was successful
        """
        try:
            if service_name not in self.oauth_configs:
                if not custom_config:
                    raise ValueError(f"Unknown service '{service_name}' and no custom config provided")
                
                # Create new config from template
                config = OAuthConfig(
                    client_id=client_id,
                    client_secret=client_secret,
                    authorization_url=custom_config.get("authorization_url", ""),
                    token_url=custom_config.get("token_url", ""),
                    scope=custom_config.get("scope", []),
                    redirect_uri=custom_config.get("redirect_uri", "http://localhost:8001/oauth/callback"),
                    service_name=custom_config.get("display_name", service_name),
                    use_pkce=custom_config.get("use_pkce", True),
                    extra_params=custom_config.get("extra_params")
                )
                self.oauth_configs[service_name] = config
            else:
                # Update existing config
                config = self.oauth_configs[service_name]
                config.client_id = client_id
                config.client_secret = client_secret
                
                if custom_config:
                    for key, value in custom_config.items():
                        if hasattr(config, key):
                            setattr(config, key, value)
            
            # Store credentials securely
            self.credential_manager.set_credential(
                f"oauth_{service_name}_client_id",
                client_id,
                CredentialType.ENVIRONMENT,
                f"OAuth client ID for {service_name}"
            )
            
            if client_secret:
                self.credential_manager.set_credential(
                    f"oauth_{service_name}_client_secret",
                    client_secret,
                    CredentialType.SECRET,
                    f"OAuth client secret for {service_name}"
                )
            
            logger.info(f"Configured OAuth for service: {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure OAuth for {service_name}: {e}")
            return False
    
    def initiate_flow(self, service_name: str, custom_scope: Optional[List[str]] = None) -> OAuthFlow:
        """
        Initiate an OAuth flow for a service.
        
        Args:
            service_name: Name of the service
            custom_scope: Custom scope override
            
        Returns:
            OAuthFlow object with authorization URL
        """
        if service_name not in self.oauth_configs:
            raise ValueError(f"OAuth not configured for service: {service_name}")
        
        config = self.oauth_configs[service_name]
        
        # Validate configuration
        if not config.client_id:
            raise ValueError(f"Client ID not configured for {service_name}")
        
        # Generate flow ID and state
        flow_id = secrets.token_urlsafe(16)
        state_parameter = secrets.token_urlsafe(32)
        
        # PKCE parameters
        code_verifier = None
        code_challenge = None
        
        if config.use_pkce:
            code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
            code_challenge = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode('utf-8')).digest()
            ).decode('utf-8').rstrip('=')
        
        # Create OAuth session
        scope = custom_scope or config.scope
        client = WebApplicationClient(config.client_id)
        
        # Build authorization URL
        oauth_session = OAuth2Session(
            client=client,
            redirect_uri=config.redirect_uri,
            scope=scope,
            state=state_parameter
        )
        
        auth_params = {}
        if config.use_pkce:
            auth_params.update({
                'code_challenge': code_challenge,
                'code_challenge_method': 'S256'
            })
        
        if config.extra_params:
            auth_params.update(config.extra_params)
        
        authorization_url, _ = oauth_session.authorization_url(
            config.authorization_url,
            **auth_params
        )
        
        # Create flow object
        flow = OAuthFlow(
            flow_id=flow_id,
            service_name=service_name,
            config=config,
            state=OAuthFlowState.INITIATED,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=self.flow_expiry_minutes),
            state_parameter=state_parameter,
            code_verifier=code_verifier,
            code_challenge=code_challenge,
            authorization_url=authorization_url,
            access_token=None,
            refresh_token=None,
            token_expires_at=None,
            error_message=None,
            metadata={"scope": scope}
        )
        
        # Store flow
        self.active_flows[flow_id] = flow
        
        # Update state
        flow.state = OAuthFlowState.AUTHORIZATION_PENDING
        self._notify_flow_callbacks(flow)
        
        logger.info(f"Initiated OAuth flow for {service_name}, flow_id: {flow_id}")
        return flow
    
    def handle_callback(self, authorization_response_url: str) -> Optional[OAuthFlow]:
        """
        Handle OAuth callback with authorization code.
        
        Args:
            authorization_response_url: Full callback URL with parameters
            
        Returns:
            OAuthFlow object if successful, None if failed
        """
        try:
            # Parse callback URL
            parsed_url = urllib.parse.urlparse(authorization_response_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            # Extract state and code
            state = query_params.get('state', [None])[0]
            code = query_params.get('code', [None])[0]
            error = query_params.get('error', [None])[0]
            
            if error:
                logger.error(f"OAuth callback error: {error}")
                return None
            
            if not state or not code:
                logger.error("Missing state or code in OAuth callback")
                return None
            
            # Find matching flow
            flow = None
            for f in self.active_flows.values():
                if f.state_parameter == state:
                    flow = f
                    break
            
            if not flow:
                logger.error(f"No matching OAuth flow found for state: {state}")
                return None
            
            # Check if flow is expired
            if datetime.now() > flow.expires_at:
                flow.state = OAuthFlowState.EXPIRED
                flow.error_message = "OAuth flow expired"
                self._notify_flow_callbacks(flow)
                return flow
            
            # Exchange code for token
            token_info = self._exchange_code_for_token(flow, code)
            
            if token_info:
                # Update flow with token info
                flow.access_token = token_info.access_token
                flow.refresh_token = token_info.refresh_token
                flow.token_expires_at = token_info.expires_at
                flow.state = OAuthFlowState.TOKEN_RECEIVED
                
                # Store tokens securely
                self._store_tokens(flow.service_name, token_info)
                
                flow.state = OAuthFlowState.COMPLETED
                logger.info(f"OAuth flow completed for {flow.service_name}")
            else:
                flow.state = OAuthFlowState.FAILED
                flow.error_message = "Failed to exchange code for token"
            
            self._notify_flow_callbacks(flow)
            return flow
            
        except Exception as e:
            logger.error(f"OAuth callback handling failed: {e}")
            return None
    
    def _exchange_code_for_token(self, flow: OAuthFlow, code: str) -> Optional[TokenInfo]:
        """Exchange authorization code for access token."""
        try:
            config = flow.config
            
            # Prepare token request
            token_data = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': config.redirect_uri,
                'client_id': config.client_id
            }
            
            # Add client secret if available
            if config.client_secret:
                token_data['client_secret'] = config.client_secret
            
            # Add PKCE code verifier
            if config.use_pkce and flow.code_verifier:
                token_data['code_verifier'] = flow.code_verifier
            
            # Make token request
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.post(
                config.token_url,
                data=token_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                return None
            
            token_response = response.json()
            
            # Extract token information
            access_token = token_response.get('access_token')
            if not access_token:
                logger.error("No access token in response")
                return None
            
            refresh_token = token_response.get('refresh_token')
            expires_in = token_response.get('expires_in')
            scope = token_response.get('scope', '').split() if token_response.get('scope') else flow.metadata.get('scope', [])
            token_type = token_response.get('token_type', 'Bearer')
            
            # Calculate expiry
            expires_at = None
            if expires_in:
                expires_at = datetime.now() + timedelta(seconds=int(expires_in))
            
            return TokenInfo(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=scope,
                token_type=token_type
            )
            
        except Exception as e:
            logger.error(f"Token exchange error: {e}")
            return None
    
    def _store_tokens(self, service_name: str, token_info: TokenInfo):
        """Store tokens securely."""
        try:
            # Store access token
            self.credential_manager.set_credential(
                f"oauth_{service_name}_access_token",
                token_info.access_token,
                CredentialType.SECRET,
                f"OAuth access token for {service_name}"
            )
            
            # Store refresh token if available
            if token_info.refresh_token:
                self.credential_manager.set_credential(
                    f"oauth_{service_name}_refresh_token",
                    token_info.refresh_token,
                    CredentialType.SECRET,
                    f"OAuth refresh token for {service_name}"
                )
            
            # Store expiry and metadata
            token_metadata = {
                "expires_at": token_info.expires_at.isoformat() if token_info.expires_at else None,
                "scope": token_info.scope,
                "token_type": token_info.token_type
            }
            
            self.credential_manager.set_credential(
                f"oauth_{service_name}_metadata",
                json.dumps(token_metadata),
                CredentialType.ENVIRONMENT,
                f"OAuth token metadata for {service_name}"
            )
            
        except Exception as e:
            logger.error(f"Failed to store tokens for {service_name}: {e}")
    
    def get_access_token(self, service_name: str) -> Optional[str]:
        """Get current access token for a service."""
        try:
            entry = self.credential_manager.get_credential(f"oauth_{service_name}_access_token")
            return entry.value if entry else None
        except Exception as e:
            logger.error(f"Failed to get access token for {service_name}: {e}")
            return None
    
    def refresh_token(self, service_name: str) -> OAuthResult:
        """Refresh access token using refresh token."""
        try:
            # Get refresh token
            refresh_entry = self.credential_manager.get_credential(f"oauth_{service_name}_refresh_token")
            if not refresh_entry:
                logger.error(f"No refresh token available for {service_name}")
                return OAuthResult(
                    success=False,
                    error="No refresh token available"
                )
            
            config = self.oauth_configs.get(service_name)
            if not config:
                logger.error(f"No OAuth config for {service_name}")
                return OAuthResult(
                    success=False,
                    error="No OAuth configuration found"
                )
            
            # Prepare refresh request
            token_data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_entry.value,
                'client_id': config.client_id
            }
            
            if config.client_secret:
                token_data['client_secret'] = config.client_secret
            
            # Make refresh request
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.post(
                config.token_url,
                data=token_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"Token refresh failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return OAuthResult(
                    success=False,
                    error=error_msg
                )
            
            token_response = response.json()
            
            # Extract new token information
            access_token = token_response.get('access_token')
            if not access_token:
                logger.error("No access token in refresh response")
                return OAuthResult(
                    success=False,
                    error="No access token in refresh response"
                )
            
            new_refresh_token = token_response.get('refresh_token')
            expires_in = token_response.get('expires_in')
            
            # Calculate expiry
            expires_at = None
            if expires_in:
                expires_at = datetime.now() + timedelta(seconds=int(expires_in))
            
            # Create new token info
            token_info = TokenInfo(
                access_token=access_token,
                refresh_token=new_refresh_token or refresh_entry.value,
                expires_at=expires_at,
                scope=[],  # Will be updated from metadata
                token_type=token_response.get('token_type', 'Bearer')
            )
            
            # Store updated tokens
            self._store_tokens(service_name, token_info)
            
            logger.info(f"Successfully refreshed token for {service_name}")
            
            # Prepare token data for response
            response_token_data = {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "token_type": token_info.token_type
            }
            
            return OAuthResult(
                success=True,
                token_data=response_token_data,
                expires_at=expires_at
            )
            
        except Exception as e:
            logger.error(f"Token refresh error for {service_name}: {e}")
            return OAuthResult(
                success=False,
                error=str(e)
            )
    
    def get_valid_token(self, service_name: str) -> Optional[str]:
        """Get a valid access token, refreshing if necessary."""
        try:
            # Check current token status
            status = self.get_service_token_status(service_name)
            
            if status["status"] == "valid":
                return self.get_access_token(service_name)
            elif status["status"] in ["expired", "expiring_soon"] and status["has_refresh_token"]:
                # Try to refresh
                refresh_result = self.refresh_token(service_name)
                if refresh_result.success:
                    return refresh_result.token_data["access_token"]
                else:
                    logger.warning(f"Failed to refresh token for {service_name}: {refresh_result.error}")
                    return None
            else:
                logger.warning(f"No valid token available for {service_name}, status: {status['status']}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting valid token for {service_name}: {e}")
            return None
    
    def has_valid_token(self, service_name: str) -> bool:
        """Check if service has a valid token (including refreshable tokens)."""
        try:
            status = self.get_service_token_status(service_name)
            return status["status"] in ["valid", "expiring_soon"] or (
                status["status"] == "expired" and status["has_refresh_token"]
            )
        except Exception as e:
            logger.error(f"Error checking token validity for {service_name}: {e}")
            return False
    
    def configure_claude_code(self, client_id: str, client_secret: str) -> bool:
        """Configure OAuth for Claude Code."""
        return self.configure_service("claude_code", client_id, client_secret)
    
    def configure_gemini_cli(self, client_id: str, client_secret: str) -> bool:
        """Configure OAuth for Gemini CLI."""
        return self.configure_service("gemini_cli", client_id, client_secret)
    
    def initiate_claude_code_flow(self) -> Optional[OAuthFlow]:
        """Initiate OAuth flow for Claude Code."""
        return self.initiate_oauth_flow("claude_code")
    
    def initiate_gemini_cli_flow(self) -> Optional[OAuthFlow]:
        """Initiate OAuth flow for Gemini CLI."""
        return self.initiate_oauth_flow("gemini_cli")
    
    def revoke_token(self, service_name: str) -> bool:
        """Revoke tokens for a service."""
        try:
            # Delete stored tokens
            keys_to_delete = [
                f"oauth_{service_name}_access_token",
                f"oauth_{service_name}_refresh_token",
                f"oauth_{service_name}_metadata"
            ]
            
            for key in keys_to_delete:
                self.credential_manager.delete_credential(key)
            
            logger.info(f"Revoked tokens for {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke tokens for {service_name}: {e}")
            return False
    
    def get_flow_status(self, flow_id: str) -> Optional[OAuthFlow]:
        """Get status of an OAuth flow."""
        return self.active_flows.get(flow_id)
    
    def cleanup_expired_flows(self):
        """Clean up expired OAuth flows."""
        current_time = datetime.now()
        expired_flows = [
            flow_id for flow_id, flow in self.active_flows.items()
            if current_time > flow.expires_at
        ]
        
        for flow_id in expired_flows:
            flow = self.active_flows[flow_id]
            flow.state = OAuthFlowState.EXPIRED
            self._notify_flow_callbacks(flow)
            del self.active_flows[flow_id]
        
        if expired_flows:
            logger.info(f"Cleaned up {len(expired_flows)} expired OAuth flows")
    
    def get_service_token_status(self, service_name: str) -> Dict[str, Any]:
        """Get token status for a service."""
        try:
            # Check if we have tokens
            access_token = self.get_access_token(service_name)
            has_access_token = access_token is not None
            
            refresh_entry = self.credential_manager.get_credential(f"oauth_{service_name}_refresh_token")
            has_refresh_token = refresh_entry is not None
            
            # Get metadata
            metadata_entry = self.credential_manager.get_credential(f"oauth_{service_name}_metadata")
            expires_at = None
            scope = []
            
            if metadata_entry:
                try:
                    metadata = json.loads(metadata_entry.value)
                    if metadata.get('expires_at'):
                        expires_at = datetime.fromisoformat(metadata['expires_at'])
                    scope = metadata.get('scope', [])
                except json.JSONDecodeError:
                    pass
            
            # Determine status
            if not has_access_token:
                status = "no_token"
            elif expires_at and datetime.now() > expires_at:
                status = "expired"
            elif expires_at and datetime.now() > (expires_at - timedelta(hours=1)):
                status = "expiring_soon"
            else:
                status = "valid"
            
            return {
                "service_name": service_name,
                "status": status,
                "has_access_token": has_access_token,
                "has_refresh_token": has_refresh_token,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "scope": scope
            }
            
        except Exception as e:
            logger.error(f"Failed to get token status for {service_name}: {e}")
            return {
                "service_name": service_name,
                "status": "error",
                "error": str(e)
            }
    
    def _notify_flow_callbacks(self, flow: OAuthFlow):
        """Notify callbacks about flow state changes."""
        for callback in self.flow_callbacks:
            try:
                callback(flow)
            except Exception as e:
                logger.error(f"OAuth flow callback failed: {e}")
    
    def get_configured_services(self) -> List[str]:
        """Get list of configured OAuth services."""
        configured = []
        for service_name, config in self.oauth_configs.items():
            if config.client_id:
                configured.append(service_name)
        return configured
    
    def get_available_services(self) -> List[str]:
        """Get list of all available OAuth services."""
        return list(self.oauth_configs.keys())
    
    def get_flow(self, flow_id: str) -> Optional[OAuthFlow]:
        """Get an OAuth flow by ID."""
        return self.active_flows.get(flow_id)
    
    def complete_flow(self, flow: OAuthFlow, callback_url: str) -> OAuthResult:
        """Complete an OAuth flow using the callback URL."""
        try:
            completed_flow = self.handle_callback(callback_url)
            
            if not completed_flow:
                return OAuthResult(
                    success=False,
                    error="Failed to handle OAuth callback"
                )
            
            if completed_flow.state == OAuthFlowState.COMPLETED:
                # Prepare token data
                token_data = {
                    "access_token": completed_flow.access_token,
                    "refresh_token": completed_flow.refresh_token,
                    "token_type": "Bearer"
                }
                
                return OAuthResult(
                    success=True,
                    token_data=token_data,
                    expires_at=completed_flow.token_expires_at
                )
            else:
                return OAuthResult(
                    success=False,
                    error=completed_flow.error_message or "OAuth flow failed"
                )
                
        except Exception as e:
            logger.error(f"Complete flow error: {e}")
            return OAuthResult(
                success=False,
                error=str(e)
            )