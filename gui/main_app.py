"""Main PyQt6 GUI application for Hive MCP Gateway."""

import sys
import logging
import asyncio
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMessageBox
from PyQt6.QtCore import QTimer, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QIcon, QAction

# Import our GUI components
from .system_tray import SystemTrayWidget
from .service_manager import ServiceManager
from .dependency_checker import DependencyChecker
from .autostart_manager import AutoStartManager

# Import backend services
from hive_mcp_gateway.services.config_manager import ConfigManager
from hive_mcp_gateway.services.migration_utility import MigrationUtility

logger = logging.getLogger(__name__)


class HiveMCPGUI(QApplication):
    """Main GUI application for Hive MCP Gateway with macOS menubar integration."""
    
    def __init__(self, argv=None):
        """Initialize the GUI application."""
        if argv is None:
            argv = sys.argv
        
        super().__init__(argv)
        
        # Configure application properties
        self.setApplicationName("Hive MCP Gateway")
        self.setApplicationDisplayName("Hive MCP Gateway")
        self.setApplicationVersion("0.3.0")
        self.setQuitOnLastWindowClosed(False)  # Keep running when windows are closed
        
        # Initialize backend services
        self.config_manager = ConfigManager()
        self.migration_utility = MigrationUtility(self.config_manager)
        
        # Initialize GUI components
        self.main_window: Optional[QMainWindow] = None
        self.system_tray: Optional[SystemTrayWidget] = None
        self.service_manager: Optional[ServiceManager] = None
        self.dependency_checker: Optional[DependencyChecker] = None
        self.autostart_manager: Optional[AutoStartManager] = None
        
        # Setup GUI
        self.setup_application()
        
    def setup_application(self):
        """Setup the complete application."""
        # Configure macOS-specific behavior
        self.configure_macos_behavior()
        
        # Check if system tray is available
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.error("System tray is not available on this platform")
            QMessageBox.critical(
                None,
                "System Tray",
                "System tray is not available on this platform."
            )
            sys.exit(1)
        else:
            logger.info("System tray is available, proceeding with setup")
        
        # Initialize components
        self.setup_backend_services()
        self.setup_system_tray()
        self.setup_main_window()
        
        # Start dependency monitoring
        self.start_dependency_monitoring()
        
        logger.info("Hive MCP Gateway GUI application initialized")
    
    def configure_macos_behavior(self):
        """Configure macOS-specific behaviors."""
        if sys.platform == "darwin":
            # Hide dock icon by default (menu bar only mode)
            self.setQuitOnLastWindowClosed(False)
            
            # Set up application icon for menu bar
            icon_path = Path(__file__).parent / "assets" / "icon.png"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
    
    def setup_backend_services(self):
        """Initialize backend service managers."""
        try:
            self.service_manager = ServiceManager()
            self.dependency_checker = DependencyChecker()
            self.autostart_manager = AutoStartManager()
            
            # Connect signals
            self.service_manager.status_changed.connect(self.on_service_status_changed)
            self.dependency_checker.dependency_status_changed.connect(self.on_dependency_status_changed)
            
        except Exception as e:
            logger.error(f"Failed to initialize backend services: {e}")
            QMessageBox.critical(
                None,
                "Hive MCP Gateway",
                f"Failed to initialize backend services: {e}"
            )
    
    def setup_system_tray(self):
        """Setup system tray icon and menu."""
        try:
            logger.info("Creating system tray widget...")
            self.system_tray = SystemTrayWidget(None)  # Pass None as parent instead of QApplication
            logger.info(f"System tray created, showing... isVisible before show: {self.system_tray.isVisible()}")
            self.system_tray.show()
            logger.info(f"System tray shown, isVisible after show: {self.system_tray.isVisible()}")
            
            # Connect system tray signals to actions
            self.system_tray.start_service_requested.connect(self.start_backend_service)
            self.system_tray.stop_service_requested.connect(self.stop_backend_service)
            self.system_tray.restart_service_requested.connect(self.restart_backend_service)
            self.system_tray.show_config_requested.connect(self.show_snippet_processor)
            self.system_tray.show_credentials_requested.connect(self.show_credentials_manager)
            self.system_tray.show_llm_config_requested.connect(self.show_llm_config)
            self.system_tray.show_main_window_requested.connect(self.show_main_window)
            self.system_tray.quit_requested.connect(self.quit_application)
            
            logger.info("System tray setup completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup system tray: {e}")
            QMessageBox.critical(
                None,
                "Hive MCP Gateway",
                f"Failed to setup system tray: {e}"
            )
    
    def setup_main_window(self):
        """Setup the main application window (hidden by default)."""
        from .main_window import MainWindow
        
        try:
            self.main_window = MainWindow(
                config_manager=self.config_manager,
                service_manager=self.service_manager,
                dependency_checker=self.dependency_checker,
                migration_utility=self.migration_utility,
                parent=None  # QMainWindow should have None parent, not QApplication
            )
            
            # Connect main window navigation signals if they exist
            if hasattr(self.main_window, 'show_snippet_processor_requested'):
                self.main_window.show_snippet_processor_requested.connect(self.show_snippet_processor)
            if hasattr(self.main_window, 'show_credentials_manager_requested'):
                self.main_window.show_credentials_manager_requested.connect(self.show_credentials_manager)
            if hasattr(self.main_window, 'show_llm_config_requested'):
                self.main_window.show_llm_config_requested.connect(self.show_llm_config)
            if hasattr(self.main_window, 'show_autostart_settings_requested'):
                self.main_window.show_autostart_settings_requested.connect(self.show_autostart_settings)
            
            # Don't show main window by default (menubar app)
            # self.main_window.show()
            
        except Exception as e:
            logger.error(f"Failed to setup main window: {e}")
    
    def safe_show_notification(self, title: str, message: str, timeout: int = 5000):
        """Safely show system tray notification."""
        if self.system_tray:
            try:
                self.system_tray.show_notification(title, message, timeout)
            except Exception as e:
                logger.error(f"Failed to show notification: {e}")
    
    def start_dependency_monitoring(self):
        """Start monitoring dependencies."""
        if self.dependency_checker:
            self.dependency_checker.start_dependency_monitoring()
    
    def start_backend_service(self):
        """Start the Hive MCP Gateway backend service."""
        if self.service_manager:
            success = self.service_manager.start_service()
            if success:
                self.safe_show_notification(
                    "Service Started",
                    "Hive MCP Gateway service started successfully"
                )
            else:
                self.safe_show_notification(
                    "Service Error",
                    "Failed to start Hive MCP Gateway service"
                )
    
    def stop_backend_service(self):
        """Stop the Hive MCP Gateway backend service."""
        if self.service_manager:
            success = self.service_manager.stop_service()
            if success:
                self.safe_show_notification(
                    "Service Stopped",
                    "Hive MCP Gateway service stopped"
                )
    
    def restart_backend_service(self):
        """Restart the Hive MCP Gateway backend service."""
        if self.service_manager:
            success = self.service_manager.restart_service()
            if success:
                self.safe_show_notification(
                    "Service Restarted",
                    "Hive MCP Gateway service restarted successfully"
                )
    
    def show_snippet_processor(self):
        """Show the JSON snippet processor window."""
        try:
            from .snippet_processor import MCPSnippetProcessor
            
            if not hasattr(self, '_snippet_processor'):
                self._snippet_processor = MCPSnippetProcessor(self.config_manager)
                # Connect the processed signal to show a notification
                self._snippet_processor.snippet_processed.connect(self.on_snippet_processed)
            
            self._snippet_processor.show()
            self._snippet_processor.raise_()
            self._snippet_processor.activateWindow()
            
        except Exception as e:
            logger.error(f"Failed to show snippet processor: {e}")
            QMessageBox.critical(
                None,
                "Snippet Processor Error",
                f"Failed to open snippet processor: {e}"
            )
    
    def show_credentials_manager(self):
        """Show the credentials management window."""
        try:
            from .credential_management import CredentialManagementWidget
            
            if not hasattr(self, '_credentials_manager'):
                self._credentials_manager = CredentialManagementWidget()
            
            self._credentials_manager.show()
            self._credentials_manager.raise_()
            self._credentials_manager.activateWindow()
            
        except Exception as e:
            logger.error(f"Failed to show credentials manager: {e}")
            QMessageBox.critical(
                None,
                "Credentials Manager Error",
                f"Failed to open credentials manager: {e}"
            )
    
    def show_llm_config(self):
        """Show the LLM configuration window."""
        try:
            from .llm_config import LLMConfigWidget
            
            if not hasattr(self, '_llm_config_widget'):
                self._llm_config_widget = LLMConfigWidget()
            
            self._llm_config_widget.show()
            self._llm_config_widget.raise_()
            self._llm_config_widget.activateWindow()
            
        except Exception as e:
            logger.error(f"Failed to show LLM config: {e}")
            QMessageBox.critical(
                None,
                "LLM Configuration Error",
                f"Failed to open LLM configuration: {e}"
            )
    
    def show_main_window(self):
        """Show the main application window."""
        if self.main_window:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
    
    def on_service_status_changed(self, status: str):
        """Handle service status changes."""
        if self.system_tray:
            if status == "running":
                self.system_tray.update_status_icon("running")
            elif status == "stopped":
                self.system_tray.update_status_icon("stopped")
            elif status == "error":
                self.system_tray.update_status_icon("error")
    
    def on_dependency_status_changed(self, service_name: str, is_running: bool):
        """Handle dependency status changes."""
        if service_name == "mcp-proxy" and not is_running:
            self.safe_show_notification(
                "Dependency Warning",
                "mcp-proxy service is not running. Hive MCP Gateway may not work with Claude Desktop."
            )
    
    def on_snippet_processed(self, server_name: str, success: bool):
        """Handle snippet processing completion."""
        if success:
            self.safe_show_notification(
                "MCP Server Added",
                f"Successfully registered '{server_name}' MCP server"
            )
        else:
            self.safe_show_notification(
                "Registration Failed",
                f"Failed to register MCP server '{server_name}'"
            )
    
    def show_autostart_settings(self):
        """Show auto-start settings dialog."""
        try:
            if self.autostart_manager:
                # Check current autostart status
                is_enabled = self.autostart_manager.is_auto_start_enabled()
                
                if is_enabled:
                    reply = QMessageBox.question(
                        None,
                        "Auto-Start Settings",
                        "Auto-start is currently ENABLED.\n\nDo you want to disable it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        success = self.autostart_manager.disable_auto_start()
                        if success:
                            self.safe_show_notification(
                                "Auto-Start Disabled",
                                "Hive MCP Gateway will no longer start automatically"
                            )
                        else:
                            QMessageBox.warning(None, "Error", "Failed to disable auto-start")
                else:
                    reply = QMessageBox.question(
                        None,
                        "Auto-Start Settings",
                        "Auto-start is currently DISABLED.\n\nDo you want to enable it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        success = self.autostart_manager.enable_auto_start()
                        if success:
                            self.safe_show_notification(
                                "Auto-Start Enabled",
                                "Hive MCP Gateway will start automatically at login"
                            )
                        else:
                            QMessageBox.warning(None, "Error", "Failed to enable auto-start")
            else:
                QMessageBox.warning(None, "Error", "Auto-start manager not available")
                
        except Exception as e:
            logger.error(f"Failed to show auto-start settings: {e}")
            QMessageBox.critical(
                None,
                "Auto-Start Settings Error",
                f"Failed to access auto-start settings: {e}"
            )
    
    def quit_application(self):
        """Quit the application gracefully."""
        logger.info("Shutting down Hive MCP Gateway GUI...")
        
        # Stop dependency monitoring
        if self.dependency_checker:
            self.dependency_checker.stop_dependency_monitoring()
        
        # Stop backend service if running
        if self.service_manager:
            service_status = self.service_manager.get_service_status()
            if service_status.is_running:
                self.service_manager.stop_service()
        
        # Hide system tray
        if self.system_tray:
            self.system_tray.hide()
        
        # Quit application
        self.quit()


def main():
    """Main entry point for the GUI application."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run application
    app = HiveMCPGUI()
    
    # Show startup notification
    if app.system_tray:
        app.system_tray.show_notification(
            "Hive MCP Gateway",
            "Application started. Access from the menu bar."
        )
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()