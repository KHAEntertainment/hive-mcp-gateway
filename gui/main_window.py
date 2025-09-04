"""Main window for Hive MCP Gateway GUI application."""

import logging
import json
import time
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QLabel, QPushButton, QTextEdit, QGroupBox,
    QGridLayout, QFormLayout, QScrollArea, QListWidget, QListWidgetItem,
    QProgressBar, QFrame, QMessageBox, QCheckBox, QLineEdit, QComboBox
)
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
import threading
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor

from .server_card import ServerCard
logger = logging.getLogger(__name__)


class StatusWidget(QWidget):
    """Widget for displaying service status information."""
    
    # Signal emitted when the user clicks the port save button
    port_save_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the status widget UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)  # Fixed: 4 arguments (left, top, right, bottom)
        
        # Notifications section
        notifications_group = QGroupBox("Notifications")
        notifications_group.setObjectName("notificationsGroup")
        notifications_layout = QVBoxLayout(notifications_group)
        notifications_layout.setContentsMargins(15, 15, 15, 15)  # Fixed: 4 arguments (left, top, right, bottom)
        
        # Notification toggle button
        self.notification_toggle = QPushButton("▼")
        self.notification_toggle.setObjectName("notificationToggle")
        self.notification_toggle.setCheckable(True)
        self.notification_toggle.setChecked(False)  # Start collapsed by default
        self.notification_toggle.clicked.connect(self.toggle_notifications)
        notifications_layout.addWidget(self.notification_toggle)
        
        # Notifications list
        self.notifications_scroll = QScrollArea()
        self.notifications_scroll.setObjectName("notificationsScroll")
        self.notifications_scroll.setWidgetResizable(True)
        self.notifications_container = QWidget()
        self.notifications_layout = QVBoxLayout(self.notifications_container)
        self.notifications_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.notifications_scroll.setWidget(self.notifications_container)
        notifications_layout.addWidget(self.notifications_scroll)
        self.notifications_scroll.setVisible(False)  # Hide by default
        
        # Add notification label when empty
        self.no_notifications_label = QLabel("No notifications")
        self.no_notifications_label.setObjectName("noNotificationsLabel")
        self.no_notifications_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_notifications_label.setStyleSheet("color: #a0a3a8; padding: 10px;")
        self.notifications_layout.addWidget(self.no_notifications_label)
        
        layout.addWidget(notifications_group)
        
        # Service status group (single-column, less cramped)
        status_group = QGroupBox("Service Status")
        status_group.setObjectName("serviceStatusGroup")
        status_layout = QFormLayout(status_group)
        status_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        status_layout.setVerticalSpacing(5)  # Reduce vertical spacing
        status_layout.setContentsMargins(10, 10, 10, 10)
        
        # Status row
        self.service_status_label = QLabel("Unknown")
        self.service_status_label.setObjectName("statusValue")
        status_layout.addRow("Status:", self.service_status_label)

        # Port configuration
        port_row = QHBoxLayout()
        self.port_input = QLineEdit("8001")  # Initialize with default value for now
        self.port_input.setObjectName("portInput")
        self.port_input.setFixedWidth(80)
        self.port_save_btn = QPushButton("Save")
        self.port_save_btn.setObjectName("portSaveButton")
        # Connect the button click to emit the signal
        self.port_save_btn.clicked.connect(self._on_port_save_clicked)
        port_row.addWidget(self.port_input)
        port_row.addWidget(self.port_save_btn)
        port_row.addStretch()
        status_layout.addRow("Port:", port_row)

        # Active API base + Refresh
        api_row = QHBoxLayout()
        self.api_base_label = QLabel("Unknown")
        self.api_base_label.setObjectName("apiBaseLabel")
        self.refresh_btn = QPushButton("Refresh Now")
        self.refresh_btn.setObjectName("refreshNowButton")
        self.reconnect_all_btn = QPushButton("Reconnect All")
        self.reconnect_all_btn.setObjectName("reconnectAllButton")
        # New: Discover All button
        self.discover_all_btn = QPushButton("Discover All")
        self.discover_all_btn.setObjectName("discoverAllButton")
        api_row.addWidget(self.api_base_label)
        api_row.addStretch()
        api_row.addWidget(self.discover_all_btn)
        api_row.addWidget(self.reconnect_all_btn)
        api_row.addWidget(self.refresh_btn)
        status_layout.addRow("API:", api_row)

        # Proxy status (read-only, always-on)
        proxy_row = QHBoxLayout()
        self.proxy_mode_label = QLabel("Managed: On")
        self.proxy_mode_label.setObjectName("proxyModeLabel")
        self.proxy_route_label = QLabel("Routing: stdio via proxy")
        self.proxy_route_label.setObjectName("proxyRouteLabel")
        self.proxy_status_label = QLabel("Unknown")
        self.proxy_status_label.setObjectName("proxyStatusLabel")
        # Helpful tooltips
        self.proxy_mode_label.setToolTip("Gateway manages the MCP Proxy automatically")
        self.proxy_route_label.setToolTip("Stdio servers are routed through the proxy for stability")
        self.proxy_status_label.setToolTip("Current proxy state and base URL")
        proxy_row.addWidget(self.proxy_mode_label)
        proxy_row.addSpacing(10)
        proxy_row.addWidget(self.proxy_route_label)
        proxy_row.addSpacing(10)
        proxy_row.addWidget(self.proxy_status_label)
        proxy_row.addStretch()
        status_layout.addRow("Proxy:", proxy_row)

        # Last refresh status
        self.last_refresh_label = QLabel("Not refreshed")
        self.last_refresh_label.setObjectName("lastRefreshLabel")
        status_layout.addRow("Last refresh:", self.last_refresh_label)
        
        # PID row
        self.service_pid_label = QLabel("Unknown")
        self.service_pid_label.setObjectName("statusValue")
        status_layout.addRow("PID:", self.service_pid_label)
        
        # Uptime row
        self.service_uptime_label = QLabel("Unknown")
        self.service_uptime_label.setObjectName("statusValue")
        status_layout.addRow("Uptime:", self.service_uptime_label)
        
        # Add service status to the main layout
        layout.addWidget(status_group)
        
        # MCP Servers
        servers_group = QGroupBox("Registered MCP Servers")
        servers_group.setObjectName("serverStatusGroup")
        servers_layout = QVBoxLayout(servers_group)
        
        # Use a scroll area for server cards
        self.servers_scroll = QScrollArea()
        self.servers_scroll.setObjectName("serverListScrollArea")
        self.servers_scroll.setWidgetResizable(True)
        self.servers_container = QWidget()
        self.servers_layout = QVBoxLayout(self.servers_container)
        self.servers_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.servers_scroll.setWidget(self.servers_container)
        servers_layout.addWidget(self.servers_scroll)
        
        # Set a larger minimum height for the servers section
        self.servers_scroll.setMinimumHeight(250)  # Make it taller to show multiple servers
        
        layout.addWidget(servers_group, 1)  # Give it a stretch factor of 1 to take more space
        
        layout.addStretch()
    
    def load_port_configuration(self, config_manager):
        """Load the port configuration from the config manager."""
        if config_manager:
            try:
                config = config_manager.load_config()
                port = config.tool_gating.port
                self.port_input.setText(str(port))
            except Exception as e:
                logger.error(f"Error loading port configuration: {e}")
                # Fallback to default port
                self.port_input.setText("8001")
        else:
            # Fallback to default port
            self.port_input.setText("8001")
    
    def toggle_notifications(self):
        """Toggle the visibility of the notifications list."""
        is_expanded = self.notification_toggle.isChecked()
        self.notifications_scroll.setVisible(is_expanded)
        self.notification_toggle.setText("▲" if is_expanded else "▼")
    
    def add_notification(self, notification_id: str, message: str, level: str = "info"):
        """Add a notification to the notifications panel."""
        # Import here to avoid circular imports
        from gui.notification_widget import NotificationWidget
        
        # Hide the "No notifications" label if it exists
        if hasattr(self, 'no_notifications_label'):
            self.no_notifications_label.setVisible(False)
        
        # Create a new notification widget
        notification = NotificationWidget(notification_id, message, level)
        notification.dismissed.connect(self.on_notification_dismissed)
        
        # Add it to the layout
        self.notifications_layout.insertWidget(0, notification)  # Add at the top
        
        # Update notification count and UI state
        self._update_notification_state()
        
        # Auto-expand notifications panel if it was empty before
        if self.notifications_layout.count() == 1 or (
            self.notifications_layout.count() == 2 and 
            not self.no_notifications_label.isVisible()
        ):
            self.notification_toggle.setChecked(True)
            self.notifications_scroll.setVisible(True)
            self.notification_toggle.setText("▲")
    
    def on_notification_dismissed(self, notification_id: str):
        """Handle notification dismissal."""
        # Update notification count and UI state
        self._update_notification_state()
    
    def _update_notification_state(self):
        """Update notification UI based on current notification count."""
        # Count actual notifications (excluding the no_notifications_label)
        notification_count = 0
        for i in range(self.notifications_layout.count()):
            item = self.notifications_layout.itemAt(i)
            if item and hasattr(item, 'widget'):
                widget = item.widget()
                if widget and widget != self.no_notifications_label:
                    notification_count += 1
        
        # Show/hide the no notifications label
        if hasattr(self, 'no_notifications_label'):
            self.no_notifications_label.setVisible(notification_count == 0)
        
        # Update button text to show notification count
        if notification_count > 0:
            self.notification_toggle.setText(
                f"▲ ({notification_count})" if self.notification_toggle.isChecked() else f"▼ ({notification_count})"
            )
        else:
            self.notification_toggle.setText(
                "▲" if self.notification_toggle.isChecked() else "▼"
            )
            # Auto-collapse if there are no notifications
            if self.notification_toggle.isChecked():
                self.notification_toggle.setChecked(False)
                self.notifications_scroll.setVisible(False)

    def _on_port_save_clicked(self):
        """Internal method called when the port save button is clicked."""
        # Emit the signal to notify the main window
        self.port_save_requested.emit()
    
    def save_port_configuration(self):
        """Placeholder method. Actual saving is handled by the main window."""
        pass


class LogsWidget(QWidget):
    """Widget for displaying service logs."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the logs widget UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Logs display
        logs_label = QLabel("Service Logs:")
        logs_label.setObjectName("sectionLabel")
        layout.addWidget(logs_label)
        
        self.logs_text = QTextEdit()
        self.logs_text.setObjectName("logsView")
        self.logs_text.setReadOnly(True)
        self.logs_text.setFont(QFont("JetBrains Mono", 10))
        self.logs_text.setPlaceholderText("Service logs will appear here...")
        
        layout.addWidget(self.logs_text)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.clear_logs_btn = QPushButton("Clear Logs")
        self.clear_logs_btn.setObjectName("clearLogsButton")
        controls_layout.addWidget(self.clear_logs_btn)
        
        self.refresh_logs_btn = QPushButton("Refresh Logs")
        self.refresh_logs_btn.setObjectName("refreshLogsButton")
        controls_layout.addWidget(self.refresh_logs_btn)
        
        self.save_logs_btn = QPushButton("Save Logs...")
        self.save_logs_btn.setObjectName("saveLogsButton")
        controls_layout.addWidget(self.save_logs_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)


class AboutWidget(QWidget):
    """Widget for displaying about information."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the about widget UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Add banner logo
        banner_label = QLabel()
        banner_label.setObjectName("bannerLabel")
        banner_pixmap = QPixmap("gui/assets/hive_banner.png")  # Will be replaced with actual banner
        if not banner_pixmap.isNull():
            # Resize the banner to fit appropriately
            banner_pixmap = banner_pixmap.scaledToWidth(400, Qt.TransformationMode.SmoothTransformation)
        banner_label.setPixmap(banner_pixmap)
        banner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(banner_label)
        
        about_text = QLabel("""
        <h2>Hive MCP Gateway</h2>
        <p><strong>Version:</strong> 0.2.0</p>
        <p><strong>Description:</strong> Intelligent proxy for Model Context Protocol (MCP)</p>
        
        <h3>Features:</h>
        <ul>
            <li>Dynamic tool discovery and provisioning</li>
            <li>Smart semantic search for relevant tools</li>
            <li>Token budget management</li>
            <li>Multiple MCP server integration</li>
            <li>Real-time configuration updates</li>
            <li>Secure credential management</li>
        </ul>
        
        <h3>Configuration:</h>
        <p>The service runs on port 8001 to avoid conflicts with development instances.</p>
        <p>Access configuration through the menubar icon or this main window.</p>
        
        <h3>Support:</h3>
        <p>For issues and documentation, visit the project repository.</p>
        """)
        
        about_text.setObjectName("aboutText")
        about_text.setWordWrap(True)
        about_text.setOpenExternalLinks(True)
        about_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Wrap about text in a scroll area
        about_scroll = QScrollArea()
        about_scroll.setObjectName("aboutScrollArea")
        about_scroll.setWidgetResizable(True)
        about_scroll.setWidget(about_text)
        layout.addWidget(about_scroll)

        # Dependencies moved here to declutter Status tab
        deps_group = QGroupBox("Dependencies")
        deps_group.setObjectName("dependenciesGroup")
        deps_layout = QVBoxLayout(deps_group)
        deps_layout.setContentsMargins(10, 10, 10, 10)
        deps_layout.setSpacing(5)
        
        self.deps_list = QListWidget()
        self.deps_list.setObjectName("depsList")
        self.deps_list.setMaximumHeight(180)
        deps_layout.addWidget(self.deps_list)
        layout.addWidget(deps_group)


class MainWindow(QMainWindow):
    """Main application window (typically hidden for menubar app)."""
    
    # Signals for navigation actions
    show_snippet_processor_requested = pyqtSignal()
    show_credentials_manager_requested = pyqtSignal()
    show_llm_config_requested = pyqtSignal()
    show_autostart_settings_requested = pyqtSignal()
    show_client_config_requested = pyqtSignal()
    server_edit_requested = pyqtSignal(str, str)  # server_id, json_config
    
    def __init__(self, config_manager=None, service_manager=None, 
                 dependency_checker=None, migration_utility=None, 
                 autostart_manager=None, notification_manager=None, parent=None):
        """Initialize main window."""
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.service_manager = service_manager
        self.dependency_checker = dependency_checker
        self.migration_utility = migration_utility
        self.autostart_manager = autostart_manager
        self.notification_manager = notification_manager
        
        self.setWindowTitle("Hive MCP Gateway")
        self.setGeometry(100, 100, 900, 700)
        
        # Apply Hive Night theme
        self.load_stylesheet()
        
        self.setup_ui()
        self.setup_connections()
        self.update_status_display()
        
        # Load port configuration
        self.load_port_configuration()
        
        # Update server tool counts once at startup
        # This is done with a slight delay to ensure the UI is fully loaded
        QTimer.singleShot(2000, self.update_all_server_tool_counts)
    
    def show_status_message(self, message: str):
        """Safely show a message in the status bar."""
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage(message)
    
    def load_stylesheet(self):
        """Load and apply the Hive Night theme stylesheet."""
        stylesheet_path = "gui/assets/styles.qss"
        try:
            with open(stylesheet_path, "r") as f:
                stylesheet = f.read()
                self.setStyleSheet(stylesheet)
        except FileNotFoundError:
            logger.warning(f"Stylesheet not found at {stylesheet_path}")
        except Exception as e:
            logger.error(f"Error loading stylesheet: {e}")
    
    def setup_ui(self):
        """Setup the main application UI."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header Bar
        header_widget = QWidget()
        header_widget.setObjectName("headerBar")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        title = QLabel("Hive MCP Gateway Control Center")
        title.setObjectName("headerTitle")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Service control buttons in header
        self.start_btn = QPushButton("Start Service")
        self.start_btn.setObjectName("startButton")
        
        self.stop_btn = QPushButton("Stop Service")
        self.stop_btn.setObjectName("stopButton")
        
        self.restart_btn = QPushButton("Restart Service")
        self.restart_btn.setObjectName("restartButton")
        
        header_layout.addWidget(self.start_btn)
        header_layout.addWidget(self.stop_btn)
        header_layout.addWidget(self.restart_btn)
        
        layout.addWidget(header_widget)
        
        # Navigation buttons section
        nav_group = QGroupBox("Quick Actions")
        nav_group.setObjectName("quickActionsGroup")
        nav_layout = QHBoxLayout(nav_group)
        nav_layout.setSpacing(10)
        
        # Configuration navigation buttons
        self.add_server_btn = QPushButton("🔧 Add MCP Server")
        self.add_server_btn.setObjectName("addServerButton")
        self.add_server_btn.setToolTip("Open JSON snippet processor to add a new MCP server")
        
        self.credentials_btn = QPushButton("🔐 Manage Credentials")
        self.credentials_btn.setObjectName("secretsButton")
        self.credentials_btn.setToolTip("Open credentials manager for API keys and secrets")
        
        import os
        self.llm_config_btn = QPushButton("🤖 LLM Configuration")
        self.llm_config_btn.setObjectName("llmConfigButton")
        self.llm_config_btn.setToolTip("Configure external LLM providers (OpenAI, Anthropic, etc.)")
        
        self.autostart_btn = QPushButton("⚙️ Auto-Start Settings")
        self.autostart_btn.setObjectName("autoStartButton")
        self.autostart_btn.setToolTip("Configure automatic startup with macOS")
        
        self.client_config_btn = QPushButton("🔌 Client Configuration")
        self.client_config_btn.setObjectName("clientConfigButton")
        self.client_config_btn.setToolTip("Configure MCP clients to connect to Hive MCP Gateway")
        
        nav_layout.addWidget(self.add_server_btn)
        nav_layout.addWidget(self.credentials_btn)
        # Feature flag: hide LLM configuration by default until re-enabled
        # Enable by setting env var HMG_ENABLE_LLM_UI=1
        enable_llm_ui = os.getenv("HMG_ENABLE_LLM_UI", "0") not in (None, "", "0", "false", "False")
        if not enable_llm_ui:
            self.llm_config_btn.setVisible(False)

        nav_layout.addWidget(self.llm_config_btn)
        nav_layout.addWidget(self.autostart_btn)
        nav_layout.addWidget(self.client_config_btn)
        nav_layout.addStretch()
        
        layout.addWidget(nav_group)
        
        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setObjectName("separatorLine")
        layout.addWidget(line)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("mainTabWidget")
        
        # Set tab bar object name
        if self.tab_widget and hasattr(self.tab_widget, 'tabBar'):
            tab_bar = self.tab_widget.tabBar()
            if tab_bar:
                tab_bar.setObjectName("mainTabBar")
        
        # Create tabs
        self.status_widget = StatusWidget()
        self.logs_widget = LogsWidget()
        self.about_widget = AboutWidget()
        
        # Import and create MCP Clients widget
        from gui.mcp_clients_widget import MCPClientsWidget
        self.mcp_clients_widget = MCPClientsWidget()
        
        self.tab_widget.addTab(self.status_widget, "📊 Status")
        self.tab_widget.addTab(self.mcp_clients_widget, "🔌 MCP Clients")
        self.tab_widget.addTab(self.logs_widget, "📝 Logs")
        self.tab_widget.addTab(self.about_widget, "ℹ️ About")
        
        layout.addWidget(self.tab_widget)
        
        # Status bar
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("Ready - Hive MCP Gateway Control Center")
    
    def setup_connections(self):
        """Setup signal connections."""
        if self.service_manager:
            self.start_btn.clicked.connect(self.start_service)
            self.stop_btn.clicked.connect(self.stop_service)
            self.restart_btn.clicked.connect(self.restart_service)
            
            # Connect to service manager signals if available
            try:
                self.service_manager.status_changed.connect(self.on_service_status_changed)
                self.service_manager.log_message.connect(self.add_log_message)
            except AttributeError:
                # Service manager might not have these signals yet
                pass
        
        # Connect log controls
        self.logs_widget.clear_logs_btn.clicked.connect(self.clear_logs)
        self.logs_widget.refresh_logs_btn.clicked.connect(self.refresh_logs)
        self.logs_widget.save_logs_btn.clicked.connect(self.save_logs)
        
        # Connect navigation buttons
        self.add_server_btn.clicked.connect(self.show_snippet_processor)
        self.credentials_btn.clicked.connect(self.show_credentials_manager)
        self.llm_config_btn.clicked.connect(self.show_llm_config)
        self.autostart_btn.clicked.connect(self.show_autostart_settings)
        self.client_config_btn.clicked.connect(self.show_client_config)
        
        # Connect port configuration signal
        self.status_widget.port_save_requested.connect(self.save_port_configuration)
        # Manual refresh button to force an immediate fetch of server statuses
        try:
            self.status_widget.refresh_btn.clicked.connect(self.update_all_server_tool_counts)
        except Exception:
            pass
        # Reconnect all servers
        try:
            self.status_widget.reconnect_all_btn.clicked.connect(self.reconnect_all_servers)
        except Exception:
            pass
        # Discover all servers' tools
        try:
            self.status_widget.discover_all_btn.clicked.connect(self.discover_all_servers)
        except Exception:
            pass
        
        # Status update timer - Temporary disable automatic status updates
        # to prevent the feedback loop we're seeing
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_service_info_only)
        self.status_timer.start(10000)  # Update every 10 seconds

        # Initialize proxy status text
        try:
            if self.config_manager:
                cfg = self.config_manager.load_config()
                managed = getattr(cfg.tool_gating, 'manage_proxy', True)
                auto_stdio = getattr(cfg.tool_gating, 'auto_proxy_stdio', True)
                if hasattr(self.status_widget, 'proxy_mode_label'):
                    self.status_widget.proxy_mode_label.setText(f"Managed: {'On' if managed else 'Off'}")
                if hasattr(self.status_widget, 'proxy_route_label'):
                    route = 'stdio via proxy' if auto_stdio else 'direct stdio'
                    self.status_widget.proxy_route_label.setText(f"Routing: {route}")
                QTimer.singleShot(300, self.update_proxy_status)
        except Exception:
            pass

        # Proxy status poller
        self.proxy_timer = QTimer()
        self.proxy_timer.timeout.connect(self.update_proxy_status)
        self.proxy_timer.start(12000)
    
    def update_service_info_only(self):
        """Update only the service information, not the servers."""
        if self.service_manager:
            try:
                status = self.service_manager.get_service_status()
                
                if hasattr(status, 'pid') and status.pid:
                    self.status_widget.service_pid_label.setText(str(status.pid))
                else:
                    self.status_widget.service_pid_label.setText("Unknown")
                
                if hasattr(status, 'is_running'):
                    status_text = "Running" if status.is_running else "Stopped"
                    self.status_widget.service_status_label.setText(status_text)
                    
            except Exception as e:
                logger.debug(f"Error updating status: {e}")
        
        # Update dependencies list only
        self.update_dependencies_display()
        
        # Update tool counts without triggering server status updates
        # We do this occasionally to keep tool counts current
        QTimer.singleShot(100, self.update_all_server_tool_counts)
    
    def start_service(self):
        """Start the service."""
        if self.service_manager:
            try:
                success = self.service_manager.start_service()
                if success:
                    self.show_status_message("Service started successfully")
                else:
                    self.show_status_message("Failed to start service")
            except Exception as e:
                self.show_status_message(f"Error starting service: {e}")
        else:
            self.show_status_message("Service manager not available")
    
    def stop_service(self):
        """Stop the service."""
        if self.service_manager:
            try:
                success = self.service_manager.stop_service()
                if success:
                    self.show_status_message("Service stopped")
                else:
                    self.show_status_message("Failed to stop service")
            except Exception as e:
                self.show_status_message(f"Error stopping service: {e}")
        else:
            self.show_status_message("Service manager not available")
    
    def restart_service(self):
        """Restart the service."""
        if self.service_manager:
            try:
                success = self.service_manager.restart_service()
                if success:
                    self.show_status_message("Service restarted successfully")
                else:
                    self.show_status_message("Failed to restart service")
            except Exception as e:
                self.show_status_message(f"Error restarting service: {e}")
        else:
            self.show_status_message("Service manager not available")
    
    def on_service_status_changed(self, status: str):
        """Handle service status changes."""
        self.status_widget.service_status_label.setText(status.title())
        
        # Update button states
        if status == "running":
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(True)
            # When the backend comes up, refresh servers and counts shortly after
            try:
                # Rebuild display to attach cards, then update counts
                QTimer.singleShot(200, self.update_servers_display)
                QTimer.singleShot(800, self.update_all_server_tool_counts)
                # Reflect the active detected port in the UI field
                if self.service_manager and self.status_widget and hasattr(self.status_widget, 'port_input'):
                    try:
                        active_port = getattr(self.service_manager, 'tool_gating_port', None)
                        if active_port:
                            self.status_widget.port_input.setText(str(active_port))
                    except Exception:
                        pass
            except Exception:
                # Best-effort; ignore if timer not available yet
                pass
        else:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.restart_btn.setEnabled(False)
        
        self.show_status_message(f"Service status: {status}")
    
    def update_status_display(self):
        """Update the status display with current information."""
        if self.service_manager:
            try:
                status = self.service_manager.get_service_status()
                
                if hasattr(status, 'pid') and status.pid:
                    self.status_widget.service_pid_label.setText(str(status.pid))
                else:
                    self.status_widget.service_pid_label.setText("Unknown")
                
                if hasattr(status, 'is_running'):
                    status_text = "Running" if status.is_running else "Stopped"
                    self.status_widget.service_status_label.setText(status_text)
                    
            except Exception as e:
                logger.debug(f"Error updating status: {e}")
        
        # Update dependencies list - exclude Claude Desktop as it's a client, not a dependency
        self.update_dependencies_display()
        
        # Update MCP servers list
        self.update_servers_display()
    
    def update_dependencies_display(self):
        """Update the dependencies status display (now on About tab)."""
        if not hasattr(self.about_widget, 'deps_list'):
            return
        self.about_widget.deps_list.clear()
        
        if self.dependency_checker:
            # Use the new method to get only actual dependencies (excluding clients)
            actual_dependencies = self.dependency_checker.get_actual_dependencies()
            
            for dep_name, dep_info in actual_dependencies.items():
                # Determine availability from stored info
                is_available = dep_info.is_running if dep_info else False
                
                if is_available:
                    status_icon = "✅"
                    status_text = "Available"
                    if dep_info and dep_info.version:
                        status_text += f" ({dep_info.version})"
                else:
                    status_icon = "⚠️"
                    status_text = "Not detected"
                    if dep_info and dep_info.error_message:
                        status_text += f" - {dep_info.error_message}"
                
                # Format dependency name for display
                display_name = dep_name.replace("_", " ").replace("-", " ").title()
                item_text = f"{display_name}: {status_icon} {status_text}"
                
                item = QListWidgetItem(item_text)
                
                # Color code items
                if is_available:
                    item.setForeground(QColor(76, 175, 80))  # Green
                else:
                    item.setForeground(QColor(255, 152, 0))  # Orange
                
                self.about_widget.deps_list.addItem(item)
        else:
            # Fallback if dependency checker not available
            fallback_deps = [
                ("Python 3.12+", "✅ Available"),
                ("Dependency Checker", "⚠️ Not initialized")
            ]
            
            for name, status in fallback_deps:
                item = QListWidgetItem(f"{name}: {status}")
                self.about_widget.deps_list.addItem(item)
    
    def update_servers_display(self):
        """Update the MCP servers list with server cards."""
        # Store existing server cards by ID for possible reuse
        existing_server_cards = {}
        
        # Clear existing server cards
        if self.status_widget and hasattr(self.status_widget, 'servers_layout'):
            servers_layout = self.status_widget.servers_layout
            if servers_layout and hasattr(servers_layout, 'count') and hasattr(servers_layout, 'itemAt'):
                for i in reversed(range(servers_layout.count())):
                    item = servers_layout.itemAt(i)
                    if item and hasattr(item, 'widget'):
                        widget = item.widget()
                        # Import ServerCard here to avoid circular imports if not already imported
                        from gui.server_card import ServerCard
                        if widget and isinstance(widget, ServerCard):  # Check if it's a ServerCard instance
                            # Store the widget for reuse
                            existing_server_cards[widget.server_id] = widget
                            # Remove from layout but don't delete yet
                            widget.setParent(None)
        
        # Get actual servers from config
        servers = []
        if self.config_manager:
            try:
                backend_servers = self.config_manager.get_backend_servers()
                # Import ServerCard here to avoid circular imports
                from gui.server_card import ServerCard
                
                # Get server statuses from the service if it's running
                server_statuses = {}
                if self.service_manager:
                    try:
                        server_status_list = self.service_manager.get_server_statuses()
                        # Convert list to dict for easier lookup
                        server_statuses = {status["name"]: status for status in server_status_list}
                    except Exception as e:
                        logger.error(f"Error getting server statuses: {e}")
                
                for server_id, server_config in backend_servers.items():
                    # Use server_id as the name to show the actual server name
                    name = server_id
                    description = server_config.description or ""
                    
                    # Get tool count and status from server status if available, otherwise use defaults
                    if server_id in server_statuses:
                        server_status = server_statuses[server_id]
                        tools_count = server_status.get("tool_count", 0)
                        error_message = server_status.get("error_message")
                        # Determine status based on connected and enabled flags
                        if server_status.get("connected", False):
                            status = "connected"
                        elif server_status.get("enabled", False):
                            status = "disconnected"
                        else:
                            status = "disabled"
                    else:
                        # Fallback to config values
                        tools_count = 0  # Default to 0 if not found in status
                        status = "connected" if server_config.enabled else "disabled"
                    
                    # Create or reuse server card
                    if server_id in existing_server_cards:
                        # Reuse existing card
                        server_card = existing_server_cards[server_id]
                        # Update its properties
                        server_card.set_status(status)
                        server_card.set_tool_count(tools_count)
                        try:
                            # Update visible error line if available
                            if 'error_message' in server_status:
                                server_card.set_error_message(server_status.get('error_message'))
                        except Exception:
                            pass
                        # Remove from existing_server_cards to mark as used
                        del existing_server_cards[server_id]
                    else:
                        # Create new card
                        server_card = ServerCard(server_id, name, tools_count, status)
                        # Set tooltip to description and any error message
                        tooltip_parts = []
                        if description:
                            tooltip_parts.append(description)
                        if server_id in server_statuses:
                            err = server_statuses[server_id].get("error_message")
                            if err:
                                tooltip_parts.append(f"Error: {err}")
                        if tooltip_parts:
                            server_card.setToolTip("\n".join(tooltip_parts))
                        # Visible error line
                        try:
                            if server_id in server_statuses:
                                err = server_statuses[server_id].get("error_message")
                                server_card.set_error_message(err)
                        except Exception:
                            pass
                        server_card.edit_requested.connect(self.edit_server)
                        server_card.delete_requested.connect(self.delete_server)
                        server_card.restart_requested.connect(self.restart_server)
                        server_card.discover_requested.connect(self.discover_server_tools)
                        server_card.toggle_requested.connect(self.toggle_server)
                    
                    self.status_widget.servers_layout.addWidget(server_card)
            except Exception as e:
                logger.error(f"Error loading servers: {e}")
        else:
            # Fallback to example servers if no config manager
            # Import ServerCard here to avoid circular imports
            from gui.server_card import ServerCard
            
            # Add some example servers with actual server IDs as names
            servers = [
                ("documentation_search", "Documentation search and library information", 7, "connected"),
                ("key_value_memory", "Simple key-value memory storage", 12, "connected"),
                ("browser_automation", "Browser automation and web scraping - High tool count server", 8, "connected"),
                ("web_search", "Web search, research, and social media tools - High tool count server with 100+ tools", 114, "connected"),
                ("ref", "Ref", 5, "connected")
            ]
            
            for server_id, description, tools_count, status in servers:
                server_card = ServerCard(server_id, server_id, tools_count, status)
                # Set tooltip to description
                server_card.setToolTip(description)
                server_card.edit_requested.connect(self.edit_server)
                server_card.delete_requested.connect(self.delete_server)
                server_card.restart_requested.connect(self.restart_server)
                server_card.toggle_requested.connect(self.toggle_server)
                self.status_widget.servers_layout.addWidget(server_card)
        
        # Clean up any unused server cards
        for card in existing_server_cards.values():
            card.deleteLater()
    
    def add_log_message(self, message: str):
        """Add a log message to the logs display."""
        self.logs_widget.logs_text.append(message)
        
        # Auto-scroll to bottom
        cursor = self.logs_widget.logs_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.logs_widget.logs_text.setTextCursor(cursor)
    
    def clear_logs(self):
        """Clear the logs display."""
        self.logs_widget.logs_text.clear()
        self.show_status_message("Logs cleared")
    
    def refresh_logs(self):
        """Refresh the logs display."""
        if self.service_manager:
            try:
                logs = self.service_manager.get_service_logs(100)
                self.logs_widget.logs_text.clear()
                for log_line in logs:
                    if log_line.strip():
                        self.logs_widget.logs_text.append(log_line)
                self.show_status_message("Logs refreshed")
            except Exception as e:
                self.add_log_message(f"Error refreshing logs: {e}")
        else:
            self.add_log_message("Service manager not available for log retrieval")
    
    def save_logs(self):
        """Save logs to file."""
        # TODO: Implement save logs functionality
        self.show_status_message("Save logs functionality not yet implemented")
    
    def show_snippet_processor(self):
        """Request to show the JSON snippet processor."""
        self.show_snippet_processor_requested.emit()
        self.show_status_message("Opening MCP Server Configuration...")
    
    def show_credentials_manager(self):
        """Request to show the credentials manager."""
        self.show_credentials_manager_requested.emit()
        self.show_status_message("Opening Credentials Manager...")
    
    def show_llm_config(self):
        """Request to show the LLM configuration."""
        self.show_llm_config_requested.emit()
        self.show_status_message("Opening LLM Configuration...")
    
    def show_autostart_settings(self):
        """Show auto-start settings dialog."""
        try:
            if self.autostart_manager:
                # Check current autostart status
                is_enabled = self.autostart_manager.is_auto_start_enabled()
                
                if is_enabled:
                    reply = QMessageBox.question(
                        self, 
                        "Auto-Start Settings",
                        "Auto-start is currently ENABLED.\n\nDo you want to disable it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        success = self.autostart_manager.disable_auto_start()
                        if success:
                            self.show_status_message("Auto-start disabled")
                            QMessageBox.information(self, "Success", "Auto-start has been disabled")
                        else:
                            self.show_status_message("Failed to disable auto-start")
                            QMessageBox.warning(self, "Error", "Failed to disable auto-start")
                else:
                    reply = QMessageBox.question(
                        self, 
                        "Auto-Start Settings",
                        "Auto-start is currently DISABLED.\n\nDo you want to enable it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        success = self.autostart_manager.enable_auto_start()
                        if success:
                            self.show_status_message("Auto-start enabled")
                            QMessageBox.information(self, "Success", "Auto-start has been enabled")
                        else:
                            self.show_status_message("Failed to enable auto-start")
                            QMessageBox.warning(self, "Error", "Failed to enable auto-start")
            else:
                QMessageBox.warning(self, "Error", "Auto-start manager not available")
                
        except Exception as e:
            self.show_status_message(f"Error with auto-start settings: {e}")
            QMessageBox.critical(self, "Error", f"Error accessing auto-start settings: {e}")
    
    def show_client_config(self):
        """Show client configuration window."""
        # Emit signal to show the client configuration window
        self.show_client_config_requested.emit()
        self.show_status_message("Opening Client Configuration...")
    
    def save_port_configuration(self):
        """Save the port configuration."""
        # Get the port from the input field
        port_text = self.status_widget.port_input.text()
        
        # Validate the port
        try:
            port = int(port_text)
            if port < 1 or port > 65535:
                raise ValueError("Port must be between 1 and 65535")
        except ValueError as e:
            self.show_status_message(f"Invalid port: {e}")
            return
        
        if self.config_manager:
            self.config_manager.set_port(port)
            self.show_status_message(f"Port configuration saved: {port}. Please restart the service for changes to take effect.")
            QMessageBox.information(self, "Port Configuration", f"Port saved to {port}. A restart is required.")
        else:
            self.show_status_message("Configuration manager not available")
    
    def edit_server(self, server_id: str):
        """Edit a server configuration."""
        # Get the server configuration
        try:
            if not self.config_manager:
                self.show_status_message("Configuration manager not available")
                return
                
            backend_servers = self.config_manager.get_backend_servers()
            if server_id not in backend_servers:
                self.show_status_message(f"Server {server_id} not found")
                return
                
            server_config = backend_servers[server_id]
            
            # Create a JSON representation of the server configuration
            server_json = {
                "mcpServers": {
                    server_id: server_config.dict(by_alias=True, exclude_unset=False)
                }
            }
            
            # Show the snippet processor with pre-filled values
            self.show_snippet_processor_requested.emit()
            
            # We need to find the snippet processor window and set values
            # This is done in main_app.py when handling the signal
            # But we can set up a temporary connection to set the values
            
            # Emit the server_edit_requested signal with server_id and config
            if hasattr(self, 'server_edit_requested'):
                self.server_edit_requested.emit(server_id, json.dumps(server_json, indent=2))
            
            self.show_status_message(f"Editing server: {server_id}")
            
        except Exception as e:
            self.show_status_message(f"Error editing server: {e}")
            logger.error(f"Error editing server {server_id}: {e}")
    
    def delete_server(self, server_id: str):
        """Delete a server configuration."""
        try:
            if not self.config_manager:
                self.show_status_message("Configuration manager not available")
                return
                
            # Ask for confirmation before deleting
            reply = QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Are you sure you want to delete the server '{server_id}'?\n\nThis action cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Remove the server from the configuration
                success = self.config_manager.remove_backend_server(server_id)
                
                if success:
                    self.show_status_message(f"Server {server_id} deleted successfully")
                    
                    # Update the server display
                    self.update_servers_display()
                    
                    # Add a notification
                    if hasattr(self.status_widget, 'add_notification'):
                        self.status_widget.add_notification(
                            f"server_deleted_{server_id}",
                            f"Server '{server_id}' has been deleted",
                            "info"
                        )
                else:
                    self.show_status_message(f"Failed to delete server {server_id}")
            else:
                self.show_status_message(f"Deletion of server {server_id} cancelled")
                
        except Exception as e:
            self.show_status_message(f"Error deleting server: {e}")
            logger.error(f"Error deleting server {server_id}: {e}")
    
    def restart_server(self, server_id: str):
        """Restart a server."""
        try:
            if not self.config_manager or not self.service_manager:
                self.show_status_message("Configuration or service manager not available")
                return
                
            backend_servers = self.config_manager.get_backend_servers()
            if server_id not in backend_servers:
                self.show_status_message(f"Server {server_id} not found")
                return
                
            # Attempt to restart the server through the service manager
            if hasattr(self.service_manager, 'restart_backend_server'):
                success = self.service_manager.restart_backend_server(server_id)
                
                if success:
                    self.show_status_message(f"Server {server_id} restarted successfully")
                    
                    # Update the specific server card
                    server_config = backend_servers[server_id]
                    self._update_specific_server_card(server_id, server_config.enabled)
                    
                    # Add a notification
                    if hasattr(self.status_widget, 'add_notification'):
                        self.status_widget.add_notification(
                            f"server_restarted_{server_id}_{int(time.time())}",  # Add timestamp to make ID unique
                            f"Server '{server_id}' has been restarted",
                            "info"
                        )
                else:
                    self.show_status_message(f"Failed to restart server {server_id}")
                    
                    # Add an error notification
                    if hasattr(self.status_widget, 'add_notification'):
                        self.status_widget.add_notification(
                            f"server_restart_failed_{server_id}_{int(time.time())}",  # Add timestamp to make ID unique
                            f"Failed to restart server '{server_id}'",
                            "error"
                        )
            else:
                # Fallback if restart_backend_server is not available
                self.show_status_message(f"Restarting server {server_id} (not implemented in service manager)")
                
                # Add a warning notification
                if hasattr(self.status_widget, 'add_notification'):
                    self.status_widget.add_notification(
                        f"server_restart_not_implemented_{server_id}_{int(time.time())}",  # Add timestamp to make ID unique
                        f"Restart functionality not implemented for server '{server_id}'",
                        "warning"
                    )
                
        except Exception as e:
            self.show_status_message(f"Error restarting server: {e}")
            logger.error(f"Error restarting server {server_id}: {e}")

    def reconnect_all_servers(self):
        """Reconnect all backend servers without blocking the UI, then refresh UI."""
        if not self.service_manager:
            self.show_status_message("Service manager not available")
            return
        self.show_status_message("Reconnecting all servers…")

        def _task():
            try:
                ok_local = self.service_manager.reconnect_all_servers()
            except Exception as e:
                ok_local = False
                err = str(e)
                QTimer.singleShot(0, lambda: self.show_status_message(f"Reconnect error: {err}"))
            else:
                msg = "Reconnect initiated for all servers" if ok_local else "Reconnect failed or no servers found"
                QTimer.singleShot(0, lambda: self.show_status_message(msg))
            finally:
                QTimer.singleShot(500, self.update_all_server_tool_counts)

        threading.Thread(target=_task, daemon=True).start()
    
    def toggle_server(self, server_id: str, enabled: bool):
        """Toggle a server on/off."""
        try:
            if not self.config_manager:
                self.show_status_message("Configuration manager not available")
                return
                
            backend_servers = self.config_manager.get_backend_servers()
            if server_id not in backend_servers:
                self.show_status_message(f"Server {server_id} not found")
                return
            
            # Debug information to help diagnose the issue
            server_config = backend_servers[server_id]
            logger.debug(f"Before toggle: Server {server_id} enabled={server_config.enabled}, requested={enabled}")
            
            # Special handling for the context7 server that won't stay disabled
            if server_id == "context7" and not enabled:
                # Double-check by forcefully disabling both in the backend and UI
                success = self.config_manager.enable_server(server_id, False)
                
                if success:
                    # Forcefully update the UI
                    self.show_status_message(f"Server {server_id} disabled successfully (forced)")
                    
                    # Update the specific server card
                    self._force_disable_server_card(server_id)
                    
                    # Add a notification with unique ID
                    if hasattr(self.status_widget, 'add_notification'):
                        self.status_widget.add_notification(
                            f"server_toggled_{server_id}_{int(time.time())}",
                            f"Server '{server_id}' has been disabled (forced)",
                            "info"
                        )
                    return
            
            # Check if the current state already matches the requested state
            # This prevents toggling back and forth repeatedly
            if server_config.enabled == enabled:
                logger.debug(f"Server {server_id} already in requested state (enabled={enabled})")
                return
                
            # Update the server's enabled status
            success = self.config_manager.enable_server(server_id, enabled)
            
            if success:
                status = "enabled" if enabled else "disabled"
                self.show_status_message(f"Server {server_id} {status} successfully")
                logger.debug(f"After toggle: Server {server_id} {status}")
                
                # Instead of updating all servers, find and update just the specific server card
                self._update_specific_server_card(server_id, enabled)
                
                # Add a notification only for user-initiated actions
                if hasattr(self.status_widget, 'add_notification'):
                    self.status_widget.add_notification(
                        f"server_toggled_{server_id}_{int(time.time())}",  # Add timestamp to make ID unique
                        f"Server '{server_id}' has been {status}",
                        "info"
                    )
            else:
                self.show_status_message(f"Failed to {('enable' if enabled else 'disable')} server {server_id}")
                
                # Add an error notification
                if hasattr(self.status_widget, 'add_notification'):
                    self.status_widget.add_notification(
                        f"server_toggle_failed_{server_id}_{int(time.time())}",  # Add timestamp to make ID unique
                        f"Failed to {('enable' if enabled else 'disable')} server '{server_id}'",
                        "error"
                    )
                
        except Exception as e:
            self.show_status_message(f"Error toggling server: {e}")
            logger.error(f"Error toggling server {server_id}: {e}")
    
    def _force_disable_server_card(self, server_id: str):
        """Force a server card to disabled state, bypassing normal update mechanisms."""
        try:
            # Import here to avoid circular imports and ensure symbol availability
            from gui.server_card import ServerCard
            # Find the specific server card widget and update it directly
            if (self.status_widget and hasattr(self.status_widget, 'servers_layout') and 
                hasattr(self.status_widget.servers_layout, 'count') and 
                hasattr(self.status_widget.servers_layout, 'itemAt')):
                
                for i in range(self.status_widget.servers_layout.count()):
                    item = self.status_widget.servers_layout.itemAt(i)
                    if item and hasattr(item, 'widget'):
                        widget = item.widget()
                        if widget and isinstance(widget, ServerCard) and widget.server_id == server_id:
                            # Found the server card, force it to disabled state
                            widget.toggle_switch.blockSignals(True)
                            widget.toggle_switch.setChecked(False)
                            widget.toggle_switch.blockSignals(False)
                            
                            # Force the status to disabled
                            widget.status = "disabled"
                            
                            # Update the UI
                            widget.update_status()
                            break
        except Exception as e:
            logger.error(f"Error forcing server card {server_id} to disabled state: {e}")
    
    def _update_specific_server_card(self, server_id: str, enabled: bool):
        """Update a specific server card without recreating all cards."""
        try:
            # Import here to avoid circular imports and ensure symbol availability
            from gui.server_card import ServerCard
            # Get the actual server status from the service if available
            actual_status = "disabled"
            actual_tool_count = 0
            
            if enabled:
                # When enabled, default to "connected" state
                actual_status = "connected"
            
            # If we have a service manager, try to get more accurate status
            if self.service_manager:
                server_statuses = self.service_manager.get_server_statuses()
                for status in server_statuses:
                    if status["name"] == server_id:
                        # Update the tool count from server status
                        actual_tool_count = status.get("tool_count", 0)
                        # Update tooltip with any error message
                        try:
                            tooltip_parts = []
                            # Keep existing tooltip description if present
                            # and append latest error message
                            err = status.get("error_message")
                            if err:
                                tooltip_parts.append(f"Error: {err}")
                            # Apply tooltip if any
                            if tooltip_parts:
                                widget_tooltip = "\n".join(tooltip_parts)
                        except Exception:
                            widget_tooltip = None
                        
                        # Determine the actual status
                        if status.get("connected", False):
                            actual_status = "connected"
                        elif status.get("enabled", False):
                            actual_status = "disconnected"
                        else:
                            actual_status = "disabled"
                        break
            
            # Find the specific server card widget and update it directly
            if (self.status_widget and hasattr(self.status_widget, 'servers_layout') and 
                hasattr(self.status_widget.servers_layout, 'count') and 
                hasattr(self.status_widget.servers_layout, 'itemAt')):
                
                for i in range(self.status_widget.servers_layout.count()):
                    item = self.status_widget.servers_layout.itemAt(i)
                    if item and hasattr(item, 'widget'):
                        widget = item.widget()
                        if widget and isinstance(widget, ServerCard) and widget.server_id == server_id:
                            # Found the server card, update its status
                            widget.set_status(actual_status)
                            
                            # Update the tool count if needed
                            widget.set_tool_count(actual_tool_count)
                            # Update tooltip if available
                            try:
                                if 'widget_tooltip' in locals() and widget_tooltip:
                                    widget.setToolTip(widget_tooltip)
                            except Exception:
                                pass
                            break
        except Exception as e:
            logger.error(f"Error updating specific server card {server_id}: {e}")
            # Fallback to full update if specific update fails
            self.update_servers_display()
    
    def update_all_server_tool_counts(self):
        """Update tool counts for all server cards without triggering status changes."""
        try:
            # Import here to avoid circular imports and ensure symbol availability
            from gui.server_card import ServerCard
            # Update API banner base before/after fetch
            if self.service_manager and hasattr(self.service_manager, 'last_api_base') and self.status_widget:
                base_pre = self.service_manager.last_api_base or f"http://localhost:{getattr(self.service_manager, 'tool_gating_port', 'unknown')}"
                if hasattr(self.status_widget, 'api_base_label'):
                    self.status_widget.api_base_label.setText(base_pre)
            # Get all server statuses from the API
            if not self.service_manager:
                return
                
            server_statuses = self.service_manager.get_server_statuses()
            # Reflect banner after call
            if self.status_widget:
                if hasattr(self.status_widget, 'api_base_label'):
                    base_post = self.service_manager.last_api_base or f"http://localhost:{getattr(self.service_manager, 'tool_gating_port', 'unknown')}"
                    self.status_widget.api_base_label.setText(base_post)
                if hasattr(self.status_widget, 'last_refresh_label'):
                    if server_statuses:
                        self.status_widget.last_refresh_label.setText("OK")
                    else:
                        err = getattr(self.service_manager, 'last_status_error', None) or "No data"
                        self.status_widget.last_refresh_label.setText(err)
            server_status_dict = {status["name"]: status for status in server_statuses}
            
            # Update each server card's tool count
            if (self.status_widget and hasattr(self.status_widget, 'servers_layout') and 
                hasattr(self.status_widget.servers_layout, 'count') and 
                hasattr(self.status_widget.servers_layout, 'itemAt')):
                
                for i in range(self.status_widget.servers_layout.count()):
                    item = self.status_widget.servers_layout.itemAt(i)
                    if item and hasattr(item, 'widget'):
                        widget = item.widget()
                        if widget and isinstance(widget, ServerCard):
                            server_id = widget.server_id
                            if server_id in server_status_dict:
                                # Only update tool count, not status
                                tool_count = server_status_dict[server_id].get("tool_count", 0)
                                widget.set_tool_count(tool_count)
                                # Also propagate error message to visible line
                                try:
                                    widget.set_error_message(server_status_dict[server_id].get("error_message"))
                                except Exception:
                                    pass
        except Exception as e:
            logger.error(f"Error updating server tool counts: {e}")

    def discover_server_tools(self, server_id: str):
        """Trigger immediate tool discovery for a server without blocking UI; refresh its count."""
        if not self.service_manager:
            self.show_status_message("Service manager not available")
            return
        self.show_status_message(f"Discovering tools on {server_id}…")

        def _task():
            try:
                ok_local = self.service_manager.discover_tools(server_id)
            except Exception as e:
                ok_local = False
                err = str(e)
                QTimer.singleShot(0, lambda: self.show_status_message(f"Discover error on {server_id}: {err}"))
            else:
                msg = f"Discover triggered for {server_id}" if ok_local else f"Discover failed for {server_id}"
                QTimer.singleShot(0, lambda: self.show_status_message(msg))
            finally:
                QTimer.singleShot(400, self.update_all_server_tool_counts)

        threading.Thread(target=_task, daemon=True).start()

    def discover_all_servers(self):
        """Trigger discovery for all servers without blocking UI; refresh counts."""
        if not self.service_manager:
            self.show_status_message("Service manager not available")
            return
        self.show_status_message("Discovering tools on all servers…")

        def _task():
            try:
                fn = getattr(self.service_manager, 'discover_all_tools', None)
                if callable(fn):
                    any_ok = self.service_manager.discover_all_tools()
                else:
                    statuses = self.service_manager.get_server_statuses()
                    any_ok = False
                    for st in statuses:
                        sid = st.get("name")
                        if not sid:
                            continue
                        try:
                            any_ok = self.service_manager.discover_tools(sid) or any_ok
                        except Exception:
                            continue
                msg = "Discover initiated for all servers" if any_ok else "Discover failed for all servers"
                QTimer.singleShot(0, lambda: self.show_status_message(msg))
            except Exception as e:
                QTimer.singleShot(0, lambda: self.show_status_message(f"Error discovering all servers: {e}"))
            finally:
                QTimer.singleShot(600, self.update_all_server_tool_counts)

        threading.Thread(target=_task, daemon=True).start()
    
    def load_port_configuration(self):
        """Load the port configuration from the config manager."""
        if self.config_manager and self.status_widget:
            try:
                config = self.config_manager.load_config()
                port = config.tool_gating.port
                self.status_widget.port_input.setText(str(port))
            except Exception as e:
                logger.error(f"Error loading port configuration: {e}")
                # Fallback to default port
                self.status_widget.port_input.setText("8001")
        elif self.status_widget:
            # Fallback to default port
            self.status_widget.port_input.setText("8001")
    
    def closeEvent(self, a0) -> None:
        """Handle window close event."""
        # For menubar app, hide instead of closing
        self.hide()
        if a0:
            a0.ignore()
        # Call the parent implementation
        super().closeEvent(a0)

    def on_manage_proxy_toggled(self, checked: bool):
        try:
            if self.config_manager:
                self.config_manager.set_manage_proxy(bool(checked))
                self.show_status_message("Managed Proxy setting saved; restarting service...")
                QTimer.singleShot(200, self.restart_service)
        except Exception as e:
            self.show_status_message(f"Failed to save Managed Proxy: {e}")

    def on_auto_proxy_stdio_toggled(self, checked: bool):
        try:
            if self.config_manager:
                self.config_manager.set_auto_proxy_stdio(bool(checked))
                self.show_status_message("Auto-Proxy stdio setting saved; restarting service...")
                QTimer.singleShot(200, self.restart_service)
        except Exception as e:
            self.show_status_message(f"Failed to save Auto-Proxy stdio: {e}")

    def update_proxy_status(self):
        try:
            if not self.service_manager:
                return
            status = self.service_manager.get_proxy_status()
            if status and hasattr(self.status_widget, 'proxy_status_label'):
                running = status.get('running')
                managed = status.get('managed')
                base = status.get('base_url') or '—'
                if hasattr(self.status_widget, 'proxy_mode_label'):
                    self.status_widget.proxy_mode_label.setText(f"Managed: {'On' if managed else 'Off'}")
                # Update status line with readable text
                txt = f"Status: {'Running' if running else 'Stopped'} • Base: {base}"
                self.status_widget.proxy_status_label.setText(txt)
        except Exception:
            pass
