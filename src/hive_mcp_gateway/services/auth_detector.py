"""Authentication detector service for monitoring connection failures and OAuth requirements."""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)


class AuthRequirement(Enum):
    """Types of authentication requirements."""
    NONE = "none"
    API_KEY = "api_key"
    OAUTH = "oauth"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    UNKNOWN = "unknown"


class AuthStatus(Enum):
    """Authentication status."""
    AUTHENTICATED = "authenticated"
    EXPIRED = "expired"
    INVALID = "invalid"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass
class AuthEvent:
    """Represents an authentication-related event."""
    timestamp: datetime
    server_name: str
    event_type: str  # "failure", "success", "expired", "required"
    auth_requirement: AuthRequirement
    error_message: Optional[str]
    oauth_url: Optional[str] = None
    suggested_action: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ServerAuthInfo:
    """Authentication information for a server."""
    server_name: str
    auth_requirement: AuthRequirement
    auth_status: AuthStatus
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    failure_count: int
    oauth_url: Optional[str]
    token_expires_at: Optional[datetime]
    metadata: Dict[str, Any]


class AuthDetector:
    """Detects authentication requirements and monitors auth status."""
    
    # OAuth patterns in error messages
    OAUTH_INDICATORS = [
        r"authorization_required",
        r"oauth_token_expired",
        r"authentication_url",
        r"login_required",
        r"unauthorized.*oauth",
        r"token_invalid",
        r"access_denied",
        r"invalid_grant",
        r"expired_token",
        r"refresh_required"
    ]
    
    # API key patterns
    API_KEY_INDICATORS = [
        r"api_key.*required",
        r"invalid.*api.*key",
        r"missing.*api.*key",
        r"api.*key.*expired",
        r"unauthorized.*key"
    ]
    
    # Bearer token patterns
    BEARER_TOKEN_INDICATORS = [
        r"bearer.*token.*required",
        r"invalid.*bearer",
        r"authorization.*header.*required",
        r"token.*expired"
    ]
    
    # OAuth URL extraction patterns
    OAUTH_URL_PATTERNS = [
        r"authorization_url[\"']?\s*:\s*[\"']([^\"']+)[\"']",
        r"oauth_url[\"']?\s*:\s*[\"']([^\"']+)[\"']",
        r"auth_url[\"']?\s*:\s*[\"']([^\"']+)[\"']",
        r"login_url[\"']?\s*:\s*[\"']([^\"']+)[\"']"
    ]
    
    def __init__(self):
        """Initialize the auth detector."""
        self.server_auth_info: Dict[str, ServerAuthInfo] = {}
        self.auth_events: List[AuthEvent] = []
        self.event_callbacks: List[Callable[[AuthEvent], None]] = []
        
        # Configuration
        self.max_events = 1000
        self.failure_threshold = 3
        self.token_expiry_warning_hours = 1
    
    def add_event_callback(self, callback: Callable[[AuthEvent], None]):
        """Add a callback for authentication events."""
        self.event_callbacks.append(callback)
    
    def analyze_error(self, server_name: str, error_message: str, 
                     response_data: Optional[Dict[str, Any]] = None) -> AuthEvent:
        """
        Analyze an error message to detect authentication requirements.
        
        Args:
            server_name: Name of the MCP server
            error_message: Error message from the server
            response_data: Optional response data containing additional info
            
        Returns:
            AuthEvent with detected information
        """
        timestamp = datetime.now()
        auth_requirement = self._detect_auth_type(error_message, response_data)
        oauth_url = self._extract_oauth_url(error_message, response_data)
        suggested_action = self._get_suggested_action(auth_requirement, oauth_url)
        
        event = AuthEvent(
            timestamp=timestamp,
            server_name=server_name,
            event_type="failure",
            auth_requirement=auth_requirement,
            error_message=error_message,
            oauth_url=oauth_url,
            suggested_action=suggested_action,
            metadata=response_data
        )
        
        # Update server auth info
        self._update_server_auth_info(server_name, event)
        
        # Store event
        self._add_event(event)
        
        # Notify callbacks
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Auth event callback failed: {e}")
        
        return event
    
    def _detect_auth_type(self, error_message: str, 
                         response_data: Optional[Dict[str, Any]]) -> AuthRequirement:
        """Detect the type of authentication required."""
        error_lower = error_message.lower()
        
        # Check response data first
        if response_data:
            # Look for specific auth type indicators
            if "oauth" in str(response_data).lower():
                return AuthRequirement.OAUTH
            if "api_key" in str(response_data).lower():
                return AuthRequirement.API_KEY
            if "bearer" in str(response_data).lower():
                return AuthRequirement.BEARER_TOKEN
        
        # Check OAuth patterns
        for pattern in self.OAUTH_INDICATORS:
            if re.search(pattern, error_lower):
                return AuthRequirement.OAUTH
        
        # Check API key patterns
        for pattern in self.API_KEY_INDICATORS:
            if re.search(pattern, error_lower):
                return AuthRequirement.API_KEY
        
        # Check Bearer token patterns
        for pattern in self.BEARER_TOKEN_INDICATORS:
            if re.search(pattern, error_lower):
                return AuthRequirement.BEARER_TOKEN
        
        # Generic auth indicators
        if any(word in error_lower for word in ["unauthorized", "403", "401"]):
            return AuthRequirement.UNKNOWN
        
        return AuthRequirement.NONE
    
    def _extract_oauth_url(self, error_message: str, 
                          response_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Extract OAuth URL from error message or response data."""
        # Check response data first
        if response_data:
            # Common OAuth URL fields
            oauth_fields = [
                "authorization_url", "oauth_url", "auth_url", 
                "login_url", "authUrl", "loginUrl"
            ]
            
            for field in oauth_fields:
                if field in response_data:
                    url = response_data[field]
                    if isinstance(url, str) and url.startswith(("http://", "https://")):
                        return url
        
        # Extract from error message
        combined_text = error_message
        if response_data:
            combined_text += " " + json.dumps(response_data)
        
        for pattern in self.OAUTH_URL_PATTERNS:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                url = match.group(1)
                if url.startswith(("http://", "https://")):
                    return url
        
        return None
    
    def _get_suggested_action(self, auth_requirement: AuthRequirement, 
                            oauth_url: Optional[str]) -> str:
        """Get suggested action based on auth requirement."""
        if auth_requirement == AuthRequirement.OAUTH:
            if oauth_url:
                return f"Complete OAuth authentication at: {oauth_url}"
            else:
                return "OAuth authentication required - check server documentation"
        elif auth_requirement == AuthRequirement.API_KEY:
            return "Configure API key in credentials manager"
        elif auth_requirement == AuthRequirement.BEARER_TOKEN:
            return "Configure bearer token in credentials manager"
        elif auth_requirement == AuthRequirement.BASIC_AUTH:
            return "Configure username/password in credentials manager"
        elif auth_requirement == AuthRequirement.UNKNOWN:
            return "Authentication required - check server documentation"
        else:
            return "No authentication action needed"
    
    def _update_server_auth_info(self, server_name: str, event: AuthEvent):
        """Update server authentication information."""
        if server_name not in self.server_auth_info:
            self.server_auth_info[server_name] = ServerAuthInfo(
                server_name=server_name,
                auth_requirement=AuthRequirement.NONE,
                auth_status=AuthStatus.UNKNOWN,
                last_success=None,
                last_failure=None,
                failure_count=0,
                oauth_url=None,
                token_expires_at=None,
                metadata={}
            )
        
        server_info = self.server_auth_info[server_name]
        
        if event.event_type == "failure":
            server_info.last_failure = event.timestamp
            server_info.failure_count += 1
            server_info.auth_requirement = event.auth_requirement
            server_info.auth_status = AuthStatus.INVALID
            
            if event.oauth_url:
                server_info.oauth_url = event.oauth_url
                
        elif event.event_type == "success":
            server_info.last_success = event.timestamp
            server_info.failure_count = 0
            server_info.auth_status = AuthStatus.AUTHENTICATED
            
        elif event.event_type == "expired":
            server_info.auth_status = AuthStatus.EXPIRED
            server_info.token_expires_at = None
    
    def _add_event(self, event: AuthEvent):
        """Add an event to the history."""
        self.auth_events.append(event)
        
        # Trim old events
        if len(self.auth_events) > self.max_events:
            self.auth_events = self.auth_events[-self.max_events:]
    
    def record_success(self, server_name: str, metadata: Optional[Dict[str, Any]] = None):
        """Record a successful authentication."""
        event = AuthEvent(
            timestamp=datetime.now(),
            server_name=server_name,
            event_type="success",
            auth_requirement=AuthRequirement.NONE,
            error_message=None,
            metadata=metadata
        )
        
        self._update_server_auth_info(server_name, event)
        self._add_event(event)
        
        # Notify callbacks
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Auth event callback failed: {e}")
    
    def record_token_expiry(self, server_name: str, expires_at: datetime):
        """Record token expiry information."""
        if server_name in self.server_auth_info:
            self.server_auth_info[server_name].token_expires_at = expires_at
    
    def get_server_auth_info(self, server_name: str) -> Optional[ServerAuthInfo]:
        """Get authentication info for a server."""
        return self.server_auth_info.get(server_name)
    
    def get_servers_requiring_auth(self) -> List[ServerAuthInfo]:
        """Get servers that require authentication."""
        return [
            info for info in self.server_auth_info.values()
            if info.auth_requirement != AuthRequirement.NONE
        ]
    
    def get_servers_with_auth_issues(self) -> List[ServerAuthInfo]:
        """Get servers with authentication issues."""
        return [
            info for info in self.server_auth_info.values()
            if (info.auth_status in [AuthStatus.EXPIRED, AuthStatus.INVALID, AuthStatus.MISSING] or
                info.failure_count >= self.failure_threshold)
        ]
    
    def get_expiring_tokens(self, hours_ahead: int = 1) -> List[ServerAuthInfo]:
        """Get servers with tokens expiring soon."""
        cutoff_time = datetime.now() + timedelta(hours=hours_ahead)
        
        return [
            info for info in self.server_auth_info.values()
            if (info.token_expires_at and 
                info.token_expires_at <= cutoff_time)
        ]
    
    def get_recent_events(self, server_name: Optional[str] = None, 
                         hours: int = 24) -> List[AuthEvent]:
        """Get recent authentication events."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        events = [
            event for event in self.auth_events
            if event.timestamp >= cutoff_time
        ]
        
        if server_name:
            events = [
                event for event in events
                if event.server_name == server_name
            ]
        
        return sorted(events, key=lambda x: x.timestamp, reverse=True)
    
    def get_oauth_urls(self) -> Dict[str, str]:
        """Get OAuth URLs for all servers that have them."""
        oauth_urls = {}
        
        for server_name, info in self.server_auth_info.items():
            if info.oauth_url:
                oauth_urls[server_name] = info.oauth_url
        
        return oauth_urls
    
    def clear_server_failures(self, server_name: str):
        """Clear failure count for a server (after successful auth)."""
        if server_name in self.server_auth_info:
            self.server_auth_info[server_name].failure_count = 0
            self.server_auth_info[server_name].auth_status = AuthStatus.AUTHENTICATED
    
    def get_auth_summary(self) -> Dict[str, Any]:
        """Get a summary of authentication status across all servers."""
        total_servers = len(self.server_auth_info)
        requiring_auth = len(self.get_servers_requiring_auth())
        with_issues = len(self.get_servers_with_auth_issues())
        expiring_soon = len(self.get_expiring_tokens())
        
        return {
            "total_servers": total_servers,
            "requiring_auth": requiring_auth,
            "with_issues": with_issues,
            "expiring_soon": expiring_soon,
            "recent_events": len(self.get_recent_events(hours=1)),
            "servers_by_auth_type": self._get_servers_by_auth_type(),
            "servers_by_status": self._get_servers_by_status()
        }
    
    def _get_servers_by_auth_type(self) -> Dict[str, int]:
        """Get count of servers by authentication type."""
        counts = {}
        for info in self.server_auth_info.values():
            auth_type = info.auth_requirement.value
            counts[auth_type] = counts.get(auth_type, 0) + 1
        return counts
    
    def _get_servers_by_status(self) -> Dict[str, int]:
        """Get count of servers by authentication status."""
        counts = {}
        for info in self.server_auth_info.values():
            status = info.auth_status.value
            counts[status] = counts.get(status, 0) + 1
        return counts
    
    def is_oauth_required(self, server_name: str) -> bool:
        """Check if OAuth is required for a server."""
        info = self.get_server_auth_info(server_name)
        return info and info.auth_requirement == AuthRequirement.OAUTH
    
    def get_oauth_url_for_server(self, server_name: str) -> Optional[str]:
        """Get OAuth URL for a specific server."""
        info = self.get_server_auth_info(server_name)
        return info.oauth_url if info else None
    
    def monitor_server_health(self) -> Dict[str, Any]:
        """Monitor overall server authentication health."""
        issues = []
        warnings = []
        
        # Check for servers with repeated failures
        for info in self.server_auth_info.values():
            if info.failure_count >= self.failure_threshold:
                issues.append(f"{info.server_name} has {info.failure_count} consecutive failures")
        
        # Check for expiring tokens
        expiring = self.get_expiring_tokens(self.token_expiry_warning_hours)
        for info in expiring:
            warnings.append(f"{info.server_name} token expires soon")
        
        # Check for servers requiring OAuth
        oauth_servers = [
            info for info in self.server_auth_info.values()
            if info.auth_requirement == AuthRequirement.OAUTH and 
               info.auth_status != AuthStatus.AUTHENTICATED
        ]
        
        for info in oauth_servers:
            issues.append(f"{info.server_name} requires OAuth authentication")
        
        return {
            "status": "healthy" if not issues else "issues_detected",
            "issues": issues,
            "warnings": warnings,
            "total_issues": len(issues),
            "total_warnings": len(warnings)
        }