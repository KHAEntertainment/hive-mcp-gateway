"""System tray widget for Hive MCP Gateway with macOS menubar integration."""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QWidget, QMessageBox
from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QBrush, QColor

from hive_mcp_gateway.services.notification_manager import NotificationManager, NotificationType
from .oauth_dialog import OAuthFlowDialog

logger = logging.getLogger(__name__)


class SystemTrayWidget(QSystemTrayIcon):
    """System tray widget with macOS menubar integration and status indicators."""
    
    # Signals for main app communication
    start_service_requested = pyqtSignal()
    stop_service_requested = pyqtSignal()
    restart_service_requested = pyqtSignal()
    show_config_requested = pyqtSignal()
    show_credentials_requested = pyqtSignal()
    show_llm_config_requested = pyqtSignal()
    show_main_window_requested = pyqtSignal()
    show_oauth_dialog_requested = pyqtSignal(str, dict)  # server_name, config
    quit_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize system tray widget."""
        super().__init__(parent)
        
        # Service status tracking
        self.current_status = "stopped"
        self.mcp_proxy_status = False
        
        # Initialize notification manager
        self.notification_manager = NotificationManager(system_tray=self)
        self.notification_manager.oauth_authentication_requested.connect(
            self.on_oauth_authentication_requested
        )
        
        # OAuth dialog tracking
        self.oauth_dialog: Optional[OAuthFlowDialog] = None
        self.pending_oauth_requests: Dict[str, Dict[str, Any]] = {}
        
        # Setup UI
        self.setup_icons()
        self.create_context_menu()
        
        # Connect signals
        self.activated.connect(self.on_tray_activated)
        self.messageClicked.connect(self.on_message_clicked)
        
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(30000)  # Update every 30 seconds
        
        # Set initial status
        self.update_status_icon("stopped")
        
        # Force visibility on macOS
        if hasattr(self, 'setVisible'):
            self.setVisible(True)
        
        # Debug logging
        logger.info(f"System tray widget initialized - isVisible: {self.isVisible()}")
        logger.info(f"System tray available: {QSystemTrayIcon.isSystemTrayAvailable()}")
        logger.info(f"Icon set: {bool(self.icon())}")
    
    def setup_icons(self):
        """Setup status icons for different service states."""
        self.icons = {}
        
        # Load Hive logo PNG icons from assets directory
        icon_dir = Path(__file__).parent / "assets"
        
        # Use the new Hive logo PNG icons
        icon_files = {
            "running": "hive_menubar_running.png",
            "stopped": "hive_menubar_stopped.png", 
            "warning": "hive_menubar_warning.png",
            "error": "hive_menubar_error.png",
            "default": "hive_menubar_default.png"
        }
        
        for status, filename in icon_files.items():
            icon_path = icon_dir / filename
            if icon_path.exists():
                self.icons[status] = QIcon(str(icon_path))
                logger.info(f"Loaded Hive logo icon for {status}: {icon_path}")
            else:
                # Fallback to programmatically created icons
                color_map = {
                    "running": QColor(76, 175, 80),   # Green
                    "stopped": QColor(158, 158, 158), # Gray
                    "warning": QColor(255, 152, 0),   # Orange
                    "error": QColor(244, 67, 54),     # Red
                    "default": QColor(96, 125, 139)   # Blue Gray
                }
                self.icons[status] = self.create_status_icon(color_map.get(status, QColor(128, 128, 128)))
                logger.warning(f"Hive logo icon not found for {status}, using fallback: {icon_path}")
    
    def create_status_icon(self, color: QColor) -> QIcon:
        """Create a simple colored network gateway icon for status indication."""
        pixmap = QPixmap(22, 22)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(color))
        painter.setPen(QColor(0, 0, 0, 150))  # Semi-transparent black outline
        
        # Draw central hub (gateway)
        painter.drawEllipse(8, 8, 6, 6)
        
        # Draw network nodes
        painter.drawEllipse(2, 2, 3, 3)
        painter.drawEllipse(17, 2, 3, 3)
        painter.drawEllipse(2, 17, 3, 3) 
        painter.drawEllipse(17, 17, 3, 3)
        
        # Draw connection lines
        painter.setPen(QColor(color.red(), color.green(), color.blue(), 200))
        painter.drawLine(5, 5, 9, 9)
        painter.drawLine(17, 5, 13, 9)
        painter.drawLine(5, 17, 9, 13)
        painter.drawLine(17, 17, 13, 13)
        
        painter.end()
        
        return QIcon(pixmap)
    
    def create_context_menu(self):
        """Create the context menu for the system tray."""
        self.context_menu = QMenu()
        
        # Service control actions
        self.start_action = QAction("Start Service", self)
        self.start_action.triggered.connect(self.start_service_requested.emit)
        self.context_menu.addAction(self.start_action)
        
        self.stop_action = QAction("Stop Service", self)
        self.stop_action.triggered.connect(self.stop_service_requested.emit)
        self.context_menu.addAction(self.stop_action)
        
        self.restart_action = QAction("Restart Service", self)
        self.restart_action.triggered.connect(self.restart_service_requested.emit)
        self.context_menu.addAction(self.restart_action)
        
        self.context_menu.addSeparator()
        
        # Configuration actions
        self.config_action = QAction("Add MCP Server...", self)
        self.config_action.triggered.connect(self.show_config_requested.emit)
        self.context_menu.addAction(self.config_action)
        
        self.credentials_action = QAction("Manage Credentials...", self)
        self.credentials_action.triggered.connect(self.show_credentials_requested.emit)
        self.context_menu.addAction(self.credentials_action)
        
        self.llm_config_action = QAction("LLM Configuration...", self)
        self.llm_config_action.triggered.connect(self.show_llm_config_requested.emit)
        self.context_menu.addAction(self.llm_config_action)
        
        self.main_window_action = QAction("Show Main Window", self)
        self.main_window_action.triggered.connect(self.show_main_window_requested.emit)
        self.context_menu.addAction(self.main_window_action)
        
        self.context_menu.addSeparator()
        
        # Status information
        self.status_action = QAction("Status: Stopped", self)
        self.status_action.setEnabled(False)
        self.context_menu.addAction(self.status_action)
        
        self.mcp_proxy_action = QAction("mcp-proxy: Not Running", self)
        self.mcp_proxy_action.setEnabled(False)
        self.context_menu.addAction(self.mcp_proxy_action)
        
        self.context_menu.addSeparator()
        
        # OAuth authentication submenu
        self.oauth_menu = QMenu("OAuth Authentication")
        self.oauth_action = QAction("OAuth Authentication", self)
        self.oauth_action.setMenu(self.oauth_menu)
        self.context_menu.addAction(self.oauth_action)
        
        # Initially empty OAuth menu
        self.update_oauth_menu()
        
        self.context_menu.addSeparator()
        
        # Application actions
        self.about_action = QAction("About Hive MCP Gateway", self)
        self.about_action.triggered.connect(self.show_about)
        self.context_menu.addAction(self.about_action)
        
        self.quit_action = QAction("Quit", self)
        self.quit_action.triggered.connect(self.quit_requested.emit)
        self.context_menu.addAction(self.quit_action)
        
        # Set the context menu
        self.setContextMenu(self.context_menu)
    
    def update_status_icon(self, status: str):
        """Update the system tray icon based on service status."""
        self.current_status = status
        
        if status in self.icons:
            self.setIcon(self.icons[status])
        
        # Update tooltip
        tooltip_text = f"Hive MCP Gateway - {status.title()}"
        if self.mcp_proxy_status:
            tooltip_text += "\nmcp-proxy: Running"
        else:
            tooltip_text += "\nmcp-proxy: Not Running"
        
        self.setToolTip(tooltip_text)
        
        # Update status action text
        self.status_action.setText(f"Status: {status.title()}")
        
        # Update available actions based on status
        if status == "running":
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(True)
            self.restart_action.setEnabled(True)
        else:
            self.start_action.setEnabled(True)
            self.stop_action.setEnabled(False)
            self.restart_action.setEnabled(False)
    
    def update_mcp_proxy_status(self, is_running: bool):
        """Update mcp-proxy service status."""
        self.mcp_proxy_status = is_running
        
        # Update status text
        if is_running:
            self.mcp_proxy_action.setText("mcp-proxy: Running")
        else:
            self.mcp_proxy_action.setText("mcp-proxy: Not Running")
        
        # Update tooltip
        self.update_status_icon(self.current_status)
    
    def show_notification(self, title: str, message: str, timeout: int = 5000):
        """Show a system notification."""
        if self.supportsMessages():
            self.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, timeout)
        else:
            # Fallback for systems without notification support
            logger.info(f"Notification: {title} - {message}")
    
    def update_oauth_menu(self):
        """Update the OAuth authentication submenu."""
        self.oauth_menu.clear()
        
        if not self.pending_oauth_requests:
            no_requests_action = QAction("No pending authentications", self)
            no_requests_action.setEnabled(False)
            self.oauth_menu.addAction(no_requests_action)
        else:
            for server_name, config in self.pending_oauth_requests.items():
                action = QAction(f"Authenticate {server_name}", self)
                action.triggered.connect(
                    lambda checked, s=server_name, c=config: self.show_oauth_dialog(s, c)
                )
                self.oauth_menu.addAction(action)
            
            self.oauth_menu.addSeparator()
            
            # Clear all action
            clear_action = QAction("Clear All Requests", self)
            clear_action.triggered.connect(self.clear_all_oauth_requests)
            self.oauth_menu.addAction(clear_action)
    
    def add_oauth_request(self, server_name: str, config: Optional[Dict[str, Any]] = None):
        """Add an OAuth authentication request."""
        self.pending_oauth_requests[server_name] = config or {}
        self.update_oauth_menu()
        
        # Show notification
        self.notification_manager.notify_oauth_required(
            server_name, 
            config.get("oauth_url") if config else None
        )
        
        # Update tray icon to indicate pending auth
        if self.current_status != "error":
            self.update_status_icon("warning")
        
        logger.info(f"Added OAuth request for {server_name}")
    
    def remove_oauth_request(self, server_name: str):
        """Remove an OAuth authentication request."""
        if server_name in self.pending_oauth_requests:
            del self.pending_oauth_requests[server_name]
            self.update_oauth_menu()
            
            # Clear notifications for this server
            self.notification_manager.clear_server_notifications(server_name)
            
            logger.info(f"Removed OAuth request for {server_name}")
    
    def clear_all_oauth_requests(self):
        """Clear all OAuth authentication requests."""
        self.pending_oauth_requests.clear()
        self.update_oauth_menu()
        
        # Clear all OAuth notifications
        for notification in self.notification_manager.get_notifications_by_type(NotificationType.OAUTH_REQUIRED):
            self.notification_manager.dismiss_notification(notification.id)
        
        logger.info("Cleared all OAuth requests")
    
    def show_oauth_dialog(self, server_name: str, config: Dict[str, Any]):
        """Show OAuth authentication dialog for a server."""
        if self.oauth_dialog and self.oauth_dialog.isVisible():
            # Close existing dialog
            self.oauth_dialog.close()
        
        self.oauth_dialog = OAuthFlowDialog()
        self.oauth_dialog.auth_completed.connect(self.on_oauth_completed)
        self.oauth_dialog.auth_failed.connect(self.on_oauth_failed)
        
        # Initiate OAuth flow
        if self.oauth_dialog.initiate_oauth(server_name, config):
            self.oauth_dialog.show()
            self.oauth_dialog.raise_()
            self.oauth_dialog.activateWindow()
        else:
            self.oauth_dialog = None
    
    def on_oauth_authentication_requested(self, server_name: str, config: Dict[str, Any]):
        """Handle OAuth authentication request from notification manager."""
        self.show_oauth_dialog(server_name, config)
    
    def on_oauth_completed(self, server_name: str, token_data: Dict[str, Any]):
        """Handle successful OAuth completion."""
        # Remove the request
        self.remove_oauth_request(server_name)
        
        # Show success notification
        self.notification_manager.notify_success(
            "Authentication Successful",
            f"Successfully authenticated with {server_name}",
            server_name
        )
        
        # Update status if no more pending requests
        if not self.pending_oauth_requests and self.current_status == "warning":
            self.update_status_icon("running")
        
        logger.info(f"OAuth completed for {server_name}")
    
    def on_oauth_failed(self, server_name: str, error_message: str):
        """Handle OAuth failure."""
        # Keep the request for retry
        self.notification_manager.notify_error(
            "Authentication Failed",
            f"Failed to authenticate with {server_name}: {error_message}",
            server_name
        )
        
        logger.error(f"OAuth failed for {server_name}: {error_message}")
    
    def update_status(self):
        """Update status information (called periodically)."""
        # This would typically query the actual service status
        # For now, we'll emit a signal that the main app can handle
        pass
    
    def on_tray_activated(self, reason):
        """Handle system tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Double-click shows main window
            self.show_main_window_requested.emit()
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            # Middle-click toggles service
            if self.current_status == "running":
                self.stop_service_requested.emit()
            else:
                self.start_service_requested.emit()
    
    def on_message_clicked(self):
        """Handle notification message click."""
        # Show main window when notification is clicked
        self.show_main_window_requested.emit()
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            None,
            "About Hive MCP Gateway",
            """
            <h3>Hive MCP Gateway</h3>
            <p>Version 0.3.0</p>
            <p>Intelligent MCP gateway and tool management system - part of The Hive agentic coding ecosystem.</p>
            <p>Features:</p>
            <ul>
                <li>Dynamic tool discovery and provisioning</li>
                <li>Smart semantic search for relevant tools</li>
                <li>Token budget management</li>
                <li>Multiple MCP server integration</li>
                <li>Real-time configuration updates</li>
                <li>IDE auto-detection and configuration injection</li>
                <li>OAuth authentication support</li>
                <li>Secure credential management</li>
            </ul>
            <p><a href="https://github.com/KHAEntertainment/hive-mcp-gateway">GitHub Repository</a></p>
            <p>© 2024 KHAEntertainment</p>
            """
        )


class StatusIndicator:
    """Helper class for managing status indicators."""
    
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"
    WARNING = "warning"
    
    @staticmethod
    def get_color_for_status(status: str) -> QColor:
        """Get color for a given status."""
        colors = {
            StatusIndicator.STOPPED: QColor(128, 128, 128),  # Gray
            StatusIndicator.RUNNING: QColor(0, 255, 0),      # Green
            StatusIndicator.ERROR: QColor(255, 0, 0),        # Red
            StatusIndicator.WARNING: QColor(255, 165, 0),    # Orange
        }
        return colors.get(status, QColor(128, 128, 128))