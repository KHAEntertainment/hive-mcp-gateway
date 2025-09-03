"""Client Configuration Window for Hive MCP Gateway."""

import logging
import platform
import os
from typing import Optional, Dict, Any
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, 
    QLineEdit, QLabel, QMessageBox, QGroupBox, QCheckBox, QComboBox,
    QFrame, QTextEdit, QTabWidget, QWidget, QScrollArea, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QClipboard

logger = logging.getLogger(__name__)


class ClientConfigWindow(QDialog):
    """Dialog for configuring MCP clients to connect to Hive MCP Gateway."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Client Configuration")
        self.setModal(True)
        self.resize(700, 500)
        
        self.detect_system_info()
        self.load_stylesheet()
        self.setup_ui()
        self.detect_installed_clients()
    
    def detect_system_info(self):
        """Detect system information for dynamic configuration."""
        self.system = platform.system()
        self.user_home = Path.home()
        
        # Detect mcp-proxy path
        self.mcp_proxy_path = self.find_mcp_proxy()
        
        # Detect common client installations
        self.client_paths = self.detect_client_installations()
        
        # Get current server info
        self.server_port = 8001  # Default port
        self.server_address = "http://localhost"
        self.server_url = f"{self.server_address}:{self.server_port}"
    
    def find_mcp_proxy(self) -> str:
        """Find the mcp-proxy executable path."""
        # Check common installation paths
        possible_paths = [
            Path("/usr/local/bin/mcp-proxy"),
            Path("/opt/mcp-proxy/bin/mcp-proxy"),
            self.user_home / ".local/bin/mcp-proxy",
            self.user_home / "node_modules/.bin/mcp-proxy",
            Path("./mcp-proxy")  # Relative to current directory
        ]
        
        # Also check PATH
        path_env = os.environ.get("PATH", "")
        for path_dir in path_env.split(os.pathsep):
            proxy_path = Path(path_dir) / "mcp-proxy"
            if proxy_path.exists() and proxy_path.is_file():
                return str(proxy_path)
        
        # Check in possible paths
        for path in possible_paths:
            if path.exists() and path.is_file():
                return str(path)
        
        # Fallback to command name
        return "mcp-proxy"
    
    def detect_client_installations(self) -> dict:
        """Detect installed MCP clients."""
        client_paths = {}
        
        if self.system == "Darwin":  # macOS
            # Claude Desktop
            claude_path = Path("/Applications/Claude.app")
            if claude_path.exists():
                client_paths["claude_desktop"] = str(claude_path)
            
            # Claude Code (if installed via npm)
            claude_code_paths = [
                self.user_home / ".npm-global/bin/claude-code",
                "/usr/local/bin/claude-code",
                self.user_home / ".nvm/versions/node/v*/bin/claude-code"
            ]
            for path in claude_code_paths:
                if path.exists():
                    client_paths["claude_code"] = str(path)
                    break
            
            # VS Code
            vscode_paths = [
                Path("/Applications/Visual Studio Code.app"),
                self.user_home / "Applications/Visual Studio Code.app"
            ]
            for path in vscode_paths:
                if path.exists():
                    client_paths["vscode"] = str(path)
                    break
        
        elif self.system == "Windows":
            # Windows paths
            claude_path = Path("C:/Program Files/Claude/Claude.exe")
            if claude_path.exists():
                client_paths["claude_desktop"] = str(claude_path)
        
        elif self.system == "Linux":
            # Linux paths
            claude_path = Path("/usr/bin/claude")
            if claude_path.exists():
                client_paths["claude_desktop"] = str(claude_path)
        
        return client_paths
    
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
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header = QLabel("Client Configuration")
        header.setObjectName("headerLabel")
        layout.addWidget(header)
        
        # Intro text
        intro_label = QLabel(
            "This utility detects installed MCP clients and provides the configuration "
            "snippets needed to connect them to Hive MCP Gateway. "
            f"The server is running at {self.server_url}."
        )
        intro_label.setObjectName("introLabel")
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)
        
        # System info
        info_label = QLabel(
            f"mcp-proxy path: {self.mcp_proxy_path}\\n"
            f"System: {self.system}"
        )
        info_label.setObjectName("descriptionLabel")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Client selection
        client_layout = QFormLayout()
        client_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        self.client_combo = QComboBox()
        self.client_combo.setObjectName("clientCombo")
        self.client_combo.currentTextChanged.connect(self.on_client_changed)
        client_layout.addRow("Select Client:", self.client_combo)
        
        layout.addLayout(client_layout)
        
        # Tab widget for different configuration types
        self.config_tabs = QTabWidget()
        self.config_tabs.setObjectName("configTabs")
        
        # JSON Configuration Tab
        json_tab = self.create_json_tab()
        self.config_tabs.addTab(json_tab, "JSON Configuration")
        
        # Bash Commands Tab
        bash_tab = self.create_bash_tab()
        self.config_tabs.addTab(bash_tab, "Bash Commands")
        
        # File Paths Tab
        paths_tab = self.create_paths_tab()
        self.config_tabs.addTab(paths_tab, "File Paths")
        
        # Generic STDIO Tab
        stdio_tab = self.create_stdio_tab()
        self.config_tabs.addTab(stdio_tab, "Generic STDIO")
        
        layout.addWidget(self.config_tabs)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        
        self.copy_btn = QPushButton("📋 Copy to Clipboard")
        self.copy_btn.setObjectName("copyButton")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        buttons_layout.addWidget(self.copy_btn)
        
        self.install_btn = QPushButton("➕ Add to Client")
        self.install_btn.setObjectName("installButton")
        self.install_btn.clicked.connect(self.add_to_client)
        buttons_layout.addWidget(self.install_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("closeButton")
        self.close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.close_btn)
        
        layout.addLayout(buttons_layout)
    
    def create_json_tab(self) -> QWidget:
        """Create the JSON configuration tab."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Description
        desc_label = QLabel(
            "Add this JSON configuration to your client's MCP configuration file. "
            "The server address and path are dynamically populated based on your installation."
        )
        desc_label.setObjectName("descriptionLabel")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # JSON editor
        self.json_editor = QTextEdit()
        self.json_editor.setObjectName("jsonEditor")
        self.json_editor.setFont(QFont("JetBrains Mono", 10))
        self.json_editor.setPlaceholderText(
            "{\n"
            "  // JSON configuration will appear here\n"
            "}"
        )
        layout.addWidget(self.json_editor)
        
        return tab_widget
    
    def create_bash_tab(self) -> QWidget:
        """Create the Bash commands tab."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Description
        desc_label = QLabel(
            "Run these Bash commands to configure your client. "
            "Commands are customized based on your client type and installation."
        )
        desc_label.setObjectName("descriptionLabel")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Bash editor
        self.bash_editor = QTextEdit()
        self.bash_editor.setObjectName("bashEditor")
        self.bash_editor.setFont(QFont("JetBrains Mono", 10))
        self.bash_editor.setPlaceholderText(
            "# Bash commands will appear here\n"
            "# Example:\n"
            "# export MCP_SERVER_URL='http://localhost:8001'\n"
            "# mcp-client --server $MCP_SERVER_URL"
        )
        layout.addWidget(self.bash_editor)
        
        return tab_widget
    
    def create_paths_tab(self) -> QWidget:
        """Create the File Paths tab."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Description
        desc_label = QLabel(
            "These are the detected file paths for your system. "
            "Use these paths when manually configuring your clients."
        )
        desc_label.setObjectName("descriptionLabel")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Paths editor
        self.paths_editor = QTextEdit()
        self.paths_editor.setObjectName("pathsEditor")
        self.paths_editor.setFont(QFont("JetBrains Mono", 10))
        self.paths_editor.setReadOnly(True)
        layout.addWidget(self.paths_editor)
        
        return tab_widget
    
    def create_stdio_tab(self) -> QWidget:
        """Create the Generic STDIO tab."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Description
        desc_label = QLabel(
            "For clients that support STDIO transport, use this generic configuration. "
            "This is suitable for custom clients or those not listed in the presets."
        )
        desc_label.setObjectName("descriptionLabel")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # STDIO editor
        self.stdio_editor = QTextEdit()
        self.stdio_editor.setObjectName("stdioEditor")
        self.stdio_editor.setFont(QFont("JetBrains Mono", 10))
        self.stdio_editor.setPlaceholderText(
            "# STDIO configuration will appear here\n"
            "# Example:\n"
            "# {\n"
            "#   \"transport\": \"stdio\",\n"
            "#   \"command\": [\"hive-mcp-gateway\", \"--stdio\"]\n"
            "# }"
        )
        layout.addWidget(self.stdio_editor)
        
        return tab_widget
    
    def detect_installed_clients(self):
        """Detect installed MCP clients."""
        # Clear existing items
        self.client_combo.clear()
        
        # Add detected clients
        detected_clients = [
            ("Claude Code", "claude_code"),
            ("Claude Desktop", "claude_desktop"),
            ("Cursor IDE", "cursor_ide"),
            ("VS Code with Continue", "vscode_continue"),
            ("Qwen Code", "qwen_code"),
            ("Gemini CLI", "gemini_cli"),
            ("Custom Client", "custom")
        ]
        
        # Add clients to combo box
        for client_name, client_id in detected_clients:
            display_name = client_name
            if client_id in self.client_paths:
                display_name += " (Detected)"
            self.client_combo.addItem(display_name, client_id)
        
        # Select first item by default
        if detected_clients:
            self.client_combo.setCurrentIndex(0)
            self.update_configurations(detected_clients[0][1])
    
    def on_client_changed(self, client_name: str):
        """Handle client selection change."""
        client_id = self.client_combo.currentData()
        self.update_configurations(client_id)
    
    def update_configurations(self, client_id: str):
        """Update configuration displays based on selected client."""
        # JSON Configuration
        json_config = self.generate_json_config(client_id)
        self.json_editor.setPlainText(json_config)
        
        # Bash Commands
        bash_commands = self.generate_bash_commands(client_id)
        self.bash_editor.setPlainText(bash_commands)
        
        # File Paths
        file_paths = self.generate_file_paths_info(client_id)
        self.paths_editor.setPlainText(file_paths)
        
        # STDIO Configuration
        stdio_config = self.generate_stdio_config(client_id)
        self.stdio_editor.setPlainText(stdio_config)
    
    def generate_json_config(self, client_id: str) -> str:
        """Generate JSON configuration for the client."""
        if client_id in ["claude_desktop", "claude_code"]:
            return f'''{{
  "mcp": {{
    "servers": [
      {{
        "name": "Hive MCP Gateway",
        "command": "{self.mcp_proxy_path}",
        "args": ["--port", "{self.server_port}"],
        "type": "stdio"
      }}
    ]
  }}
}}'''
        elif client_id == "cursor_ide":
            return f'''{{
  "mcp": {{
    "gateway": "{self.server_url}",
    "transport": "http"
  }}
}}'''
        elif client_id == "vscode_continue":
            return f'''{{
  "continue": {{
    "mcpServers": {{
      "hive-gateway": {{
        "command": "{self.mcp_proxy_path}",
        "args": ["--port", "{self.server_port}"]
      }}
    }}
  }}
}}'''
        else:
            # Generic configuration
            return f'''{{
  "mcp": {{
    "server": "{self.server_url}",
    "command": "{self.mcp_proxy_path}",
    "args": ["--port", "{self.server_port}"]
  }}
}}'''
    
    def generate_bash_commands(self, client_id: str) -> str:
        """Generate Bash commands for the client."""
        if client_id == "claude_code":
            return f'''# Configure Claude Code to use Hive MCP Gateway
export CLAUDE_MCP_SERVER="{self.server_url}"
{self.mcp_proxy_path} --port {self.server_port}
echo "Claude Code configured to use Hive MCP Gateway at {self.server_url}"'''
        elif client_id == "gemini_cli":
            return f'''# Configure Gemini CLI to use Hive MCP Gateway
export GEMINI_MCP_GATEWAY="{self.server_url}"
echo "Gemini CLI configured to use Hive MCP Gateway at {self.server_url}"'''
        elif client_id == "claude_desktop":
            return f'''# Configure Claude Desktop
# Add the following to ~/.config/claude/desktop/settings.json:
# {{
#   "mcpServers": {{
#     "hive-gateway": {{
#       "command": "{self.mcp_proxy_path}",
#       "args": ["--port", "{self.server_port}"]
#     }}
#   }}
# }}'''
        else:
            return f'''# Generic configuration for MCP client
export MCP_SERVER_URL="{self.server_url}"
export MCP_SERVER_PATH="{self.mcp_proxy_path}"
{self.mcp_proxy_path} --port {self.server_port}
echo "MCP client configured to use Hive MCP Gateway at {self.server_url}"'''
    
    def generate_file_paths_info(self, client_id: str) -> str:
        """Generate file paths information."""
        info = [
            f"mcp-proxy path: {self.mcp_proxy_path}",
            f"Server URL: {self.server_url}",
            f"Server Port: {self.server_port}",
            f"System: {self.system}",
            f"User Home: {self.user_home}"
        ]
        
        if client_id in self.client_paths:
            info.append(f"Client Installation: {self.client_paths[client_id]}")
        
        # Add configuration file paths
        if self.system == "Darwin":  # macOS
            info.extend([
                "Configuration Paths:",
                f"  Claude Desktop: {self.user_home}/.config/claude/desktop/settings.json",
                f"  Claude Code: {self.user_home}/.config/claude-code/config.json",
                f"  VS Code: {self.user_home}/Library/Application Support/Code/User/settings.json"
            ])
        elif self.system == "Windows":
            info.extend([
                "Configuration Paths:",
                f"  Claude Desktop: {self.user_home}\\AppData\\Roaming\\Claude\\settings.json",
                f"  VS Code: {self.user_home}\\AppData\\Roaming\\Code\\User\\settings.json"
            ])
        elif self.system == "Linux":
            info.extend([
                "Configuration Paths:",
                f"  Claude Desktop: {self.user_home}/.config/claude/settings.json",
                f"  VS Code: {self.user_home}/.config/Code/User/settings.json"
            ])
        
        return "\\n".join(info)
    
    def generate_stdio_config(self, client_id: str) -> str:
        """Generate STDIO configuration for the client."""
        return f'''{{
  "transport": "stdio",
  "command": ["{self.mcp_proxy_path}", "--port", "{self.server_port}"],
  "name": "Hive MCP Gateway"
}}'''
    
    def copy_to_clipboard(self):
        """Copy current configuration to clipboard."""
        # Get current tab
        current_tab_index = self.config_tabs.currentIndex()
        current_tab_name = self.config_tabs.tabText(current_tab_index)
        
        # Get text from current editor
        if current_tab_name == "JSON Configuration":
            text = self.json_editor.toPlainText()
        elif current_tab_name == "Bash Commands":
            text = self.bash_editor.toPlainText()
        elif current_tab_name == "File Paths":
            text = self.paths_editor.toPlainText()
        elif current_tab_name == "Generic STDIO":
            text = self.stdio_editor.toPlainText()
        else:
            text = ""
        
        if text:
            clipboard = QApplication.clipboard()
            if clipboard:  # Add null check
                clipboard.setText(text)
                QMessageBox.information(self, "Copied", f"Configuration copied to clipboard!\n\nTab: {current_tab_name}")
            else:
                QMessageBox.warning(self, "Clipboard Error", "Could not access system clipboard.")
        else:
            QMessageBox.warning(self, "No Content", "No configuration content to copy.")
    
    def add_to_client(self):
        """Add configuration to client."""
        client_id = self.client_combo.currentData()
        client_name = self.client_combo.currentText()
        
        # This would be implemented based on the specific client
        # For now, just show a message
        QMessageBox.information(
            self, 
            "Add to Client", 
            f"Adding configuration to {client_name} is not yet implemented.\\n\\n"
            f"Please manually copy the configuration and add it to your client settings.\\n\\n"
            f"Server URL: {self.server_url}\\n"
            f"mcp-proxy path: {self.mcp_proxy_path}"
        )