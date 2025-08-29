"""MCP JSON snippet processor for easy server registration."""

import json
import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
    QLabel, QMessageBox, QGroupBox, QLineEdit, QComboBox
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont

from hive_mcp_gateway.services.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class MCPSnippetProcessor(QWidget):
    """Widget for processing and registering MCP JSON snippets."""
    
    snippet_processed = pyqtSignal(str, bool)  # server_name, success
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        
        self.setWindowTitle("MCP Snippet Processor")
        self.resize(600, 500)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the snippet processor UI."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("MCP JSON Snippet Processor")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            "Paste MCP server JSON snippets below to automatically register them with Hive MCP Gateway. "
            "Supports both mcp-proxy format and direct server configuration format."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; margin: 5px;")
        layout.addWidget(instructions)
        
        # Input section
        input_group = QGroupBox("JSON Snippet Input")
        input_layout = QVBoxLayout(input_group)
        
        # Server name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Server Name (optional):"))
        self.server_name_edit = QLineEdit()
        self.server_name_edit.setPlaceholderText("Auto-detected from JSON or enter custom name")
        name_layout.addWidget(self.server_name_edit)
        input_layout.addLayout(name_layout)
        
        # JSON input area
        self.json_input = QTextEdit()
        self.json_input.setFont(QFont("Courier", 10))
        self.json_input.setPlaceholderText("""Paste MCP JSON snippet here, e.g.:

{
  "mcpServers": {
    "my_server": {
      "command": "npx",
      "args": ["-y", "@my/mcp-server"],
      "env": {}
    }
  }
}

or direct format:

{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@my/mcp-server"],
  "description": "My MCP server"
}""")
        input_layout.addWidget(self.json_input)
        
        layout.addWidget(input_group)
        
        # Processing options
        options_group = QGroupBox("Processing Options")
        options_layout = QVBoxLayout(options_group)
        
        action_layout = QHBoxLayout()
        action_layout.addWidget(QLabel("Action if server exists:"))
        self.action_combo = QComboBox()
        self.action_combo.addItems(["Update existing", "Skip", "Create new with suffix"])
        action_layout.addWidget(self.action_combo)
        options_layout.addLayout(action_layout)
        
        layout.addWidget(options_group)
        
        # Status area
        self.status_label = QLabel("Ready to process snippets")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.validate_btn = QPushButton("Validate JSON")
        self.validate_btn.clicked.connect(self.validate_snippet)
        button_layout.addWidget(self.validate_btn)
        
        self.preview_btn = QPushButton("Preview Config")
        self.preview_btn.clicked.connect(self.preview_config)
        button_layout.addWidget(self.preview_btn)
        
        button_layout.addStretch()
        
        self.process_btn = QPushButton("Process & Register")
        self.process_btn.clicked.connect(self.process_snippet)
        self.process_btn.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")
        button_layout.addWidget(self.process_btn)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_input)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
    
    def validate_snippet(self):
        """Validate the JSON snippet."""
        try:
            json_text = self.json_input.toPlainText().strip()
            if not json_text:
                self.update_status("No JSON input provided", "warning")
                return False
            
            # Parse JSON
            data = json.loads(json_text)
            
            # Check format
            if "mcpServers" in data:
                self.update_status("Valid mcp-proxy format detected", "success")
                return True
            elif "type" in data:
                self.update_status("Valid direct server format detected", "success")
                return True
            else:
                self.update_status("Unknown JSON format - please check structure", "warning")
                return False
                
        except json.JSONDecodeError as e:
            self.update_status(f"Invalid JSON: {e}", "error")
            return False
        except Exception as e:
            self.update_status(f"Validation error: {e}", "error")
            return False
    
    def preview_config(self):
        """Preview the configuration that would be created."""
        if not self.validate_snippet():
            return
        
        try:
            json_text = self.json_input.toPlainText().strip()
            server_name = self.server_name_edit.text().strip()
            
            # Process snippet to see what would be created
            result = self.config_manager.process_mcp_snippet(json_text, server_name)
            
            if result.success:
                QMessageBox.information(
                    self, "Preview Configuration",
                    f"Server Name: {result.server_name}\n"
                    f"Action: {result.action}\n"
                    f"Message: {result.message}"
                )
            else:
                QMessageBox.warning(
                    self, "Preview Failed", 
                    f"Preview failed: {result.message}"
                )
                
        except Exception as e:
            QMessageBox.critical(self, "Preview Error", f"Preview failed: {e}")
    
    def process_snippet(self):
        """Process the JSON snippet and register the server."""
        if not self.validate_snippet():
            return
        
        try:
            json_text = self.json_input.toPlainText().strip()
            server_name = self.server_name_edit.text().strip() or None
            
            # Process the snippet
            result = self.config_manager.process_mcp_snippet(json_text, server_name)
            
            if result.success:
                self.update_status(f"✅ {result.message}", "success")
                
                # Show success message
                QMessageBox.information(
                    self, "Registration Successful",
                    f"Server '{result.server_name}' was successfully {result.action}!\n\n"
                    "The configuration has been saved and will be automatically loaded."
                )
                
                # Clear input
                self.clear_input()
                
                # Emit signal
                self.snippet_processed.emit(result.server_name, True)
                
            else:
                self.update_status(f"❌ {result.message}", "error")
                
                error_details = "\n".join(result.errors) if result.errors else "Unknown error"
                QMessageBox.warning(
                    self, "Registration Failed",
                    f"Failed to register server: {result.message}\n\n"
                    f"Details:\n{error_details}"
                )
                
                self.snippet_processed.emit("", False)
                
        except Exception as e:
            logger.error(f"Error processing snippet: {e}")
            self.update_status(f"Processing error: {e}", "error")
            QMessageBox.critical(self, "Processing Error", f"Failed to process snippet: {e}")
    
    def clear_input(self):
        """Clear all input fields."""
        self.json_input.clear()
        self.server_name_edit.clear()
        self.update_status("Ready to process snippets", "normal")
    
    def update_status(self, message: str, status_type: str = "normal"):
        """Update the status label with appropriate styling."""
        colors = {
            "normal": "#666",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "error": "#F44336"
        }
        
        color = colors.get(status_type, colors["normal"])
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; font-style: italic;")
    
    def set_example_snippet(self, snippet_type: str = "mcp_proxy"):
        """Set an example snippet for demonstration."""
        examples = {
            "mcp_proxy": """{
  "mcpServers": {
    "example_server": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "${API_KEY}"
      }
    }
  }
}""",
            "direct": """{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@example/mcp-server"],
  "env": {
    "API_KEY": "${API_KEY}"
  },
  "description": "Example MCP server",
  "enabled": true
}"""
        }
        
        self.json_input.setPlainText(examples.get(snippet_type, examples["mcp_proxy"]))
        self.update_status(f"Example {snippet_type} snippet loaded", "normal")