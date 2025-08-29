"""Main window for Hive MCP Gateway GUI application."""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QLabel, QPushButton, QTextEdit, QGroupBox,
    QGridLayout, QScrollArea, QListWidget, QListWidgetItem,
    QProgressBar, QFrame, QMessageBox
)
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor

logger = logging.getLogger(__name__)


class StatusWidget(QWidget):
    """Widget for displaying service status information."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the status widget UI."""
        layout = QVBoxLayout(self)
        
        # Service status group
        status_group = QGroupBox("Service Status")
        status_layout = QGridLayout(status_group)
        
        self.service_status_label = QLabel("Status: Unknown")
        self.service_port_label = QLabel("Port: 8001")
        self.service_pid_label = QLabel("PID: Unknown")
        self.service_uptime_label = QLabel("Uptime: Unknown")
        
        status_layout.addWidget(QLabel("Hive MCP Gateway:"), 0, 0)
        status_layout.addWidget(self.service_status_label, 0, 1)
        status_layout.addWidget(QLabel("Port:"), 1, 0)
        status_layout.addWidget(self.service_port_label, 1, 1)
        status_layout.addWidget(QLabel("PID:"), 2, 0)
        status_layout.addWidget(self.service_pid_label, 2, 1)
        status_layout.addWidget(QLabel("Uptime:"), 3, 0)
        status_layout.addWidget(self.service_uptime_label, 3, 1)
        
        layout.addWidget(status_group)
        
        # Dependencies status
        deps_group = QGroupBox("Dependencies")
        deps_layout = QVBoxLayout(deps_group)
        
        self.deps_list = QListWidget()
        deps_layout.addWidget(self.deps_list)
        
        layout.addWidget(deps_group)
        
        # MCP Servers
        servers_group = QGroupBox("Registered MCP Servers")
        servers_layout = QVBoxLayout(servers_group)
        
        self.servers_list = QListWidget()
        servers_layout.addWidget(self.servers_list)
        
        layout.addWidget(servers_group)
        
        layout.addStretch()


class LogsWidget(QWidget):
    """Widget for displaying service logs."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the logs widget UI."""
        layout = QVBoxLayout(self)
        
        # Logs display
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setFont(QFont("Courier", 10))
        self.logs_text.setPlaceholderText("Service logs will appear here...")
        
        layout.addWidget(QLabel("Service Logs:"))
        layout.addWidget(self.logs_text)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.clear_logs_btn = QPushButton("Clear Logs")
        self.refresh_logs_btn = QPushButton("Refresh Logs")
        self.save_logs_btn = QPushButton("Save Logs...")
        
        controls_layout.addWidget(self.clear_logs_btn)
        controls_layout.addWidget(self.refresh_logs_btn)
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
        
        about_text = QLabel("""
        <h2>Hive MCP Gateway</h2>
        <p><strong>Version:</strong> 0.2.0</p>
        <p><strong>Description:</strong> Intelligent proxy for Model Context Protocol (MCP)</p>
        
        <h3>Features:</h3>
        <ul>
            <li>Dynamic tool discovery and provisioning</li>
            <li>Smart semantic search for relevant tools</li>
            <li>Token budget management</li>
            <li>Multiple MCP server integration</li>
            <li>Real-time configuration updates</li>
            <li>Secure credential management</li>
        </ul>
        
        <h3>Configuration:</h3>
        <p>The service runs on port 8001 to avoid conflicts with development instances.</p>
        <p>Access configuration through the menubar icon or this main window.</p>
        
        <h3>Support:</h3>
        <p>For issues and documentation, visit the project repository.</p>
        """)
        
        about_text.setWordWrap(True)
        about_text.setOpenExternalLinks(True)
        about_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Wrap in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidget(about_text)
        scroll_area.setWidgetResizable(True)
        
        layout.addWidget(scroll_area)


class MainWindow(QMainWindow):
    """Main application window (typically hidden for menubar app)."""
    
    # Signals for navigation actions
    show_snippet_processor_requested = pyqtSignal()
    show_credentials_manager_requested = pyqtSignal()
    show_llm_config_requested = pyqtSignal()
    show_autostart_settings_requested = pyqtSignal()
    
    def __init__(self, config_manager=None, service_manager=None, 
                 dependency_checker=None, migration_utility=None, 
                 autostart_manager=None, parent=None):
        """Initialize main window."""
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.service_manager = service_manager
        self.dependency_checker = dependency_checker
        self.migration_utility = migration_utility
        self.autostart_manager = autostart_manager
        
        self.setWindowTitle("Hive MCP Gateway")
        self.setGeometry(100, 100, 900, 700)
        
        self.setup_ui()
        self.setup_connections()
        self.update_status_display()
    
    def show_status_message(self, message: str):
        """Safely show a message in the status bar."""
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage(message)
        
        # Remove the incorrect log message that was causing repeated "Main window initialized" messages
        # logger.info("Main window initialized")
    
    def setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("Hive MCP Gateway Control Center")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Service control buttons in header
        self.start_btn = QPushButton("Start Service")
        self.stop_btn = QPushButton("Stop Service")
        self.restart_btn = QPushButton("Restart Service")
        
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.restart_btn.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold;")
        
        header_layout.addWidget(self.start_btn)
        header_layout.addWidget(self.stop_btn)
        header_layout.addWidget(self.restart_btn)
        
        layout.addLayout(header_layout)
        
        # Navigation buttons section
        nav_group = QGroupBox("Quick Actions")
        nav_layout = QHBoxLayout(nav_group)
        
        # Configuration navigation buttons
        self.add_server_btn = QPushButton("🔧 Add MCP Server")
        self.add_server_btn.setToolTip("Open JSON snippet processor to add a new MCP server")
        self.add_server_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px; } QPushButton:hover { background-color: #1976D2; }")
        
        self.credentials_btn = QPushButton("🔐 Manage Credentials")
        self.credentials_btn.setToolTip("Open credentials manager for API keys and secrets")
        self.credentials_btn.setStyleSheet("QPushButton { background-color: #9C27B0; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px; } QPushButton:hover { background-color: #7B1FA2; }")
        
        self.llm_config_btn = QPushButton("🤖 LLM Configuration")
        self.llm_config_btn.setToolTip("Configure external LLM providers (OpenAI, Anthropic, etc.)")
        self.llm_config_btn.setStyleSheet("QPushButton { background-color: #FF5722; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px; } QPushButton:hover { background-color: #E64A19; }")
        
        self.autostart_btn = QPushButton("⚙️ Auto-Start Settings")
        self.autostart_btn.setToolTip("Configure automatic startup with macOS")
        self.autostart_btn.setStyleSheet("QPushButton { background-color: #607D8B; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px; } QPushButton:hover { background-color: #455A64; }")
        
        nav_layout.addWidget(self.add_server_btn)
        nav_layout.addWidget(self.credentials_btn)
        nav_layout.addWidget(self.llm_config_btn)
        nav_layout.addWidget(self.autostart_btn)
        nav_layout.addStretch()
        
        layout.addWidget(nav_group)
        
        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.status_widget = StatusWidget()
        self.logs_widget = LogsWidget()
        self.about_widget = AboutWidget()
        
        self.tab_widget.addTab(self.status_widget, "📊 Status")
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
        
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_display)
        self.status_timer.start(5000)  # Update every 5 seconds
    
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
        self.status_widget.service_status_label.setText(f"Status: {status.title()}")
        
        # Update button states
        if status == "running":
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(True)
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
                    self.status_widget.service_pid_label.setText(f"PID: {status.pid}")
                else:
                    self.status_widget.service_pid_label.setText("PID: Unknown")
                
                if hasattr(status, 'is_running'):
                    status_text = "Running" if status.is_running else "Stopped"
                    self.status_widget.service_status_label.setText(f"Status: {status_text}")
                    
            except Exception as e:
                logger.debug(f"Error updating status: {e}")
        
        # Update dependencies list
        self.update_dependencies_display()
        
        # Update MCP servers list
        self.update_servers_display()
    
    def update_dependencies_display(self):
        """Update the dependencies status display."""
        self.status_widget.deps_list.clear()
        
        if self.dependency_checker:
            # Instead of calling check_all_dependencies every time (which is expensive),
            # use the already stored dependency status to avoid repeated expensive checks
            # Get detailed info for each dependency that was already checked
            for dep_name in self.dependency_checker.dependency_status.keys():
                dep_info = self.dependency_checker.get_dependency_info(dep_name)
                
                # Determine availability from stored info
                is_available = False
                if dep_info:
                    is_available = dep_info.is_running if hasattr(dep_info, 'is_running') else False
                
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
                
                self.status_widget.deps_list.addItem(item)
            
            # Add Claude Desktop detection
            self.update_claude_desktop_status()
        else:
            # Fallback if dependency checker not available
            fallback_deps = [
                ("Python 3.12+", "✅ Available"),
                ("Dependency Checker", "⚠️ Not initialized")
            ]
            
            for name, status in fallback_deps:
                item = QListWidgetItem(f"{name}: {status}")
                self.status_widget.deps_list.addItem(item)
    
    def update_claude_desktop_status(self):
        """Add Claude Desktop detection to dependency list."""
        try:
            # Try to import and use IDE detector
            from hive_mcp_gateway.services.ide_detector import IDEDetector, IDEType
            
            ide_detector = IDEDetector()
            claude_info = ide_detector.detect_ide(IDEType.CLAUDE_DESKTOP)
            
            if claude_info and claude_info.is_installed:
                status_icon = "✅"
                status_text = "Available"
                if claude_info.version:
                    status_text += f" ({claude_info.version})"
                color = QColor(76, 175, 80)  # Green
            else:
                status_icon = "⚠️"
                status_text = "Not detected"
                color = QColor(255, 152, 0)  # Orange
            
            item_text = f"Claude Desktop: {status_icon} {status_text}"
            item = QListWidgetItem(item_text)
            item.setForeground(color)
            self.status_widget.deps_list.addItem(item)
            
        except ImportError as e:
            logger.debug(f"IDE detector not available: {e}")
            # Add basic entry if IDE detector is not available
            item = QListWidgetItem("Claude Desktop: ⚠️ Detection unavailable")
            item.setForeground(QColor(255, 152, 0))
            self.status_widget.deps_list.addItem(item)
        except Exception as e:
            logger.error(f"Error detecting Claude Desktop: {e}")
            item = QListWidgetItem(f"Claude Desktop: ❌ Error - {e}")
            item.setForeground(QColor(244, 67, 54))  # Red
            self.status_widget.deps_list.addItem(item)
    
    def update_servers_display(self):
        """Update the MCP servers list."""
        self.status_widget.servers_list.clear()
        
        # Add some example servers
        servers = [
            ("Exa Search", "7 tools", "Connected"),
            ("Puppeteer", "12 tools", "Connected"),
            ("Context7", "8 tools", "Disconnected"),
            ("Desktop Commander", "18 tools", "Connected")
        ]
        
        for name, tools, status in servers:
            status_icon = "🟢" if status == "Connected" else "🔴"
            item = QListWidgetItem(f"{status_icon} {name} ({tools}) - {status}")
            self.status_widget.servers_list.addItem(item)
    
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
                is_enabled = self.autostart_manager.is_autostart_enabled()
                
                if is_enabled:
                    reply = QMessageBox.question(
                        self, 
                        "Auto-Start Settings",
                        "Auto-start is currently ENABLED.\n\nDo you want to disable it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        success = self.autostart_manager.disable_autostart()
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
                        success = self.autostart_manager.enable_autostart()
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
    
    def closeEvent(self, a0) -> None:
        """Handle window close event."""
        # For menubar app, hide instead of closing
        self.hide()
        if a0:
            a0.ignore()