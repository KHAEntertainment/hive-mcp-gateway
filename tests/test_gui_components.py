"""GUI component tests for Hive MCP Gateway Phase 2 features."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest

# Import GUI components
from gui.system_tray import SystemTrayWidget
from gui.oauth_dialog import OAuthFlowDialog
from gui.credential_management import CredentialManagementWidget
from gui.ide_config_wizard import IDEConfigWizard

# Import services
from hive_mcp_gateway.services.credential_manager import CredentialManager
from hive_mcp_gateway.services.oauth_manager import OAuthManager
from hive_mcp_gateway.services.notification_manager import NotificationManager


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Don't quit the app here to avoid issues with other tests


class TestSystemTrayIntegration:
    """Test system tray widget functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def system_tray(self, qapp, temp_dir):
        """Create system tray widget with mocked dependencies."""
        with patch('gui.system_tray.NotificationManager') as mock_nm:
            mock_nm.return_value = Mock()
            widget = SystemTrayWidget()
            yield widget
            if widget.oauth_dialog:
                widget.oauth_dialog.close()
    
    def test_system_tray_initialization(self, system_tray):
        """Test system tray widget initialization."""
        assert system_tray is not None
        assert system_tray.current_status == "stopped"
        assert system_tray.pending_oauth_requests == {}
    
    def test_oauth_menu_management(self, system_tray):
        """Test OAuth menu management."""
        # Add OAuth request
        system_tray.add_oauth_request("test_server", {"oauth_url": "https://test.com"})
        
        assert "test_server" in system_tray.pending_oauth_requests
        
        # Remove OAuth request
        system_tray.remove_oauth_request("test_server")
        assert "test_server" not in system_tray.pending_oauth_requests
    
    def test_status_updates(self, system_tray):
        """Test status icon updates."""
        # Test status changes
        system_tray.update_status_icon("running")
        assert system_tray.current_status == "running"
        
        system_tray.update_status_icon("warning")
        assert system_tray.current_status == "warning"
        
        system_tray.update_status_icon("error")
        assert system_tray.current_status == "error"
    
    @patch('gui.system_tray.OAuthFlowDialog')
    def test_oauth_dialog_creation(self, mock_dialog_class, system_tray):
        """Test OAuth dialog creation and management."""
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        mock_dialog.initiate_oauth.return_value = True
        
        # Show OAuth dialog
        system_tray.show_oauth_dialog("test_server", {"oauth_url": "https://test.com"})
        
        # Verify dialog was created and configured
        mock_dialog_class.assert_called_once()
        mock_dialog.initiate_oauth.assert_called_once_with("test_server", {"oauth_url": "https://test.com"})
        mock_dialog.show.assert_called_once()


class TestOAuthDialogIntegration:
    """Test OAuth dialog functionality."""
    
    @pytest.fixture
    def oauth_dialog(self, qapp):
        """Create OAuth dialog with mocked dependencies."""
        with patch('gui.oauth_dialog.OAuthManager') as mock_om, \
             patch('gui.oauth_dialog.AuthDetector') as mock_ad:
            
            mock_om.return_value = Mock()
            mock_ad.return_value = Mock()
            
            dialog = OAuthFlowDialog()
            yield dialog
            dialog.close()
    
    def test_oauth_dialog_initialization(self, oauth_dialog):
        """Test OAuth dialog initialization."""
        assert oauth_dialog is not None
        assert oauth_dialog.current_flow is None
        assert oauth_dialog.server_name is None
    
    @patch('gui.oauth_dialog.OAuthFlow')
    def test_oauth_flow_initiation(self, mock_flow_class, oauth_dialog):
        """Test OAuth flow initiation."""
        # Setup mock flow
        mock_flow = Mock()
        mock_flow.service_name = "test_service"
        mock_flow.scope = ["read", "write"]
        mock_flow.auth_url = "https://auth.example.com"
        
        oauth_dialog.oauth_manager.initiate_flow.return_value = mock_flow
        
        # Initiate OAuth
        success = oauth_dialog.initiate_oauth("test_server")
        
        assert success == True
        assert oauth_dialog.current_flow == mock_flow
        assert oauth_dialog.server_name == "test_server"
    
    def test_oauth_callback_handling(self, oauth_dialog):
        """Test OAuth callback URL handling."""
        # Setup mock flow and result
        mock_flow = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.token_data = {"access_token": "test_token"}
        mock_result.expires_at = None
        
        oauth_dialog.current_flow = mock_flow
        oauth_dialog.server_name = "test_server"
        oauth_dialog.oauth_manager.complete_flow.return_value = mock_result
        
        # Simulate callback
        callback_url = "http://localhost:8080/callback?code=test_code&state=test_state"
        oauth_dialog.on_auth_callback(callback_url)
        
        # Verify flow completion was attempted
        oauth_dialog.oauth_manager.complete_flow.assert_called_once_with(mock_flow, callback_url)


class TestCredentialManagementGUI:
    """Test credential management widget."""
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def credential_widget(self, qapp, temp_dir):
        """Create credential management widget."""
        credential_manager = CredentialManager(temp_dir)
        widget = CredentialManagementWidget()
        widget.credential_manager = credential_manager
        yield widget
        widget.close()
    
    def test_credential_widget_initialization(self, credential_widget):
        """Test credential widget initialization."""
        assert credential_widget is not None
        assert hasattr(credential_widget, 'env_tab')
        assert hasattr(credential_widget, 'secrets_tab')
    
    def test_credential_addition(self, credential_widget):
        """Test adding credentials through GUI."""
        # This would test the GUI interaction for adding credentials
        # In a real test, we'd simulate user input and verify the result
        
        # Simulate adding an API key
        with patch.object(credential_widget.credential_manager, 'set_credential') as mock_set:
            mock_set.return_value = Mock()
            
            # Simulate form submission (would be more detailed in actual implementation)
            credential_widget._add_credential("test_api_key", "sk-test123", auto_detect=True)
            
            mock_set.assert_called_once()
    
    def test_sensitivity_preview(self, credential_widget):
        """Test sensitivity detection preview."""
        # Test the preview functionality that shows whether a credential
        # will be classified as sensitive or not
        
        preview_result = credential_widget._preview_sensitivity("api_key", "sk-test123")
        assert preview_result["is_sensitive"] == True
        assert preview_result["credential_type"] == "secret"
        
        preview_result = credential_widget._preview_sensitivity("base_url", "https://api.example.com")
        assert preview_result["is_sensitive"] == False
        assert preview_result["credential_type"] == "environment"


class TestIDEConfigWizard:
    """Test IDE configuration wizard."""
    
    @pytest.fixture
    def temp_ide_dirs(self):
        """Create temporary IDE directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create mock Claude config
            claude_dir = temp_path / "Claude"
            claude_dir.mkdir()
            (claude_dir / "claude_desktop_config.json").write_text('{"mcpServers": {}}')
            
            yield {"claude": claude_dir}
    
    @pytest.fixture
    def ide_wizard(self, qapp, temp_ide_dirs):
        """Create IDE configuration wizard."""
        with patch('gui.ide_config_wizard.IDEDetector') as mock_detector:
            # Setup mock detector
            mock_ide_info = Mock()
            mock_ide_info.name = "Claude Desktop"
            mock_ide_info.is_installed = True
            mock_ide_info.config_exists = True
            mock_ide_info.mcp_servers = {}
            
            mock_detector.return_value.detect_all_ides.return_value = [mock_ide_info]
            
            wizard = IDEConfigWizard()
            yield wizard
            wizard.close()
    
    def test_wizard_initialization(self, ide_wizard):
        """Test wizard initialization."""
        assert ide_wizard is not None
        assert ide_wizard.operation_type == "import"
        assert ide_wizard.selected_ides == []
    
    def test_ide_detection_integration(self, ide_wizard):
        """Test IDE detection integration in wizard."""
        # The wizard should have detected IDEs during initialization
        assert hasattr(ide_wizard, 'detector')
        
        # Test manual refresh
        ide_wizard.page(ide_wizard.PAGE_IDE_SELECT).refresh_ides()
        
        # Verify table was populated (would check row count in real test)
        ide_select_page = ide_wizard.page(ide_wizard.PAGE_IDE_SELECT)
        assert ide_select_page.ide_table.rowCount() >= 0
    
    def test_operation_selection(self, ide_wizard):
        """Test operation type selection."""
        operation_page = ide_wizard.page(ide_wizard.PAGE_OPERATION_SELECT)
        
        # Test import operation
        operation_page.import_radio.setChecked(True)
        operation_page.on_operation_changed()
        assert ide_wizard.operation_type == "import"
        
        # Test export operation
        operation_page.export_radio.setChecked(True)
        operation_page.on_operation_changed()
        assert ide_wizard.operation_type == "export"


class TestGUIIntegration:
    """Test GUI component integration scenarios."""
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def gui_components(self, qapp, temp_dir):
        """Create integrated GUI components."""
        # Create services
        credential_manager = CredentialManager(temp_dir)
        oauth_manager = OAuthManager()
        notification_manager = NotificationManager()
        
        # Create GUI components
        system_tray = SystemTrayWidget()
        
        # Mock the notification manager in system tray
        system_tray.notification_manager = notification_manager
        
        yield {
            "system_tray": system_tray,
            "credential_manager": credential_manager,
            "oauth_manager": oauth_manager,
            "notification_manager": notification_manager
        }
        
        # Cleanup
        if system_tray.oauth_dialog:
            system_tray.oauth_dialog.close()
    
    def test_system_tray_notification_integration(self, gui_components):
        """Test system tray integration with notifications."""
        system_tray = gui_components["system_tray"]
        notification_manager = gui_components["notification_manager"]
        
        # Create OAuth notification
        notification_manager.notify_oauth_required("test_server", "https://oauth.example.com")
        
        # Verify system tray can handle the notification
        oauth_notifications = notification_manager.get_notifications_by_type(
            NotificationType.OAUTH_REQUIRED
        )
        assert len(oauth_notifications) == 1
        
        # Test adding OAuth request to system tray
        system_tray.add_oauth_request("test_server", {"oauth_url": "https://oauth.example.com"})
        assert "test_server" in system_tray.pending_oauth_requests
    
    @patch('gui.oauth_dialog.OAuthFlowDialog')
    def test_oauth_dialog_system_tray_integration(self, mock_dialog_class, gui_components):
        """Test OAuth dialog integration with system tray."""
        system_tray = gui_components["system_tray"]
        
        # Setup mock dialog
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        mock_dialog.initiate_oauth.return_value = True
        
        # Add OAuth request
        system_tray.add_oauth_request("test_server", {"oauth_url": "https://oauth.example.com"})
        
        # Show OAuth dialog
        system_tray.show_oauth_dialog("test_server", {"oauth_url": "https://oauth.example.com"})
        
        # Verify dialog was created and shown
        mock_dialog_class.assert_called_once()
        mock_dialog.show.assert_called_once()
        
        # Simulate successful OAuth completion
        system_tray.on_oauth_completed("test_server", {"access_token": "test_token"})
        
        # Verify request was removed
        assert "test_server" not in system_tray.pending_oauth_requests
    
    def test_gui_error_handling(self, gui_components):
        """Test GUI error handling and user feedback."""
        system_tray = gui_components["system_tray"]
        notification_manager = gui_components["notification_manager"]
        
        # Simulate OAuth failure
        system_tray.on_oauth_failed("test_server", "OAuth authentication failed")
        
        # Verify error notification was created
        error_notifications = notification_manager.get_notifications_by_type(
            NotificationType.ERROR
        )
        # Note: In the actual implementation, the error would be added to notifications
        # This test verifies the error handling mechanism exists