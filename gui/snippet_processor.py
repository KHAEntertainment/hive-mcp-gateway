"""MCP JSON snippet processor for easy server registration."""

import json
import logging
import re
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
    QLabel, QMessageBox, QGroupBox, QLineEdit, QComboBox,
    QDialog, QFormLayout, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt, QCoreApplication
from PyQt6.QtGui import QFont

from hive_mcp_gateway.services.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class MCPSnippetProcessor(QDialog):
    """Widget for processing and registering MCP JSON snippets."""
    
    snippet_processed = pyqtSignal(str, bool)  # server_name, success
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.editing_mode = False  # Whether we're editing an existing server
        self.original_server_id = None  # The ID of the server being edited
        
        self.setWindowTitle("MCP Snippet Processor")
        self.resize(680, 550)
        self.setObjectName("snippetProcessorDialog")
        
        # Load stylesheet
        self.load_stylesheet()
        
        self.setup_ui()
    
    def load_stylesheet(self):
        """Load and apply the Hive Night theme stylesheet."""
        try:
            # Try to load from assets directory using absolute path
            from pathlib import Path
            current_dir = Path(__file__).parent
            stylesheet_path = current_dir / "assets" / "styles.qss"
            
            if not stylesheet_path.exists():
                # Fallback to relative path
                stylesheet_path = "gui/assets/styles.qss"
                
            with open(stylesheet_path, "r") as f:
                stylesheet = f.read()
                self.setStyleSheet(stylesheet)
                logger.info(f"Loaded stylesheet for Snippet Processor from {stylesheet_path}")
        except FileNotFoundError:
            logger.warning(f"Stylesheet not found for Snippet Processor")
        except Exception as e:
            logger.error(f"Error loading stylesheet for Snippet Processor: {e}")
    
    def setup_ui(self):
        """Setup the snippet processor UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)  # Reduced from 24
        layout.setContentsMargins(24, 16, 24, 16)  # Reduced top/bottom margins
        
        # Header section
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        self.title_label = QLabel("MCP JSON Snippet Processor")
        self.title_label.setObjectName("headerTitle")
        header_layout.addWidget(self.title_label)
        
        # Instructions
        instructions = QLabel(
            "Paste MCP server JSON snippets below to automatically register them with Hive MCP Gateway. "
            "Supports both mcp-proxy and direct server configuration format."
        )
        instructions.setObjectName("headerDescription")
        instructions.setWordWrap(True)
        header_layout.addWidget(instructions)
        
        layout.addWidget(header_widget)
        
        # Input section
        input_group = QGroupBox()
        input_group.setTitle("JSON SNIPPET INPUT")
        input_group.setObjectName("jsonInputGroup")
        input_layout = QVBoxLayout(input_group)
        input_layout.setContentsMargins(10, 10, 10, 10)  # Reduced padding
        input_layout.setSpacing(8)  # Reduced spacing
        
        # Server name input
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        server_name_label = QLabel("Server Name (optional):")
        self.server_name_edit = QLineEdit()
        self.server_name_edit.setObjectName("serverNameInput")
        self.server_name_edit.setPlaceholderText("auto-detected from JSON or enter custom name")
        form_layout.addRow(server_name_label, self.server_name_edit)
        input_layout.addLayout(form_layout)
        
        # JSON input area
        self.json_input = QTextEdit()
        self.json_input.setObjectName("snippetInputArea")
        self.json_input.setFont(QFont("JetBrains Mono", 10))
        self.json_input.setMinimumHeight(180)  # Set a taller minimum height
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

Or partial server config that will be auto-wrapped:
{
  "Ref": {
    "command": "npx",
    "args": ["ref-tools-mcp@latest"],
    "env": {
      "REF_API_KEY": "1418ed51634694ef65e1"
    }
  }
}""")
        input_layout.addWidget(self.json_input)
        
        layout.addWidget(input_group)
        
        # Processing options
        options_group = QGroupBox()
        options_group.setTitle("PROCESSING OPTIONS")
        options_group.setObjectName("optionsGroup")
        options_layout = QVBoxLayout(options_group)
        options_layout.setContentsMargins(10, 10, 10, 10)  # Reduced padding
        options_layout.setSpacing(8)  # Reduced spacing
        
        options_form = QFormLayout()
        options_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        options_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        action_label = QLabel("Action if server exists:")
        self.action_combo = QComboBox()
        self.action_combo.setObjectName("actionComboBox")
        self.action_combo.addItems(["Update existing", "Skip", "Create new with unique name"])
        options_form.addRow(action_label, self.action_combo)
        options_layout.addLayout(options_form)
        
        layout.addWidget(options_group)
        
        # Status area
        self.status_label = QLabel("Ready to process snippets")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        
        # Footer with Buttons
        footer_widget = QWidget()
        footer_widget.setObjectName("footerBar")
        button_layout = QHBoxLayout(footer_widget)
        button_layout.setContentsMargins(0, 16, 0, 0)
        
        # Add spacing to push buttons to the right
        button_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        self.validate_btn = QPushButton("Validate JSON")
        self.validate_btn.setObjectName("validateButton")
        self.validate_btn.clicked.connect(self.validate_snippet)
        button_layout.addWidget(self.validate_btn)
        
        self.fix_btn = QPushButton("Fix JSON")
        self.fix_btn.setObjectName("fixButton")
        self.fix_btn.clicked.connect(self.fix_json_snippet)
        button_layout.addWidget(self.fix_btn)
        
        self.preview_btn = QPushButton("Preview Config")
        self.preview_btn.setObjectName("previewButton")
        self.preview_btn.clicked.connect(self.preview_config)
        button_layout.addWidget(self.preview_btn)
        
        self.process_btn = QPushButton("Process & Register")
        self.process_btn.setObjectName("processButton")
        self.process_btn.clicked.connect(self.process_snippet)
        button_layout.addWidget(self.process_btn)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("clearButton")
        self.clear_btn.clicked.connect(self.clear_input)
        button_layout.addWidget(self.clear_btn)
        
        layout.addWidget(footer_widget)
    
    def set_editing_mode(self, server_id: str, json_config: str):
        """Set the dialog to editing mode for an existing server."""
        self.editing_mode = True
        self.original_server_id = server_id
        
        # Update the window title and button text
        self.setWindowTitle(f"Edit MCP Server: {server_id}")
        self.title_label.setText(f"Edit MCP Server: {server_id}")
        self.process_btn.setText("Save Changes")
        
        # Set the server name and JSON input
        self.server_name_edit.setText(server_id)
        self.server_name_edit.setEnabled(False)  # Can't change server ID when editing
        self.json_input.setPlainText(json_config)
        
        # Set the action to update existing
        self.action_combo.setCurrentText("Update existing")
        self.action_combo.setEnabled(False)  # Can't change action when editing
    
    def clear_editing_mode(self):
        """Clear editing mode settings."""
        self.editing_mode = False
        self.original_server_id = None
        
        # Reset window title and button text
        self.setWindowTitle("MCP Snippet Processor")
        self.title_label.setText("MCP JSON Snippet Processor")
        self.process_btn.setText("Process & Register")
        
        # Enable server name and action combo
        self.server_name_edit.setEnabled(True)
        self.action_combo.setEnabled(True)
        
        # Clear input fields
        self.clear_input()
    
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
    
    def fix_json_snippet(self):
        """Attempt to automatically fix common JSON errors."""
        try:
            json_text = self.json_input.toPlainText().strip()
            if not json_text:
                self.update_status("No JSON input provided", "warning")
                return False
            
            # Fix common JSON issues
            fixed_json = self._fix_common_json_issues(json_text)
            
            # Try to parse the fixed JSON
            try:
                json.loads(fixed_json)
                # If successful, update the input field with the fixed JSON
                self.json_input.setPlainText(fixed_json)
                self.update_status("JSON fixed successfully! Click Validate to check.", "success")
                return True
            except json.JSONDecodeError as e:
                self.update_status(f"Could not fix JSON: {e}", "error")
                return False
                
        except Exception as e:
            self.update_status(f"Error fixing JSON: {e}", "error")
            return False
    
    def _fix_common_json_issues(self, json_text: str) -> str:
        """Fix common JSON formatting issues."""
        # Make a copy to work with
        fixed = json_text.strip()
        
        # Fix 1: Remove trailing commas before } or ]
        fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
        
        # Fix 2: Quote unquoted string values (be more specific to avoid matching keys)
        # Match values that look like they might be API keys or similar
        fixed = re.sub(r'("REF_API_KEY":)\s*([a-zA-Z0-9]+)(\s*[,\}\n])', r'\1 "\2"\3', fixed)
        # Handle end of line case
        fixed = re.sub(r'("REF_API_KEY":)\s*([a-zA-Z0-9]+)(\s*)$', r'\1 "\2"\3', fixed)
        
        # Fix 3: Wrap partial server config in mcpServers structure
        if (fixed.startswith("{") and 
            not fixed.startswith('{"mcpServers"') and 
            not fixed.startswith('{"type"') and
            ('"command"' in fixed or '"args"' in fixed or '"env"' in fixed)):
            
            # Try to parse what we have first to see if it's valid after fixes
            try:
                json.loads(fixed)
                # If it's valid JSON, wrap it properly
                # Match the server name and its configuration object properly
                match = re.search(r'"([^"]+)":\s*({[^{]*"command"[^{]*{[^}]*}[^}]*})', fixed, re.DOTALL)
                if match:
                    server_name = match.group(1)
                    server_config = match.group(2)
                    # Wrap properly with correct indentation
                    fixed = f'{{\n  "mcpServers": {{\n    "{server_name}": {server_config}\n  }}\n}}'
                elif fixed.startswith('{') and fixed.endswith('}'):
                    # Fallback: simpler approach
                    # Extract everything between the first { and last }
                    content = fixed[1:-1].strip()
                    # Find the first key and extract just its value
                    key_match = re.search(r'"([^"]+)":\s*({.*})', content, re.DOTALL)
                    if key_match:
                        server_name = key_match.group(1)
                        server_config = key_match.group(2)
                        # Fix trailing commas in the server config
                        server_config = re.sub(r',(\s*[}\]])', r'\1', server_config)
                        fixed = f'{{\n  "mcpServers": {{\n    "{server_name}": {server_config}\n  }}\n}}'
            except:
                pass
        
        return fixed
    
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
            # Try to fix JSON automatically before failing
            if self.fix_json_snippet() and self.validate_snippet():
                # If fixing worked, continue with processing
                pass
            else:
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
        
        # If we were in editing mode, clear it
        if self.editing_mode:
            self.clear_editing_mode()
    
    def update_status(self, message: str, status_type: str = "normal"):
        """Update the status label with appropriate styling."""
        self.status_label.setText(message)
        
        # Set property for status type that can be styled via QSS
        self.status_label.setProperty("statusType", status_type)
        
        # Force style refresh
        QCoreApplication.processEvents()
        self.status_label.setStyleSheet("")
        self.status_label.setStyleSheet(" ")
    
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