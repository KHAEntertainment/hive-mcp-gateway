"""Integration tests for Hive MCP Gateway Phase 2 features."""

import asyncio
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from hive_mcp_gateway.services.credential_manager import CredentialManager, CredentialType
from hive_mcp_gateway.services.oauth_manager import OAuthManager
from hive_mcp_gateway.services.auth_detector import AuthDetector, AuthRequirement
from hive_mcp_gateway.services.ide_detector import IDEDetector, IDEType
from hive_mcp_gateway.services.config_injector import ConfigInjector, InjectionResult
from hive_mcp_gateway.services.notification_manager import NotificationManager, NotificationType


class TestCredentialIntegration:
    """Test credential management integration."""
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def credential_manager(self, temp_dir):
        return CredentialManager(temp_dir)
    
    def test_dual_layer_storage(self, credential_manager):
        """Test automatic credential classification."""
        # API key should be classified as secret
        api_key = credential_manager.set_credential("openai_api_key", "sk-1234567890")
        assert api_key.credential_type == CredentialType.SECRET
        
        # URL should be classified as environment
        url = credential_manager.set_credential("base_url", "https://api.openai.com")
        assert url.credential_type == CredentialType.ENVIRONMENT
    
    @patch('keyring.set_password')
    @patch('keyring.get_password')
    def test_keyring_integration(self, mock_get, mock_set, credential_manager):
        """Test keyring storage for secrets."""
        credential_manager.set_credential("test_secret", "secret_value")
        mock_set.assert_called_with("hive-mcp-gateway", "test_secret", "secret_value")
        
        mock_get.return_value = "secret_value"
        retrieved = credential_manager.get_credential("test_secret")
        assert retrieved.value == "secret_value"


class TestOAuthIntegration:
    """Test OAuth system integration."""
    
    @pytest.fixture
    def oauth_manager(self):
        return OAuthManager()
    
    @pytest.fixture
    def auth_detector(self):
        return AuthDetector()
    
    def test_oauth_flow_creation(self, oauth_manager):
        """Test OAuth flow creation."""
        flow = oauth_manager.initiate_flow("google")
        assert flow.service_name == "google"
        assert "code_challenge" in flow.auth_url  # PKCE verification
    
    def test_auth_requirement_detection(self, auth_detector):
        """Test authentication requirement detection."""
        event = auth_detector.analyze_error(
            "test_server",
            "authorization_required: Please visit https://oauth.example.com"
        )
        assert event.auth_requirement == AuthRequirement.OAUTH
        assert event.oauth_url == "https://oauth.example.com"
    
    @patch('httpx.AsyncClient.post')
    async def test_oauth_completion(self, mock_post, oauth_manager):
        """Test OAuth flow completion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "token_123",
            "expires_in": 3600
        }
        mock_post.return_value = mock_response
        
        flow = oauth_manager.initiate_flow("google")
        callback_url = f"http://localhost:8080/callback?code=auth_code&state={flow.state}"
        result = oauth_manager.complete_flow(flow, callback_url)
        
        assert result.success == True
        assert result.token_data["access_token"] == "token_123"


class TestIDEIntegration:
    """Test IDE detection and configuration injection."""
    
    @pytest.fixture
    def temp_ide_dirs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create mock Claude config
            claude_dir = temp_path / "Claude"
            claude_dir.mkdir()
            (claude_dir / "claude_desktop_config.json").write_text('{"mcpServers": {}}')
            
            yield {"claude": claude_dir}
    
    @pytest.fixture
    def ide_detector(self, temp_ide_dirs):
        detector = IDEDetector()
        detector._get_claude_config_path = lambda: temp_ide_dirs["claude"] / "claude_desktop_config.json"
        return detector
    
    @pytest.fixture
    def config_injector(self, temp_ide_dirs):
        backup_dir = Path(temp_ide_dirs["claude"].parent) / "backups"
        return ConfigInjector(backup_dir)
    
    def test_configuration_injection(self, ide_detector, config_injector):
        """Test configuration injection with backup."""
        claude_ide = ide_detector.get_ide_info(IDEType.CLAUDE_DESKTOP)
        
        # Test injection
        operation = config_injector.inject_hive_config(claude_ide)
        assert operation.result == InjectionResult.SUCCESS
        assert operation.backup_path.exists()
        
        # Verify injection worked
        updated_claude = ide_detector.get_ide_info(IDEType.CLAUDE_DESKTOP)
        assert "hive-mcp-gateway" in updated_claude.mcp_servers
        
        # Test removal
        remove_operation = config_injector.remove_hive_config(claude_ide)
        assert remove_operation.result == InjectionResult.SUCCESS


class TestNotificationIntegration:
    """Test notification system integration."""
    
    @pytest.fixture
    def notification_manager(self):
        return NotificationManager()
    
    def test_oauth_notifications(self, notification_manager):
        """Test OAuth notification creation."""
        notification_manager.notify_oauth_required("test_server", "https://oauth.example.com")
        
        oauth_notifications = notification_manager.get_notifications_by_type(
            NotificationType.OAUTH_REQUIRED
        )
        assert len(oauth_notifications) == 1
        assert oauth_notifications[0].server_name == "test_server"
    
    def test_notification_filtering(self, notification_manager):
        """Test notification filtering capabilities."""
        # Create test notifications
        notification_manager.notify_error("Error 1", "Error message", "server1")
        notification_manager.notify_success("Success 1", "Success message", "server2")
        
        # Test filtering by server
        server1_notifications = notification_manager.get_notifications_by_server("server1")
        assert len(server1_notifications) == 1
        assert server1_notifications[0].server_name == "server1"


class TestEndToEndIntegration:
    """Test complete end-to-end scenarios."""
    
    @pytest.fixture
    def integrated_system(self):
        """Create integrated system with all components."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            credential_manager = CredentialManager(temp_path)
            oauth_manager = OAuthManager()
            auth_detector = AuthDetector()
            notification_manager = NotificationManager()
            
            yield {
                "credential_manager": credential_manager,
                "oauth_manager": oauth_manager,
                "auth_detector": auth_detector,
                "notification_manager": notification_manager
            }
    
    def test_oauth_credential_flow(self, integrated_system):
        """Test complete OAuth + credential flow."""
        oauth_manager = integrated_system["oauth_manager"]
        auth_detector = integrated_system["auth_detector"]
        
        # 1. Detect auth requirement
        event = auth_detector.analyze_error(
            "google_service",
            "authorization_required: Visit https://oauth.google.com"
        )
        assert event.auth_requirement == AuthRequirement.OAUTH
        
        # 2. Initiate OAuth flow
        flow = oauth_manager.initiate_flow("google")
        assert flow.service_name == "google"
        
        # 3. Simulate successful completion
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "oauth_token_123",
                "expires_in": 3600
            }
            mock_post.return_value = mock_response
            
            callback_url = f"http://localhost:8080/callback?code=auth_code&state={flow.state}"
            result = oauth_manager.complete_flow(flow, callback_url)
            assert result.success == True
        
        # 4. Record success
        auth_detector.record_success("google_service")
        
        # 5. Verify token availability
        token = oauth_manager.get_valid_token("google_service")
        assert token is not None
    
    def test_monitoring_integration(self, integrated_system):
        """Test monitoring with notifications."""
        auth_detector = integrated_system["auth_detector"]
        notification_manager = integrated_system["notification_manager"]
        
        # Simulate auth failure
        auth_detector.analyze_error("test_server", "unauthorized: invalid credentials")
        
        # Check that we can detect auth issues
        servers_with_issues = auth_detector.get_servers_with_auth_issues()
        assert len(servers_with_issues) >= 1
        assert servers_with_issues[0].server_name == "test_server"
        
        # Test notification for OAuth requirement
        notification_manager.notify_oauth_required("test_server")
        oauth_notifications = notification_manager.get_notifications_by_type(
            NotificationType.OAUTH_REQUIRED
        )
        assert len(oauth_notifications) >= 1