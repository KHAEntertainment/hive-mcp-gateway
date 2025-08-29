"""OAuth flow tests for Hive MCP Gateway authentication scenarios."""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

from hive_mcp_gateway.services.oauth_manager import OAuthManager, OAuthFlow, OAuthResult
from hive_mcp_gateway.services.auth_detector import AuthDetector, AuthRequirement


class TestOAuthFlowScenarios:
    """Test various OAuth flow scenarios."""
    
    @pytest.fixture
    def oauth_manager(self):
        """Create OAuth manager instance."""
        return OAuthManager()
    
    @pytest.fixture
    def auth_detector(self):
        """Create auth detector instance."""
        return AuthDetector()
    
    def test_google_oauth_flow(self, oauth_manager):
        """Test Google OAuth flow initiation."""
        flow = oauth_manager.initiate_flow("google")
        
        # Verify flow properties
        assert flow.service_name == "google"
        assert flow.flow_id is not None
        assert flow.state is not None
        assert flow.code_verifier is not None
        assert flow.code_challenge is not None
        
        # Verify auth URL contains required parameters
        auth_url_parts = urlparse(flow.auth_url)
        query_params = parse_qs(auth_url_parts.query)
        
        assert "client_id" in query_params
        assert "redirect_uri" in query_params
        assert "response_type" in query_params
        assert query_params["response_type"][0] == "code"
        assert "state" in query_params
        assert query_params["state"][0] == flow.state
        assert "code_challenge" in query_params
        assert "code_challenge_method" in query_params
        assert query_params["code_challenge_method"][0] == "S256"
    
    def test_github_oauth_flow(self, oauth_manager):
        """Test GitHub OAuth flow initiation."""
        flow = oauth_manager.initiate_flow("github")
        
        assert flow.service_name == "github"
        assert "github.com" in flow.auth_url
        
        # Verify GitHub-specific scope
        query_params = parse_qs(urlparse(flow.auth_url).query)
        assert "scope" in query_params
    
    def test_microsoft_oauth_flow(self, oauth_manager):
        """Test Microsoft OAuth flow initiation."""
        flow = oauth_manager.initiate_flow("microsoft")
        
        assert flow.service_name == "microsoft"
        assert "login.microsoftonline.com" in flow.auth_url
    
    def test_custom_oauth_flow(self, oauth_manager):
        """Test custom OAuth service configuration."""
        custom_flow = oauth_manager.initiate_custom_flow(
            service_name="custom_service",
            client_id="custom_client_123",
            client_secret="custom_secret_456",
            auth_url="https://custom-auth.example.com/oauth/authorize",
            token_url="https://custom-auth.example.com/oauth/token",
            scope=["read", "write", "admin"]
        )
        
        assert custom_flow.service_name == "custom_service"
        assert custom_flow.scope == ["read", "write", "admin"]
        assert "custom_client_123" in custom_flow.auth_url
        assert "custom-auth.example.com" in custom_flow.auth_url
    
    @patch('httpx.AsyncClient.post')
    async def test_successful_oauth_completion(self, mock_post, oauth_manager):
        """Test successful OAuth flow completion."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "access_token_12345",
            "refresh_token": "refresh_token_67890",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "read write"
        }
        mock_post.return_value = mock_response
        
        # Create and complete flow
        flow = oauth_manager.initiate_flow("google")
        callback_url = f"http://localhost:8080/callback?code=auth_code_123&state={flow.state}"
        
        result = oauth_manager.complete_flow(flow, callback_url)
        
        # Verify successful completion
        assert result.success == True
        assert result.token_data["access_token"] == "access_token_12345"
        assert result.token_data["refresh_token"] == "refresh_token_67890"
        assert result.expires_at is not None
        
        # Verify token was stored
        stored_token = oauth_manager.get_valid_token("google")
        assert stored_token == "access_token_12345"
    
    @patch('httpx.AsyncClient.post')
    async def test_oauth_completion_with_error(self, mock_post, oauth_manager):
        """Test OAuth completion with error response."""
        # Setup mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "The authorization code is invalid"
        }
        mock_post.return_value = mock_response
        
        # Create and complete flow
        flow = oauth_manager.initiate_flow("google")
        callback_url = f"http://localhost:8080/callback?code=invalid_code&state={flow.state}"
        
        result = oauth_manager.complete_flow(flow, callback_url)
        
        # Verify error handling
        assert result.success == False
        assert "invalid_grant" in result.error
    
    async def test_invalid_state_protection(self, oauth_manager):
        """Test protection against invalid state parameter."""
        flow = oauth_manager.initiate_flow("google")
        
        # Use wrong state parameter
        callback_url = "http://localhost:8080/callback?code=auth_code_123&state=wrong_state"
        
        result = oauth_manager.complete_flow(flow, callback_url)
        
        # Should fail due to state mismatch
        assert result.success == False
        assert "state" in result.error.lower()
    
    async def test_missing_authorization_code(self, oauth_manager):
        """Test handling of missing authorization code."""
        flow = oauth_manager.initiate_flow("google")
        
        # Callback without code parameter
        callback_url = f"http://localhost:8080/callback?state={flow.state}"
        
        result = oauth_manager.complete_flow(flow, callback_url)
        
        # Should fail due to missing code
        assert result.success == False
        assert "code" in result.error.lower()
    
    async def test_oauth_error_callback(self, oauth_manager):
        """Test handling of OAuth error in callback."""
        flow = oauth_manager.initiate_flow("google")
        
        # Callback with error
        callback_url = f"http://localhost:8080/callback?error=access_denied&error_description=User+denied+access&state={flow.state}"
        
        result = oauth_manager.complete_flow(flow, callback_url)
        
        # Should fail with user-friendly error
        assert result.success == False
        assert "access_denied" in result.error
    
    def test_flow_expiration(self, oauth_manager):
        """Test OAuth flow expiration handling."""
        # Create flow
        flow = oauth_manager.initiate_flow("google")
        original_expires_at = flow.expires_at
        
        # Manually expire the flow
        flow.expires_at = datetime.now() - timedelta(minutes=1)
        oauth_manager.active_flows[flow.flow_id] = flow
        
        # Try to complete expired flow
        callback_url = f"http://localhost:8080/callback?code=auth_code_123&state={flow.state}"
        result = oauth_manager.complete_flow(flow, callback_url)
        
        # Should fail due to expiration
        assert result.success == False
        assert "expired" in result.error.lower()
    
    @patch('httpx.AsyncClient.post')
    async def test_token_refresh(self, mock_post, oauth_manager):
        """Test OAuth token refresh functionality."""
        # Setup initial token
        oauth_manager.active_tokens["test_service"] = {
            "access_token": "old_access_token",
            "refresh_token": "refresh_token_123",
            "expires_at": datetime.now() - timedelta(minutes=1)  # Expired
        }
        
        # Setup mock refresh response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        mock_post.return_value = mock_response
        
        # Attempt token refresh
        result = oauth_manager.refresh_token("test_service")
        
        # Verify refresh success
        assert result.success == True
        assert result.token_data["access_token"] == "new_access_token"
        
        # Verify new token is stored
        new_token = oauth_manager.get_valid_token("test_service")
        assert new_token == "new_access_token"
    
    async def test_token_revocation(self, oauth_manager):
        """Test OAuth token revocation."""
        # Setup token
        oauth_manager.active_tokens["test_service"] = {
            "access_token": "access_token_123",
            "refresh_token": "refresh_token_456",
            "expires_at": datetime.now() + timedelta(hours=1)
        }
        
        # Revoke token
        success = oauth_manager.revoke_token("test_service")
        
        # Verify revocation
        assert success == True
        assert oauth_manager.get_valid_token("test_service") is None
    
    def test_pkce_implementation(self, oauth_manager):
        """Test PKCE (Proof Key for Code Exchange) implementation."""
        flow = oauth_manager.initiate_flow("google")
        
        # Verify PKCE parameters are present
        assert flow.code_verifier is not None
        assert flow.code_challenge is not None
        assert len(flow.code_verifier) >= 43  # PKCE spec minimum
        assert len(flow.code_challenge) >= 43
        
        # Verify code challenge is in auth URL
        assert "code_challenge" in flow.auth_url
        assert "code_challenge_method=S256" in flow.auth_url
    
    def test_scope_customization(self, oauth_manager):
        """Test OAuth scope customization."""
        # Test with custom scope
        custom_scope = ["read:user", "write:data", "admin:settings"]
        flow = oauth_manager.initiate_flow("google", custom_scope=custom_scope)
        
        assert flow.scope == custom_scope
        
        # Verify scope is in auth URL
        query_params = parse_qs(urlparse(flow.auth_url).query)
        assert "scope" in query_params
        scope_param = query_params["scope"][0]
        for scope_item in custom_scope:
            assert scope_item in scope_param


class TestAuthenticationDetection:
    """Test authentication requirement detection."""
    
    @pytest.fixture
    def auth_detector(self):
        return AuthDetector()
    
    def test_oauth_requirement_detection(self, auth_detector):
        """Test OAuth requirement detection from error messages."""
        test_cases = [
            {
                "error": "authorization_required: Please visit https://oauth.google.com/auth",
                "expected_auth": AuthRequirement.OAUTH,
                "expected_url": "https://oauth.google.com/auth"
            },
            {
                "error": "oauth_token_expired: Token has expired, please re-authenticate",
                "expected_auth": AuthRequirement.OAUTH,
                "expected_url": None
            },
            {
                "error": "login_required: Visit https://github.com/login/oauth/authorize?client_id=123",
                "expected_auth": AuthRequirement.OAUTH,
                "expected_url": "https://github.com/login/oauth/authorize?client_id=123"
            }
        ]
        
        for case in test_cases:
            event = auth_detector.analyze_error("test_server", case["error"])
            
            assert event.auth_requirement == case["expected_auth"]
            assert event.oauth_url == case["expected_url"]
            assert "OAuth" in event.suggested_action
    
    def test_api_key_requirement_detection(self, auth_detector):
        """Test API key requirement detection."""
        test_cases = [
            "api_key_required: Please provide a valid API key",
            "invalid_api_key: The provided API key is invalid or expired",
            "missing_api_key: API key is required for this operation"
        ]
        
        for error_message in test_cases:
            event = auth_detector.analyze_error("test_server", error_message)
            
            assert event.auth_requirement == AuthRequirement.API_KEY
            assert "API key" in event.suggested_action
    
    def test_bearer_token_requirement_detection(self, auth_detector):
        """Test bearer token requirement detection."""
        test_cases = [
            "bearer_token_required: Authorization header with Bearer token required",
            "invalid_bearer_token: The provided bearer token is invalid",
            "authorization_header_required: Missing Authorization header"
        ]
        
        for error_message in test_cases:
            event = auth_detector.analyze_error("test_server", error_message)
            
            assert event.auth_requirement == AuthRequirement.BEARER_TOKEN
    
    def test_token_expiry_monitoring(self, auth_detector):
        """Test token expiry monitoring and warnings."""
        server_name = "test_server"
        
        # Test token expiring soon
        expires_soon = datetime.now() + timedelta(minutes=30)
        auth_detector.record_token_expiry(server_name, expires_soon)
        
        expiring_tokens = auth_detector.get_expiring_tokens(hours_ahead=1)
        assert len(expiring_tokens) == 1
        assert expiring_tokens[0].server_name == server_name
        
        # Test token not expiring soon
        expires_later = datetime.now() + timedelta(hours=2)
        auth_detector.record_token_expiry("other_server", expires_later)
        
        expiring_tokens = auth_detector.get_expiring_tokens(hours_ahead=1)
        # Should still be 1 (only the first server)
        assert len([t for t in expiring_tokens if t.server_name == server_name]) == 1
    
    def test_authentication_success_tracking(self, auth_detector):
        """Test authentication success tracking."""
        server_name = "test_server"
        
        # Record authentication success
        auth_detector.record_success(server_name, {"method": "oauth"})
        
        # Verify server info was updated
        server_info = auth_detector.get_server_auth_info(server_name)
        assert server_info is not None
        assert server_info.last_success is not None
        assert server_info.failure_count == 0
    
    def test_failure_counting(self, auth_detector):
        """Test authentication failure counting."""
        server_name = "test_server"
        
        # Record multiple failures
        for i in range(3):
            auth_detector.analyze_error(server_name, "unauthorized: invalid credentials")
        
        # Check failure count
        server_info = auth_detector.get_server_auth_info(server_name)
        assert server_info.failure_count == 3
        
        # Record success - should reset failure count
        auth_detector.record_success(server_name)
        
        server_info = auth_detector.get_server_auth_info(server_name)
        assert server_info.failure_count == 0


class TestOAuthIntegrationScenarios:
    """Test OAuth integration with other components."""
    
    @pytest.fixture
    def oauth_manager(self):
        return OAuthManager()
    
    @pytest.fixture
    def auth_detector(self):
        return AuthDetector()
    
    def test_oauth_flow_with_auth_detection(self, oauth_manager, auth_detector):
        """Test complete OAuth flow triggered by auth detection."""
        server_name = "google_service"
        
        # 1. Detect OAuth requirement
        event = auth_detector.analyze_error(
            server_name,
            "authorization_required: Please visit https://accounts.google.com/oauth2/auth"
        )
        
        assert event.auth_requirement == AuthRequirement.OAUTH
        assert event.oauth_url is not None
        
        # 2. Initiate OAuth flow based on detection
        flow = oauth_manager.initiate_flow("google")
        assert flow.service_name == "google"
        
        # 3. Simulate successful completion
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "oauth_access_token",
                "expires_in": 3600
            }
            mock_post.return_value = mock_response
            
            callback_url = f"http://localhost:8080/callback?code=auth_code&state={flow.state}"
            result = oauth_manager.complete_flow(flow, callback_url)
            
            assert result.success == True
        
        # 4. Record success in auth detector
        auth_detector.record_success(server_name, {
            "method": "oauth",
            "token_expires_at": result.expires_at.isoformat() if result.expires_at else None
        })
        
        # 5. Verify the issue is resolved
        server_info = auth_detector.get_server_auth_info(server_name)
        assert server_info.last_success is not None
        assert server_info.failure_count == 0
    
    @patch('httpx.AsyncClient.post')
    async def test_concurrent_oauth_flows(self, mock_post, oauth_manager):
        """Test handling of concurrent OAuth flows."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "access_token",
            "expires_in": 3600
        }
        mock_post.return_value = mock_response
        
        # Create multiple concurrent flows
        flow1 = oauth_manager.initiate_flow("google")
        flow2 = oauth_manager.initiate_flow("github") 
        flow3 = oauth_manager.initiate_custom_flow(
            "custom", "client_id", "secret", 
            "https://auth.example.com", "https://token.example.com"
        )
        
        # Verify all flows are tracked
        assert len(oauth_manager.active_flows) == 3
        assert flow1.flow_id != flow2.flow_id != flow3.flow_id
        
        # Complete flows concurrently
        callback1 = f"http://localhost:8080/callback?code=code1&state={flow1.state}"
        callback2 = f"http://localhost:8080/callback?code=code2&state={flow2.state}"
        callback3 = f"http://localhost:8080/callback?code=code3&state={flow3.state}"
        
        results = await asyncio.gather(
            asyncio.create_task(asyncio.to_thread(oauth_manager.complete_flow, flow1, callback1)),
            asyncio.create_task(asyncio.to_thread(oauth_manager.complete_flow, flow2, callback2)),
            asyncio.create_task(asyncio.to_thread(oauth_manager.complete_flow, flow3, callback3))
        )
        
        # Verify all completed successfully
        assert all(result.success for result in results)
        assert len(oauth_manager.active_tokens) == 3