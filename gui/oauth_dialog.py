"""OAuth authentication dialog with embedded webview for Hive MCP Gateway."""

import logging
import json
from typing import Optional, Dict, Any, Callable
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QProgressBar, QTextEdit, QGroupBox, QMessageBox, QWidget,
    QSplitter, QFrame, QTabWidget, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread, QUrl
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage

from hive_mcp_gateway.services.oauth_manager import OAuthManager, OAuthFlow, OAuthResult
from hive_mcp_gateway.services.auth_detector import AuthDetector, AuthEvent

logger = logging.getLogger(__name__)


class OAuthWebView(QWebEngineView):
    """Custom WebView for OAuth authentication with callback detection."""
    
    auth_completed = pyqtSignal(str)  # Emits the callback URL
    auth_error = pyqtSignal(str)      # Emits error message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Configure settings
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        
        # Connect to URL changes
        self.urlChanged.connect(self.on_url_changed)
        self.loadFinished.connect(self.on_load_finished)
        self.loadStarted.connect(self.on_load_started)
    
    def on_url_changed(self, url: QUrl):
        """Handle URL changes to detect OAuth callbacks."""
        url_str = url.toString()
        logger.debug(f"OAuth WebView URL changed: {url_str}")
        
        # Check for localhost callback (typical OAuth pattern)
        if "localhost" in url_str and ("code=" in url_str or "error=" in url_str):
            self.auth_completed.emit(url_str)
        
        # Check for other common callback patterns
        elif any(pattern in url_str for pattern in ["callback", "redirect", "oauth/complete"]):
            if "code=" in url_str or "error=" in url_str or "access_token=" in url_str:
                self.auth_completed.emit(url_str)
    
    def on_load_finished(self, success: bool):
        """Handle page load completion."""
        if not success:
            current_url = self.url().toString()
            if current_url:
                self.auth_error.emit(f"Failed to load: {current_url}")
    
    def on_load_started(self):
        """Handle page load start."""
        logger.debug("OAuth page load started")


class OAuthFlowDialog(QDialog):
    """Dialog for managing OAuth authentication flows."""
    
    auth_completed = pyqtSignal(str, dict)  # server_name, token_data
    auth_failed = pyqtSignal(str, str)      # server_name, error_message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("OAuth Authentication - Hive MCP Gateway")
        self.setMinimumSize(900, 700)
        self.setModal(True)
        
        # Services
        self.oauth_manager = OAuthManager()
        self.auth_detector = AuthDetector()
        
        # Current flow tracking
        self.current_flow: Optional[OAuthFlow] = None
        self.server_name: Optional[str] = None
        self.callback_handler: Optional[Callable] = None
        
        # Setup UI
        self.setup_ui()
        
        # Setup timers
        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self.on_auth_timeout)
        
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
    
    def setup_ui(self):
        """Setup the OAuth dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        self.title_label = QLabel("OAuth Authentication")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        self.close_button = QPushButton("Cancel")
        self.close_button.clicked.connect(self.reject)
        header_layout.addWidget(self.close_button)
        
        layout.addLayout(header_layout)
        
        # Main content with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - flow info and status
        left_panel = self.create_info_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - webview
        right_panel = self.create_webview_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions (30% left, 70% right)
        splitter.setSizes([270, 630])
        
        layout.addWidget(splitter)
        
        # Status bar
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Ready for authentication")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        
        layout.addLayout(status_layout)
    
    def create_info_panel(self) -> QWidget:
        """Create the information panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Flow information
        flow_group = QGroupBox("OAuth Flow Information")
        flow_layout = QVBoxLayout(flow_group)
        
        self.server_label = QLabel("Server: Not selected")
        self.provider_label = QLabel("Provider: Unknown")
        self.scope_label = QLabel("Scope: None")
        self.state_label = QLabel("State: Ready")
        
        flow_layout.addWidget(self.server_label)
        flow_layout.addWidget(self.provider_label)
        flow_layout.addWidget(self.scope_label)
        flow_layout.addWidget(self.state_label)
        
        layout.addWidget(flow_group)
        
        # Instructions
        instructions_group = QGroupBox("Instructions")
        instructions_layout = QVBoxLayout(instructions_group)
        
        self.instructions_text = QTextEdit()
        self.instructions_text.setMaximumHeight(150)
        self.instructions_text.setPlainText(
            "1. Click 'Start OAuth Flow' to begin authentication\n"
            "2. You will be redirected to the provider's login page\n"
            "3. Login with your credentials\n"
            "4. Grant permissions to Hive MCP Gateway\n"
            "5. You will be redirected back automatically"
        )
        self.instructions_text.setReadOnly(True)
        instructions_layout.addWidget(self.instructions_text)
        
        layout.addWidget(instructions_group)
        
        # Actions
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        
        self.start_button = QPushButton("Start OAuth Flow")
        self.start_button.clicked.connect(self.start_oauth_flow)
        self.start_button.setEnabled(False)
        actions_layout.addWidget(self.start_button)
        
        self.refresh_button = QPushButton("Refresh Page")
        self.refresh_button.clicked.connect(self.refresh_webview)
        self.refresh_button.setEnabled(False)
        actions_layout.addWidget(self.refresh_button)
        
        self.manual_code_button = QPushButton("Enter Code Manually")
        self.manual_code_button.clicked.connect(self.enter_manual_code)
        self.manual_code_button.setEnabled(False)
        actions_layout.addWidget(self.manual_code_button)
        
        layout.addWidget(actions_group)
        
        # Recent auth events
        events_group = QGroupBox("Recent Events")
        events_layout = QVBoxLayout(events_group)
        
        self.events_list = QListWidget()
        self.events_list.setMaximumHeight(150)
        events_layout.addWidget(self.events_list)
        
        layout.addWidget(events_group)
        
        layout.addStretch()
        
        return panel
    
    def create_webview_panel(self) -> QWidget:
        """Create the webview panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Webview header
        webview_header = QHBoxLayout()
        
        self.url_label = QLabel("URL: Not loaded")
        self.url_label.setStyleSheet("font-family: monospace; font-size: 12px; color: #666;")
        webview_header.addWidget(self.url_label)
        
        webview_header.addStretch()
        
        self.webview_status = QLabel("●")
        self.webview_status.setStyleSheet("color: #ccc; font-size: 16px;")
        webview_header.addWidget(self.webview_status)
        
        layout.addLayout(webview_header)
        
        # WebView
        self.webview = OAuthWebView()
        self.webview.auth_completed.connect(self.on_auth_callback)
        self.webview.auth_error.connect(self.on_auth_error)
        self.webview.urlChanged.connect(self.on_webview_url_changed)
        self.webview.loadStarted.connect(self.on_webview_load_started)
        self.webview.loadFinished.connect(self.on_webview_load_finished)
        
        layout.addWidget(self.webview)
        
        return panel
    
    def initiate_oauth(self, server_name: str, service_config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Initiate OAuth flow for a specific server.
        
        Args:
            server_name: Name of the MCP server requiring OAuth
            service_config: Optional custom OAuth service configuration
            
        Returns:
            True if flow was initiated successfully
        """
        try:
            self.server_name = server_name
            
            # Update UI
            self.server_label.setText(f"Server: {server_name}")
            self.title_label.setText(f"OAuth Authentication - {server_name}")
            
            # Try to initiate flow
            if service_config:
                # Use custom configuration
                flow = self.oauth_manager.initiate_custom_flow(
                    service_name=server_name,
                    client_id=service_config.get("client_id"),
                    client_secret=service_config.get("client_secret"),
                    auth_url=service_config.get("auth_url"),
                    token_url=service_config.get("token_url"),
                    scope=service_config.get("scope", [])
                )
            else:
                # Try to auto-detect service or use generic flow
                flow = self.oauth_manager.initiate_flow(server_name)
            
            self.current_flow = flow
            
            # Update UI with flow info
            self.provider_label.setText(f"Provider: {flow.service_name}")
            self.scope_label.setText(f"Scope: {', '.join(flow.scope)}")
            self.state_label.setText("State: Flow initiated")
            
            # Enable actions
            self.start_button.setEnabled(True)
            self.manual_code_button.setEnabled(True)
            
            logger.info(f"OAuth flow initiated for {server_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initiate OAuth flow for {server_name}: {e}")
            QMessageBox.critical(self, "OAuth Error", f"Failed to initiate OAuth flow:\n{e}")
            return False
    
    def start_oauth_flow(self):
        """Start the OAuth authentication in the webview."""
        if not self.current_flow:
            return
        
        # Load the authorization URL
        auth_url = self.current_flow.auth_url
        self.webview.load(QUrl(auth_url))
        
        # Update UI
        self.state_label.setText("State: Authenticating...")
        self.start_button.setEnabled(False)
        self.refresh_button.setEnabled(True)
        
        # Start timeout timer (5 minutes)
        self.timeout_timer.start(300000)
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        self.add_event(f"Started OAuth flow for {self.server_name}")
    
    def refresh_webview(self):
        """Refresh the webview."""
        self.webview.reload()
        self.add_event("Refreshed authentication page")
    
    def enter_manual_code(self):
        """Allow manual entry of authorization code."""
        # This would open a dialog for manual code entry
        # For now, just show a message
        QMessageBox.information(
            self, 
            "Manual Code Entry", 
            "Manual code entry is not yet implemented.\n"
            "Please complete the OAuth flow in the browser."
        )
    
    def on_webview_url_changed(self, url: QUrl):
        """Handle webview URL changes."""
        url_str = url.toString()
        self.url_label.setText(f"URL: {url_str[:80]}{'...' if len(url_str) > 80 else ''}")
    
    def on_webview_load_started(self):
        """Handle webview load start."""
        self.webview_status.setText("●")
        self.webview_status.setStyleSheet("color: orange; font-size: 16px;")
    
    def on_webview_load_finished(self, success: bool):
        """Handle webview load completion."""
        if success:
            self.webview_status.setText("●")
            self.webview_status.setStyleSheet("color: green; font-size: 16px;")
        else:
            self.webview_status.setText("●")
            self.webview_status.setStyleSheet("color: red; font-size: 16px;")
    
    def on_auth_callback(self, callback_url: str):
        """Handle OAuth callback from webview."""
        try:
            if not self.current_flow:
                return
            
            self.add_event(f"Received OAuth callback")
            self.state_label.setText("State: Processing callback...")
            
            # Complete the OAuth flow
            result = self.oauth_manager.complete_flow(self.current_flow, callback_url)
            
            if result.success:
                self.add_event(f"OAuth authentication successful")
                self.state_label.setText("State: Success!")
                
                # Stop timers and hide progress
                self.timeout_timer.stop()
                self.progress_bar.setVisible(False)
                
                # Emit success signal
                self.auth_completed.emit(self.server_name, result.token_data)
                
                # Show success message
                QMessageBox.information(
                    self, 
                    "Authentication Successful", 
                    f"Successfully authenticated with {self.server_name}!\n"
                    f"Access token expires: {result.expires_at}"
                )
                
                self.accept()  # Close dialog
                
            else:
                self.add_event(f"OAuth authentication failed: {result.error}")
                self.state_label.setText("State: Failed")
                self.on_auth_error(result.error or "Unknown error")
                
        except Exception as e:
            logger.error(f"OAuth callback processing failed: {e}")
            self.on_auth_error(f"Callback processing failed: {e}")
    
    def on_auth_error(self, error_message: str):
        """Handle OAuth authentication errors."""
        self.add_event(f"OAuth error: {error_message}")
        self.state_label.setText("State: Error")
        
        # Stop timers and hide progress
        self.timeout_timer.stop()
        self.progress_bar.setVisible(False)
        
        # Re-enable start button
        self.start_button.setEnabled(True)
        
        # Emit error signal
        self.auth_failed.emit(self.server_name, error_message)
        
        # Show error message
        QMessageBox.critical(
            self, 
            "Authentication Failed", 
            f"OAuth authentication failed:\n{error_message}"
        )
    
    def on_auth_timeout(self):
        """Handle authentication timeout."""
        self.timeout_timer.stop()
        self.on_auth_error("Authentication timeout - please try again")
    
    def update_status(self):
        """Update the status display."""
        if self.current_flow:
            # Update flow status if needed
            pass
    
    def add_event(self, message: str):
        """Add an event to the events list."""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        event_text = f"[{timestamp}] {message}"
        
        item = QListWidgetItem(event_text)
        self.events_list.insertItem(0, item)  # Add to top
        
        # Limit to 20 items
        while self.events_list.count() > 20:
            self.events_list.takeItem(self.events_list.count() - 1)
        
        logger.info(f"OAuth event: {message}")
    
    def closeEvent(self, event):
        """Handle dialog close."""
        if self.timeout_timer.isActive():
            self.timeout_timer.stop()
        
        if self.status_timer.isActive():
            self.status_timer.stop()
        
        super().closeEvent(event)


class OAuthNotificationWidget(QWidget):
    """Widget for showing OAuth-related notifications in the system tray."""
    
    oauth_requested = pyqtSignal(str)  # server_name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.auth_detector = AuthDetector()
        self.auth_detector.add_event_callback(self.on_auth_event)
        
        # Notification tracking
        self.pending_notifications: Dict[str, AuthEvent] = {}
    
    def on_auth_event(self, event: AuthEvent):
        """Handle authentication events for notifications."""
        if event.auth_requirement.value == "oauth":
            self.show_oauth_notification(event)
    
    def show_oauth_notification(self, event: AuthEvent):
        """Show OAuth authentication notification."""
        server_name = event.server_name
        
        # Store pending notification
        self.pending_notifications[server_name] = event
        
        # Emit signal for system tray to handle
        self.oauth_requested.emit(server_name)
    
    def clear_notification(self, server_name: str):
        """Clear notification for a server."""
        if server_name in self.pending_notifications:
            del self.pending_notifications[server_name]
    
    def get_pending_notifications(self) -> Dict[str, AuthEvent]:
        """Get all pending OAuth notifications."""
        return self.pending_notifications.copy()


def create_oauth_system_notification(server_name: str, oauth_url: Optional[str] = None) -> Dict[str, Any]:
    """Create a system notification for OAuth requirement."""
    title = f"OAuth Required - {server_name}"
    
    if oauth_url:
        message = f"Server '{server_name}' requires OAuth authentication.\nClick to authenticate."
    else:
        message = f"Server '{server_name}' requires OAuth authentication.\nPlease configure OAuth settings."
    
    return {
        "title": title,
        "message": message,
        "server_name": server_name,
        "oauth_url": oauth_url,
        "action": "oauth_authenticate"
    }