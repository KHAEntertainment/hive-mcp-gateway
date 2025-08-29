"""Configuration editor for Hive MCP Gateway JSON configuration."""

import json
import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
    QLabel, QMessageBox, QSplitter, QGroupBox, QFormLayout,
    QLineEdit, QSpinBox, QCheckBox, QComboBox, QTabWidget,
    QListWidget, QListWidgetItem, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor

from hive_mcp_gateway.services.config_manager import ConfigManager
from hive_mcp_gateway.models.config import (
    ToolGatingConfig, BackendServerConfig, ValidationResult
)

logger = logging.getLogger(__name__)


class JsonSyntaxHighlighter(QSyntaxHighlighter):
    """JSON syntax highlighter for the text editor."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Define text formats
        self.key_format = QTextCharFormat()
        self.key_format.setForeground(QColor(0, 0, 255))  # Blue
        
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor(0, 128, 0))  # Green
        
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor(255, 0, 0))  # Red
        
        self.boolean_format = QTextCharFormat()
        self.boolean_format.setForeground(QColor(128, 0, 128))  # Purple
        
        self.null_format = QTextCharFormat()
        self.null_format.setForeground(QColor(128, 128, 128))  # Gray
    
    def highlightBlock(self, text):
        """Apply syntax highlighting to a block of text."""
        # Simple JSON highlighting
        import re
        
        # Highlight strings (keys and values)
        string_pattern = r'"[^"]*"'
        for match in re.finditer(string_pattern, text):
            start, end = match.span()
            # Check if it's a key (followed by colon) or value
            if end < len(text) and text[end:end+1].strip().startswith(':'):
                self.setFormat(start, end - start, self.key_format)
            else:
                self.setFormat(start, end - start, self.string_format)
        
        # Highlight numbers
        number_pattern = r'\b\d+\.?\d*\b'
        for match in re.finditer(number_pattern, text):
            start, end = match.span()
            self.setFormat(start, end - start, self.number_format)
        
        # Highlight booleans
        boolean_pattern = r'\b(true|false)\b'
        for match in re.finditer(boolean_pattern, text):
            start, end = match.span()
            self.setFormat(start, end - start, self.boolean_format)
        
        # Highlight null
        null_pattern = r'\bnull\b'
        for match in re.finditer(null_pattern, text):
            start, end = match.span()
            self.setFormat(start, end - start, self.null_format)


class ServerConfigDialog(QDialog):
    """Dialog for editing individual server configurations."""
    
    def __init__(self, server_name: str = "", config: Optional[BackendServerConfig] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server Configuration")
        self.setModal(True)
        self.resize(500, 400)
        
        self.server_name = server_name
        self.config = config or BackendServerConfig()
        
        self.setup_ui()
        self.load_config()
    
    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Server name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Server Name:"))
        self.name_edit = QLineEdit(self.server_name)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Tabs for different configuration sections
        tabs = QTabWidget()
        
        # Basic tab
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["stdio", "sse", "streamable-http"])
        basic_layout.addRow("Type:", self.type_combo)
        
        self.enabled_check = QCheckBox()
        self.enabled_check.setChecked(True)
        basic_layout.addRow("Enabled:", self.enabled_check)
        
        self.description_edit = QLineEdit()
        basic_layout.addRow("Description:", self.description_edit)
        
        tabs.addTab(basic_tab, "Basic")
        
        # Stdio tab
        stdio_tab = QWidget()
        stdio_layout = QFormLayout(stdio_tab)
        
        self.command_edit = QLineEdit()
        stdio_layout.addRow("Command:", self.command_edit)
        
        self.args_edit = QTextEdit()
        self.args_edit.setMaximumHeight(100)
        stdio_layout.addRow("Arguments (one per line):", self.args_edit)
        
        tabs.addTab(stdio_tab, "Stdio")
        
        # HTTP tab
        http_tab = QWidget()
        http_layout = QFormLayout(http_tab)
        
        self.url_edit = QLineEdit()
        http_layout.addRow("URL:", self.url_edit)
        
        self.headers_edit = QTextEdit()
        self.headers_edit.setMaximumHeight(100)
        http_layout.addRow("Headers (JSON):", self.headers_edit)
        
        tabs.addTab(http_tab, "HTTP")
        
        # Environment tab
        env_tab = QWidget()
        env_layout = QFormLayout(env_tab)
        
        self.env_edit = QTextEdit()
        self.env_edit.setMaximumHeight(150)
        env_layout.addRow("Environment Variables (JSON):", self.env_edit)
        
        tabs.addTab(env_tab, "Environment")
        
        layout.addWidget(tabs)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def load_config(self):
        """Load configuration into the form."""
        if self.config:
            self.type_combo.setCurrentText(self.config.type)
            self.enabled_check.setChecked(self.config.enabled)
            self.description_edit.setText(self.config.description or "")
            self.command_edit.setText(self.config.command or "")
            self.url_edit.setText(self.config.url or "")
            
            if self.config.args:
                self.args_edit.setPlainText("\n".join(self.config.args))
            
            if self.config.headers:
                self.headers_edit.setPlainText(json.dumps(self.config.headers, indent=2))
            
            if self.config.env:
                self.env_edit.setPlainText(json.dumps(self.config.env, indent=2))
    
    def get_config(self) -> tuple[str, BackendServerConfig]:
        """Get the configuration from the form."""
        # Parse args
        args = []
        args_text = self.args_edit.toPlainText().strip()
        if args_text:
            args = [line.strip() for line in args_text.split('\n') if line.strip()]
        
        # Parse headers
        headers = {}
        headers_text = self.headers_edit.toPlainText().strip()
        if headers_text:
            try:
                headers = json.loads(headers_text)
            except json.JSONDecodeError:
                pass
        
        # Parse env
        env = {}
        env_text = self.env_edit.toPlainText().strip()
        if env_text:
            try:
                env = json.loads(env_text)
            except json.JSONDecodeError:
                pass
        
        config = BackendServerConfig(
            type=self.type_combo.currentText(),
            command=self.command_edit.text() if self.command_edit.text() else None,
            args=args if args else None,
            url=self.url_edit.text() if self.url_edit.text() else None,
            headers=headers if headers else None,
            env=env if env else None,
            description=self.description_edit.text() if self.description_edit.text() else None,
            enabled=self.enabled_check.isChecked()
        )
        
        return self.name_edit.text(), config


class ConfigurationEditor(QWidget):
    """Main configuration editor widget."""
    
    config_saved = pyqtSignal()
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.current_config: Optional[ToolGatingConfig] = None
        
        self.setWindowTitle("Hive MCP Gateway Configuration")
        self.resize(800, 600)
        
        self.setup_ui()
        self.load_configuration()
    
    def setup_ui(self):
        """Setup the configuration editor UI."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Hive MCP Gateway Configuration Editor")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Server list and controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Server list
        servers_group = QGroupBox("MCP Servers")
        servers_layout = QVBoxLayout(servers_group)
        
        self.servers_list = QListWidget()
        self.servers_list.itemDoubleClicked.connect(self.edit_server)
        servers_layout.addWidget(self.servers_list)
        
        # Server buttons
        server_buttons = QHBoxLayout()
        self.add_server_btn = QPushButton("Add Server")
        self.add_server_btn.clicked.connect(self.add_server)
        server_buttons.addWidget(self.add_server_btn)
        
        self.edit_server_btn = QPushButton("Edit Server")
        self.edit_server_btn.clicked.connect(self.edit_server)
        server_buttons.addWidget(self.edit_server_btn)
        
        self.remove_server_btn = QPushButton("Remove Server")
        self.remove_server_btn.clicked.connect(self.remove_server)
        server_buttons.addWidget(self.remove_server_btn)
        
        servers_layout.addLayout(server_buttons)
        left_layout.addWidget(servers_group)
        
        # App settings
        settings_group = QGroupBox("Application Settings")
        settings_layout = QFormLayout(settings_group)
        
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(8001)
        settings_layout.addRow("Port:", self.port_spin)
        
        self.host_edit = QLineEdit("0.0.0.0")
        settings_layout.addRow("Host:", self.host_edit)
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["debug", "info", "warning", "error"])
        self.log_level_combo.setCurrentText("info")
        settings_layout.addRow("Log Level:", self.log_level_combo)
        
        self.auto_discover_check = QCheckBox()
        self.auto_discover_check.setChecked(True)
        settings_layout.addRow("Auto Discover:", self.auto_discover_check)
        
        left_layout.addWidget(settings_group)
        
        splitter.addWidget(left_panel)
        
        # Right panel - JSON editor
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # JSON editor
        json_group = QGroupBox("Raw JSON Configuration")
        json_layout = QVBoxLayout(json_group)
        
        self.json_editor = QTextEdit()
        self.json_editor.setFont(QFont("Courier", 10))
        
        # Add syntax highlighting
        self.highlighter = JsonSyntaxHighlighter(self.json_editor.document())
        
        json_layout.addWidget(self.json_editor)
        
        # Validation status
        self.validation_label = QLabel("Configuration is valid")
        self.validation_label.setStyleSheet("color: green;")
        json_layout.addWidget(self.validation_label)
        
        right_layout.addWidget(json_group)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 500])
        
        layout.addWidget(splitter)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        self.validate_btn = QPushButton("Validate")
        self.validate_btn.clicked.connect(self.validate_configuration)
        button_layout.addWidget(self.validate_btn)
        
        self.reload_btn = QPushButton("Reload")
        self.reload_btn.clicked.connect(self.load_configuration)
        button_layout.addWidget(self.reload_btn)
        
        button_layout.addStretch()
        
        self.save_btn = QPushButton("Save Configuration")
        self.save_btn.clicked.connect(self.save_configuration)
        self.save_btn.setStyleSheet("font-weight: bold;")
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
    
    def load_configuration(self):
        """Load configuration from config manager."""
        try:
            self.current_config = self.config_manager.load_config()
            self.update_ui_from_config()
            self.validation_label.setText("Configuration loaded successfully")
            self.validation_label.setStyleSheet("color: green;")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            QMessageBox.critical(self, "Load Error", f"Failed to load configuration: {e}")
    
    def update_ui_from_config(self):
        """Update UI elements from current config."""
        if not self.current_config:
            return
        
        # Update app settings
        self.port_spin.setValue(self.current_config.tool_gating.port)
        self.host_edit.setText(self.current_config.tool_gating.host)
        self.log_level_combo.setCurrentText(self.current_config.tool_gating.log_level)
        self.auto_discover_check.setChecked(self.current_config.tool_gating.auto_discover)
        
        # Update servers list
        self.servers_list.clear()
        for name, config in self.current_config.backend_mcp_servers.items():
            item = QListWidgetItem(f"{name} ({config.type})")
            item.setData(Qt.ItemDataRole.UserRole, name)
            if not config.enabled:
                item.setText(f"{name} ({config.type}) [DISABLED]")
            self.servers_list.addItem(item)
        
        # Update JSON editor
        config_dict = self.current_config.dict(by_alias=True)
        formatted_json = json.dumps(config_dict, indent=2)
        self.json_editor.setPlainText(formatted_json)
    
    def add_server(self):
        """Add a new server configuration."""
        dialog = ServerConfigDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, config = dialog.get_config()
            if name and name not in self.current_config.backend_mcp_servers:
                self.current_config.backend_mcp_servers[name] = config
                self.update_ui_from_config()
            else:
                QMessageBox.warning(self, "Add Server", "Server name is empty or already exists")
    
    def edit_server(self):
        """Edit selected server configuration."""
        current_item = self.servers_list.currentItem()
        if not current_item:
            return
        
        server_name = current_item.data(Qt.ItemDataRole.UserRole)
        server_config = self.current_config.backend_mcp_servers[server_name]
        
        dialog = ServerConfigDialog(server_name, server_config, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name, new_config = dialog.get_config()
            
            # Remove old entry if name changed
            if new_name != server_name:
                del self.current_config.backend_mcp_servers[server_name]
            
            self.current_config.backend_mcp_servers[new_name] = new_config
            self.update_ui_from_config()
    
    def remove_server(self):
        """Remove selected server configuration."""
        current_item = self.servers_list.currentItem()
        if not current_item:
            return
        
        server_name = current_item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, "Remove Server",
            f"Are you sure you want to remove server '{server_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            del self.current_config.backend_mcp_servers[server_name]
            self.update_ui_from_config()
    
    def validate_configuration(self):
        """Validate current configuration."""
        try:
            json_text = self.json_editor.toPlainText()
            config_data = json.loads(json_text)
            
            result = self.config_manager.validate_config(config_data)
            
            if result.is_valid:
                self.validation_label.setText("Configuration is valid")
                self.validation_label.setStyleSheet("color: green;")
            else:
                error_text = "Validation errors:\n" + "\n".join(result.errors)
                if result.warnings:
                    error_text += "\n\nWarnings:\n" + "\n".join(result.warnings)
                
                self.validation_label.setText("Configuration has errors")
                self.validation_label.setStyleSheet("color: red;")
                
                QMessageBox.warning(self, "Validation Errors", error_text)
                
        except json.JSONDecodeError as e:
            self.validation_label.setText("Invalid JSON format")
            self.validation_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "JSON Error", f"Invalid JSON format: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Validation Error", f"Validation failed: {e}")
    
    def save_configuration(self):
        """Save current configuration."""
        try:
            # First validate
            self.validate_configuration()
            
            # Update config from UI
            self.current_config.tool_gating.port = self.port_spin.value()
            self.current_config.tool_gating.host = self.host_edit.text()
            self.current_config.tool_gating.log_level = self.log_level_combo.currentText()
            self.current_config.tool_gating.auto_discover = self.auto_discover_check.isChecked()
            
            # Save to file
            self.config_manager.save_config(self.current_config)
            
            QMessageBox.information(self, "Save Configuration", "Configuration saved successfully!")
            self.config_saved.emit()
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            QMessageBox.critical(self, "Save Error", f"Failed to save configuration: {e}")
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Check if there are unsaved changes
        # For now, just close
        event.accept()