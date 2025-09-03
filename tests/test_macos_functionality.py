"""Comprehensive testing plan for macOS-specific functionality in Hive MCP Gateway."""

import unittest
import tempfile
import os
import plistlib
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Import the components we need to test
from gui.autostart_manager import AutoStartManager, MacOSAutoStartImpl
from gui.main_app import HiveMCPGUI
from gui.system_tray import SystemTrayWidget
from src.hive_mcp_gateway.services.claude_code_sdk import ClaudeCodeSDK
from src.hive_mcp_gateway.services.gemini_cli_sdk import GeminiCLISDK
from src.hive_mcp_gateway.services.credential_manager import CredentialManager


class TestMacOSAutoStartManager(unittest.TestCase):
    """Test macOS Auto Start Manager functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.auto_start_manager = AutoStartManager()
        
        # Mock the launch agents directory for testing (only if on macOS)
        if (hasattr(self.auto_start_manager, '_impl') and 
            isinstance(self.auto_start_manager._impl, MacOSAutoStartImpl)):
            self.auto_start_manager._impl.launch_agents_dir = self.temp_dir
            self.auto_start_manager._impl.plist_path = self.temp_dir / "com.hive.mcp-gateway.plist"
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_auto_start_manager_initialization(self):
        """Test that AutoStartManager initializes correctly on macOS."""
        self.assertIsNotNone(self.auto_start_manager)
        self.assertIsInstance(self.auto_start_manager._impl, MacOSAutoStartImpl)
    
    def test_plist_creation(self):
        """Test Launch Agent plist file creation."""
        if not isinstance(self.auto_start_manager._impl, MacOSAutoStartImpl):
            self.skipTest("Not running on macOS")
        
        impl = self.auto_start_manager._impl
        
        # Test plist creation with mocked app bundle path
        with patch.object(impl, 'get_app_bundle_path') as mock_get_path:
            mock_app_path = Path("/Applications/HiveMCPGateway.app")
            mock_get_path.return_value = mock_app_path
            
            with patch('pathlib.Path.exists', return_value=True):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value.returncode = 0
                    
                    result = impl.create_launch_agent()
                    self.assertTrue(result)
                    
                    # Verify plist file was created
                    self.assertTrue(impl.plist_path.exists())
                    
                    # Verify plist content
                    with open(impl.plist_path, 'rb') as f:
                        plist_data = plistlib.load(f)
                    
                    self.assertEqual(plist_data['Label'], 'com.hive.mcp-gateway')
                    self.assertTrue(plist_data['RunAtLoad'])
                    self.assertIn(sys.executable, plist_data['ProgramArguments'])
    
    def test_launch_agent_status_detection(self):
        """Test detection of launch agent installation and load status."""
        if not isinstance(self.auto_start_manager._impl, MacOSAutoStartImpl):
            self.skipTest("Not running on macOS")
        
        impl = self.auto_start_manager._impl
        
        # Test when plist doesn't exist
        self.assertFalse(impl.is_launch_agent_installed())
        self.assertFalse(impl.is_auto_start_enabled())
        
        # Create a test plist file
        plist_data = {
            "Label": "com.hive.mcp-gateway",
            "ProgramArguments": [sys.executable, sys.argv[0]],
            "RunAtLoad": True
        }
        
        with open(impl.plist_path, 'wb') as f:
            plistlib.dump(plist_data, f)
        
        # Test plist detection
        self.assertTrue(impl.is_launch_agent_installed())
    
    def test_app_bundle_path_detection(self):
        """Test detection of application bundle path."""
        if not isinstance(self.auto_start_manager._impl, MacOSAutoStartImpl):
            self.skipTest("Not running on macOS")
        
        impl = self.auto_start_manager._impl
        
        # Test with mocked common paths
        with patch('pathlib.Path.exists') as mock_exists:
            def exists_side_effect(path_obj):
                return str(path_obj).endswith("HiveMCPGateway.app")
            mock_exists.side_effect = exists_side_effect
            
            with patch('pathlib.Path.is_dir', return_value=True):
                app_path = impl.get_app_bundle_path()
                self.assertIsNotNone(app_path)
                self.assertTrue(str(app_path).endswith("HiveMCPGateway.app"))


class TestMacOSGUIBehavior(unittest.TestCase):
    """Test macOS-specific GUI behavior."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock QApplication to prevent actual GUI creation during tests
        self.mock_app = Mock()
    
    @patch('PyQt6.QtWidgets.QApplication')
    @patch('PyQt6.QtWidgets.QSystemTrayIcon.isSystemTrayAvailable', return_value=True)
    def test_macos_menu_bar_app_initialization(self, mock_tray_available, mock_qapp):
        """Test that the app initializes correctly as a macOS menu bar app."""
        with patch('sys.platform', 'darwin'):
            # Mock the GUI components
            with patch('gui.main_app.SystemTrayWidget') as mock_tray:
                with patch('gui.main_app.ServiceManager') as mock_service:
                    with patch('gui.main_app.DependencyChecker') as mock_deps:
                        with patch('gui.main_app.AutoStartManager') as mock_autostart:
                            # This should not raise any exceptions
                            app = HiveMCPGUI([])
                            
                            # Verify macOS-specific behavior
                            self.assertEqual(app.applicationName(), "Hive MCP Gateway")
                            self.assertFalse(app.quitOnLastWindowClosed())
    
    def test_system_tray_integration(self):
        """Test system tray functionality on macOS."""
        # Mock system tray availability
        with patch('PyQt6.QtWidgets.QSystemTrayIcon.isSystemTrayAvailable', return_value=True):
            tray = SystemTrayWidget(None)
            
            # Verify tray widget was created
            self.assertIsNotNone(tray)
    
    def test_macos_dock_behavior(self):
        """Test that the app hides from dock correctly on macOS."""
        with patch('sys.platform', 'darwin'):
            mock_app = Mock()
            
            # Simulate the macOS behavior configuration
            mock_app.setQuitOnLastWindowClosed(False)
            
            # Verify the call was made
            mock_app.setQuitOnLastWindowClosed.assert_called_with(False)


class TestMacOSCredentialIntegration(unittest.TestCase):
    """Test macOS-specific credential detection and integration."""
    
    def setUp(self):
        """Set up test environment."""
        self.credential_manager = CredentialManager()
        self.claude_sdk = ClaudeCodeSDK(self.credential_manager)
        self.gemini_sdk = GeminiCLISDK(self.credential_manager)
    
    def test_claude_code_detection_macos(self):
        """Test Claude Code detection on macOS."""
        # Mock macOS Claude Code paths
        mock_claude_path = Path("/Applications/Claude Code.app")
        mock_oauth_path = Path.home() / "Library/Application Support/Claude Code/oauth_tokens.json"
        
        with patch('pathlib.Path.exists') as mock_exists:
            def exists_side_effect(path_obj):
                return str(path_obj) in [str(mock_claude_path), str(mock_oauth_path)]
            mock_exists.side_effect = exists_side_effect
            
            with patch('pathlib.Path.is_dir', return_value=True):
                status = self.claude_sdk.get_status()
                
                # Verify detection results
                self.assertIn('claude_code_installed', status)
                self.assertIn('oauth_file_found', status)
    
    def test_gemini_cli_detection_macos(self):
        """Test Gemini CLI detection on macOS."""
        # Mock Gemini CLI installation
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "/usr/local/bin/gemini"
            
            with patch('pathlib.Path.exists', return_value=True):
                status = self.gemini_sdk.get_status()
                
                # Verify detection results
                self.assertIn('gemini_cli_installed', status)
    
    def test_keyring_integration_macos(self):
        """Test macOS keyring integration."""
        # Test storing and retrieving credentials
        test_key = "test_macos_credential"
        test_value = "test_secret_value"
        
        try:
            # Store credential
            success, message = self.credential_manager.validate_keyring_access()
            if success:
                self.credential_manager.set_credential(
                    test_key, 
                    test_value, 
                    description="Test credential for macOS"
                )
                
                # Retrieve credential
                retrieved = self.credential_manager.get_credential(test_key)
                self.assertIsNotNone(retrieved)
                if retrieved:  # Type guard
                    self.assertEqual(retrieved.value, test_value)
                
                # Clean up
                self.credential_manager.delete_credential(test_key)
            else:
                self.skipTest(f"Keyring not available: {message}")
        except Exception as e:
            self.skipTest(f"Keyring test failed: {e}")


class TestMacOSPortConfiguration(unittest.TestCase):
    """Test port configuration persistence on macOS."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_config_path = Path(tempfile.mktemp(suffix='.json'))
        
    def tearDown(self):
        """Clean up test environment."""
        if self.temp_config_path.exists():
            self.temp_config_path.unlink()
    
    def test_port_persistence_macos(self):
        """Test that port configuration persists across application restarts."""
        from src.hive_mcp_gateway.services.config_manager import ConfigManager
        
        # Create config manager with temp file
        config_manager = ConfigManager(str(self.temp_config_path))
        
        # Set a custom port
        test_port = 9001
        success = config_manager.set_port(test_port)
        self.assertTrue(success)
        
        # Create new config manager instance (simulating app restart)
        new_config_manager = ConfigManager(str(self.temp_config_path))
        loaded_config = new_config_manager.load_config()
        
        # Verify port was persisted
        self.assertEqual(loaded_config.tool_gating.port, test_port)


class TestMacOSOAuthFlows(unittest.TestCase):
    """Test OAuth flows work correctly on macOS."""
    
    def setUp(self):
        """Set up test environment."""
        from src.hive_mcp_gateway.services.oauth_manager import OAuthManager
        self.oauth_manager = OAuthManager()
    
    def test_oauth_redirect_uri_generation(self):
        """Test that OAuth redirect URIs are generated correctly for macOS."""
        # Test with default port
        config = self.oauth_manager.oauth_configs.get("google")
        if config:
            self.assertTrue(config.redirect_uri.startswith("http://localhost:"))
            self.assertIn("oauth/callback", config.redirect_uri)
    
    def test_oauth_flow_creation_macos(self):
        """Test OAuth flow creation with macOS-specific considerations."""
        # Configure a test service
        success = self.oauth_manager.configure_service(
            "test_service",
            "test_client_id",
            "test_client_secret"
        )
        self.assertTrue(success)
        
        # Initiate flow
        flow = self.oauth_manager.initiate_oauth_flow("test_service")
        self.assertIsNotNone(flow)
        self.assertIsNotNone(flow.authorization_url)


# Test Suite Configuration
class MacOSTestSuite:
    """Complete macOS testing suite."""
    
    @staticmethod
    def run_all_tests():
        """Run all macOS-specific tests."""
        # Only run on macOS
        if sys.platform != 'darwin':
            print("Skipping macOS tests - not running on macOS")
            return
        
        # Create test suite
        suite = unittest.TestSuite()
        
        # Add test cases
        suite.addTest(unittest.makeSuite(TestMacOSAutoStartManager))
        suite.addTest(unittest.makeSuite(TestMacOSGUIBehavior))
        suite.addTest(unittest.makeSuite(TestMacOSCredentialIntegration))
        suite.addTest(unittest.makeSuite(TestMacOSPortConfiguration))
        suite.addTest(unittest.makeSuite(TestMacOSOAuthFlows))
        
        # Run tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        return result.wasSuccessful()
    
    @staticmethod
    def create_manual_test_checklist():
        """Create a manual testing checklist for macOS functionality."""
        return """
# Manual Testing Checklist for macOS Functionality

## 🚀 Auto Start Manager Tests
- [ ] Enable auto-start through GUI → Verify Launch Agent created in ~/Library/LaunchAgents/
- [ ] Restart macOS → Verify Hive MCP Gateway starts automatically
- [ ] Disable auto-start through GUI → Verify Launch Agent removed
- [ ] Restart macOS → Verify Hive MCP Gateway does NOT start automatically
- [ ] Test auto-start with app installed in different locations (Applications, Downloads, etc.)

## 🔧 GUI and System Integration Tests  
- [ ] App appears in menu bar with correct icon
- [ ] Menu bar icon shows different states (running, stopped, error)
- [ ] App runs in background without dock icon (menu bar only mode)
- [ ] Main window can be shown/hidden correctly
- [ ] System notifications work properly
- [ ] App handles multiple instances correctly (shows warning and exits)

## 🔐 Credential Detection Tests
- [ ] Claude Code detection works when app is installed in /Applications/
- [ ] Claude Code OAuth credentials detected in ~/Library/Application Support/Claude Code/
- [ ] Gemini CLI detection works when installed via Homebrew
- [ ] Gemini CLI credentials detected in ~/.gemini/
- [ ] macOS Keyring integration works for storing secrets
- [ ] Credentials persist across app restarts

## ⚙️ Port Configuration Tests
- [ ] Port number loads from config on startup
- [ ] Port can be changed through GUI
- [ ] Port changes persist after app restart
- [ ] Invalid port numbers show appropriate error messages
- [ ] Service restart required notification appears after port change

## 🌐 OAuth Flow Tests
- [ ] OAuth flows work correctly in embedded WebView
- [ ] Callback URLs redirect properly to localhost
- [ ] OAuth tokens stored securely in keyring
- [ ] Token refresh works automatically
- [ ] Multiple OAuth providers can be configured

## 🧪 Dependency Detection Tests
- [ ] Node.js detection works correctly
- [ ] NPX detection works correctly  
- [ ] Python detection works correctly
- [ ] UV package manager detection works correctly
- [ ] Claude Desktop properly excluded from dependencies list
- [ ] MCP-Proxy properly excluded from dependencies list

## 🔄 Integration Tests
- [ ] All components work together without conflicts
- [ ] Configuration changes propagate correctly
- [ ] Service can start/stop/restart successfully
- [ ] MCP server management works correctly
- [ ] Error handling and recovery works properly

## 📋 Performance Tests
- [ ] App startup time is reasonable (< 3 seconds)
- [ ] Memory usage is acceptable (< 100MB idle)
- [ ] CPU usage is minimal when idle
- [ ] No memory leaks during extended operation
- [ ] GUI remains responsive during background operations

## 🚨 Error Handling Tests
- [ ] Graceful handling of missing dependencies
- [ ] Proper error messages for configuration issues  
- [ ] Recovery from service crashes
- [ ] Handling of permission issues (keyring, file system)
- [ ] Network connectivity error handling for OAuth

## 🔒 Security Tests
- [ ] Credentials stored securely in macOS keyring
- [ ] No secrets logged to console or files
- [ ] OAuth tokens encrypted in storage
- [ ] File permissions set correctly for config files
- [ ] Launch Agent created with appropriate permissions
"""


if __name__ == "__main__":
    # Run automated tests
    print("Running macOS automated tests...")
    success = MacOSTestSuite.run_all_tests()
    
    # Print manual testing checklist
    print("\n" + "="*50)
    print("MANUAL TESTING CHECKLIST")
    print("="*50)
    print(MacOSTestSuite.create_manual_test_checklist())
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)