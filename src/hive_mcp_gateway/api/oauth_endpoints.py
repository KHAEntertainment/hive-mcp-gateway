"""OAuth authentication API endpoints for Hive MCP Gateway."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Query, Depends
from pydantic import BaseModel, Field

from ..services.oauth_manager import OAuthManager, OAuthFlow, TokenInfo, OAuthResult
from ..services.auth_detector import AuthDetector, AuthEvent, AuthRequirement, AuthStatus
from ..services.notification_manager import NotificationManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oauth", tags=["oauth"])

# Global instances (would be properly injected in production)
oauth_manager = OAuthManager()
auth_detector = AuthDetector()
notification_manager = NotificationManager()


# Request/Response Models

class OAuthInitiateRequest(BaseModel):
    """Request to initiate OAuth flow."""
    server_name: str = Field(..., description="Name of the MCP server requiring OAuth")
    service_name: Optional[str] = Field(None, description="OAuth service name (google, github, microsoft, etc.)")
    custom_config: Optional[Dict[str, Any]] = Field(None, description="Custom OAuth configuration")
    custom_scope: Optional[List[str]] = Field(None, description="Custom OAuth scope")


class OAuthInitiateResponse(BaseModel):
    """Response for OAuth flow initiation."""
    success: bool
    flow_id: str
    auth_url: str
    expires_at: datetime
    service_name: str
    scope: List[str]
    message: str


class OAuthCompleteRequest(BaseModel):
    """Request to complete OAuth flow."""
    flow_id: str = Field(..., description="OAuth flow ID")
    callback_url: str = Field(..., description="OAuth callback URL with authorization code")


class OAuthCompleteResponse(BaseModel):
    """Response for OAuth flow completion."""
    success: bool
    server_name: str
    access_token: Optional[str] = Field(None, description="Access token (masked for security)")
    expires_at: Optional[datetime] = Field(None, description="Token expiration time")
    refresh_token_available: bool = Field(False, description="Whether refresh token is available")
    error: Optional[str] = Field(None, description="Error message if failed")


class OAuthStatusResponse(BaseModel):
    """OAuth status for a server."""
    server_name: str
    auth_requirement: str
    auth_status: str
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    failure_count: int
    oauth_url: Optional[str]
    token_expires_at: Optional[datetime]


class OAuthListResponse(BaseModel):
    """List of OAuth statuses."""
    servers: List[OAuthStatusResponse]
    summary: Dict[str, Any]


class AuthEventResponse(BaseModel):
    """Authentication event response."""
    timestamp: datetime
    server_name: str
    event_type: str
    auth_requirement: str
    error_message: Optional[str]
    oauth_url: Optional[str]
    suggested_action: Optional[str]


# Dependency injection helpers

def get_oauth_manager() -> OAuthManager:
    """Get OAuth manager instance."""
    return oauth_manager


def get_auth_detector() -> AuthDetector:
    """Get auth detector instance."""
    return auth_detector


def get_notification_manager() -> NotificationManager:
    """Get notification manager instance."""
    return notification_manager


# API Endpoints

@router.post("/initiate", response_model=OAuthInitiateResponse)
async def initiate_oauth_flow(
    request: OAuthInitiateRequest,
    oauth_mgr: OAuthManager = Depends(get_oauth_manager)
) -> OAuthInitiateResponse:
    """
    Initiate an OAuth authentication flow for a server.
    
    This endpoint starts the OAuth process and returns the authorization URL
    that the client should redirect to for user authentication.
    """
    try:
        logger.info(f"Initiating OAuth flow for server: {request.server_name}")
        
        if request.custom_config:
            # Use custom OAuth configuration
            flow = oauth_mgr.initiate_custom_flow(
                service_name=request.server_name,
                client_id=request.custom_config.get("client_id"),
                client_secret=request.custom_config.get("client_secret"),
                auth_url=request.custom_config.get("auth_url"),
                token_url=request.custom_config.get("token_url"),
                scope=request.custom_scope or request.custom_config.get("scope", [])
            )
        else:
            # Use built-in service configuration
            service_name = request.service_name or request.server_name
            flow = oauth_mgr.initiate_flow(service_name, request.custom_scope)
        
        logger.info(f"OAuth flow initiated: {flow.flow_id}")
        
        return OAuthInitiateResponse(
            success=True,
            flow_id=flow.flow_id,
            auth_url=flow.auth_url,
            expires_at=flow.expires_at,
            service_name=flow.service_name,
            scope=flow.scope,
            message=f"OAuth flow initiated for {request.server_name}. Redirect user to auth_url."
        )
        
    except Exception as e:
        logger.error(f"Failed to initiate OAuth flow for {request.server_name}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to initiate OAuth flow: {str(e)}"
        )


@router.post("/complete", response_model=OAuthCompleteResponse)
async def complete_oauth_flow(
    request: OAuthCompleteRequest,
    oauth_mgr: OAuthManager = Depends(get_oauth_manager),
    auth_det: AuthDetector = Depends(get_auth_detector)
) -> OAuthCompleteResponse:
    """
    Complete an OAuth authentication flow.
    
    This endpoint processes the OAuth callback URL with authorization code
    and exchanges it for access tokens.
    """
    try:
        logger.info(f"Completing OAuth flow: {request.flow_id}")
        
        # Get the flow
        flow = oauth_mgr.get_flow(request.flow_id)
        if not flow:
            raise HTTPException(
                status_code=404,
                detail=f"OAuth flow not found: {request.flow_id}"
            )
        
        # Complete the flow
        result = oauth_mgr.complete_flow(flow, request.callback_url)
        
        if result.success:
            logger.info(f"OAuth flow completed successfully for {flow.service_name}")
            
            # Record success in auth detector
            auth_det.record_success(flow.service_name, {
                "flow_id": request.flow_id,
                "token_type": result.token_data.get("token_type", "Bearer"),
                "expires_at": result.expires_at.isoformat() if result.expires_at else None
            })
            
            # Record token expiry if available
            if result.expires_at:
                auth_det.record_token_expiry(flow.service_name, result.expires_at)
            
            return OAuthCompleteResponse(
                success=True,
                server_name=flow.service_name,
                access_token=f"{result.token_data.get('access_token', '')[:10]}..." if result.token_data.get('access_token') else None,
                expires_at=result.expires_at,
                refresh_token_available=bool(result.token_data.get('refresh_token')),
                error=None
            )
        else:
            logger.error(f"OAuth flow failed for {flow.service_name}: {result.error}")
            
            # Record failure in auth detector
            auth_det.analyze_error(flow.service_name, result.error or "OAuth completion failed")
            
            return OAuthCompleteResponse(
                success=False,
                server_name=flow.service_name,
                access_token=None,
                expires_at=None,
                refresh_token_available=False,
                error=result.error or "OAuth completion failed"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete OAuth flow {request.flow_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete OAuth flow: {str(e)}"
        )


@router.get("/status", response_model=OAuthListResponse)
async def get_oauth_status(
    server_name: Optional[str] = Query(None, description="Filter by server name"),
    auth_det: AuthDetector = Depends(get_auth_detector)
) -> OAuthListResponse:
    """
    Get OAuth authentication status for servers.
    
    Returns the current authentication status for all servers or a specific server.
    """
    try:
        if server_name:
            # Get status for specific server
            server_info = auth_det.get_server_auth_info(server_name)
            if not server_info:
                servers = []
            else:
                servers = [OAuthStatusResponse(
                    server_name=server_info.server_name,
                    auth_requirement=server_info.auth_requirement.value,
                    auth_status=server_info.auth_status.value,
                    last_success=server_info.last_success,
                    last_failure=server_info.last_failure,
                    failure_count=server_info.failure_count,
                    oauth_url=server_info.oauth_url,
                    token_expires_at=server_info.token_expires_at
                )]
        else:
            # Get status for all servers
            servers = []
            for server_info in auth_det.server_auth_info.values():
                servers.append(OAuthStatusResponse(
                    server_name=server_info.server_name,
                    auth_requirement=server_info.auth_requirement.value,
                    auth_status=server_info.auth_status.value,
                    last_success=server_info.last_success,
                    last_failure=server_info.last_failure,
                    failure_count=server_info.failure_count,
                    oauth_url=server_info.oauth_url,
                    token_expires_at=server_info.token_expires_at
                ))
        
        # Get summary
        summary = auth_det.get_auth_summary()
        
        return OAuthListResponse(
            servers=servers,
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Failed to get OAuth status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get OAuth status: {str(e)}"
        )


@router.get("/events", response_model=List[AuthEventResponse])
async def get_auth_events(
    server_name: Optional[str] = Query(None, description="Filter by server name"),
    hours: int = Query(24, description="Hours of history to retrieve"),
    auth_det: AuthDetector = Depends(get_auth_detector)
) -> List[AuthEventResponse]:
    """
    Get recent authentication events.
    
    Returns a list of recent authentication events for monitoring and debugging.
    """
    try:
        events = auth_det.get_recent_events(server_name, hours)
        
        return [
            AuthEventResponse(
                timestamp=event.timestamp,
                server_name=event.server_name,
                event_type=event.event_type,
                auth_requirement=event.auth_requirement.value,
                error_message=event.error_message,
                oauth_url=event.oauth_url,
                suggested_action=event.suggested_action
            )
            for event in events
        ]
        
    except Exception as e:
        logger.error(f"Failed to get auth events: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get auth events: {str(e)}"
        )


@router.post("/refresh")
async def refresh_oauth_token(
    server_name: str = Query(..., description="Server name to refresh token for"),
    oauth_mgr: OAuthManager = Depends(get_oauth_manager),
    auth_det: AuthDetector = Depends(get_auth_detector)
) -> Dict[str, Any]:
    """
    Refresh an OAuth access token using the refresh token.
    
    This endpoint attempts to refresh an expired or expiring access token.
    """
    try:
        logger.info(f"Refreshing OAuth token for server: {server_name}")
        
        # Try to refresh the token
        result = oauth_mgr.refresh_token(server_name)
        
        if result.success:
            logger.info(f"Token refreshed successfully for {server_name}")
            
            # Record success
            auth_det.record_success(server_name, {
                "refreshed": True,
                "expires_at": result.expires_at.isoformat() if result.expires_at else None
            })
            
            # Update token expiry
            if result.expires_at:
                auth_det.record_token_expiry(server_name, result.expires_at)
            
            return {
                "success": True,
                "server_name": server_name,
                "expires_at": result.expires_at,
                "message": "Token refreshed successfully"
            }
        else:
            logger.error(f"Token refresh failed for {server_name}: {result.error}")
            
            # Record failure
            auth_det.analyze_error(server_name, result.error or "Token refresh failed")
            
            return {
                "success": False,
                "server_name": server_name,
                "error": result.error or "Token refresh failed",
                "message": "Token refresh failed - re-authentication may be required"
            }
        
    except Exception as e:
        logger.error(f"Failed to refresh token for {server_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh token: {str(e)}"
        )


@router.delete("/revoke")
async def revoke_oauth_token(
    server_name: str = Query(..., description="Server name to revoke token for"),
    oauth_mgr: OAuthManager = Depends(get_oauth_manager),
    auth_det: AuthDetector = Depends(get_auth_detector)
) -> Dict[str, Any]:
    """
    Revoke an OAuth access token.
    
    This endpoint revokes the stored access token for a server.
    """
    try:
        logger.info(f"Revoking OAuth token for server: {server_name}")
        
        # Revoke the token
        success = oauth_mgr.revoke_token(server_name)
        
        if success:
            logger.info(f"Token revoked successfully for {server_name}")
            
            # Clear server failures since we're starting fresh
            auth_det.clear_server_failures(server_name)
            
            return {
                "success": True,
                "server_name": server_name,
                "message": "Token revoked successfully"
            }
        else:
            logger.warning(f"Token revoke failed for {server_name}")
            
            return {
                "success": False,
                "server_name": server_name,
                "message": "Token revoke failed or no token found"
            }
        
    except Exception as e:
        logger.error(f"Failed to revoke token for {server_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to revoke token: {str(e)}"
        )


@router.get("/health")
async def oauth_health_check(
    auth_det: AuthDetector = Depends(get_auth_detector)
) -> Dict[str, Any]:
    """
    Get OAuth system health status.
    
    Returns overall health status of the OAuth authentication system.
    """
    try:
        health_status = auth_det.monitor_server_health()
        
        # Add OAuth manager status
        oauth_flows = len(oauth_manager.active_flows)
        
        return {
            "status": health_status["status"],
            "issues": health_status["issues"],
            "warnings": health_status["warnings"],
            "total_issues": health_status["total_issues"],
            "total_warnings": health_status["total_warnings"],
            "active_oauth_flows": oauth_flows,
            "oauth_manager_healthy": True,  # Could add actual health checks
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get OAuth health status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get OAuth health status: {str(e)}"
        )


@router.get("/services")
async def list_oauth_services(
    oauth_mgr: OAuthManager = Depends(get_oauth_manager)
) -> Dict[str, Any]:
    """
    List available OAuth service configurations.
    
    Returns a list of built-in OAuth service configurations.
    """
    try:
        services = {}
        
        for service_name, config in oauth_mgr.service_configs.items():
            services[service_name] = {
                "name": service_name,
                "auth_url": config["auth_url"],
                "scope": config.get("scope", []),
                "description": config.get("description", f"OAuth service: {service_name}")
            }
        
        return {
            "services": services,
            "total": len(services)
        }
        
    except Exception as e:
        logger.error(f"Failed to list OAuth services: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list OAuth services: {str(e)}"
        )