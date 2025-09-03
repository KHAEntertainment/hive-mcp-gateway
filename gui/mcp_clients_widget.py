"""MCP Clients widget for the Hive MCP Gateway."""

import os
import platform
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QStackedWidget, QTextEdit, QFrame, QApplication, QTabWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QClipboard

logger = logging.getLogger(__name__)


class MCPClientsWidget(QWidget):
    """Widget for displaying MCP client configuration and instructions."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.server_url = "http://localhost:8001"  # Default server URL
        self.server_port = 8001  # Default port
        self.mcp_proxy_path = "mcp-proxy"  # Default proxy path
        self.system = "Unknown"  # Default system
        self.user_home = Path.home()  # Default user home
        self.client_paths = {}  # Default client paths
        
        self.load_stylesheet()
        self.setup_ui()
        self.detect_system_info()
    
    def load_stylesheet(self):
        """Load and apply the Hive Night theme stylesheet."""
        try:
            stylesheet_path = "gui/assets/styles.qss"
            with open(stylesheet_path, "r") as f:
                stylesheet = f.read()
                self.setStyleSheet(stylesheet)
                logger.info("Loaded stylesheet for MCP Clients widget")
        except FileNotFoundError:
            logger.warning(f"Stylesheet not found at {stylesheet_path}")
        except Exception as e:
            logger.error(f"Error loading stylesheet: {e}")
    
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
            if isinstance(path, Path) and path.exists() and path.is_file():
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
                Path("/usr/local/bin/claude-code"),
                self.user_home / ".nvm/versions/node/v*/bin/claude-code"
            ]
            for path in claude_code_paths:
                if isinstance(path, Path) and path.exists():
                    client_paths["claude_code"] = str(path)
                    break
            
            # VS Code
            vscode_paths = [
                Path("/Applications/Visual Studio Code.app"),
                self.user_home / "Applications/Visual Studio Code.app"
            ]
            for path in vscode_paths:
                if isinstance(path, Path) and path.exists():
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
    
    def setup_ui(self):
        """Setup the MCP clients widget UI."""
        layout = QVBoxLayout(self)
        
        # Header text
        header_text = QLabel("MCP Client Integration")
        header_text.setObjectName("clientsHeader")
        layout.addWidget(header_text)
        
        # Info text
        info_text = QLabel("Configure your MCP-compatible clients to connect to Hive MCP Gateway. Select your client below to get specific configuration instructions.")
        info_text.setObjectName("clientsInfo")
        info_text.setWordWrap(True)
        layout.addWidget(info_text)
        
        # Client selection pills
        pills_layout = QHBoxLayout()
        pills_layout.setSpacing(10)
        pills_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        clients = [
            ("Claude Desktop", "claude_desktop"),
            ("Claude Code", "claude_code"),
            ("Gemini CLI", "gemini_cli"),
            ("VS Code (Continue)", "vscode_continue"),
            ("Cursor IDE", "cursor_ide"),
            ("Generic Stdio", "generic_stdio")
        ]
        
        self.client_buttons = {}
        for client_name, client_id in clients:
            button = QPushButton(client_name)
            button.setObjectName("clientTabButton")
            button.setCheckable(True)
            button.setProperty("client_id", client_id)
            button.clicked.connect(lambda checked, cid=client_id: self.switch_client(cid))
            pills_layout.addWidget(button)
            self.client_buttons[client_id] = button
        
        pills_layout.addStretch()
        layout.addLayout(pills_layout)
        
        # Client content area
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("clientContentStack")
        
        # Create content widgets for each client
        for client_id, client_name in [(c[1], c[0]) for c in clients]:
            content_widget = self.create_client_content(client_id, client_name)
            content_widget.setProperty("client_id", client_id)
            self.content_stack.addWidget(content_widget)
        
        layout.addWidget(self.content_stack)
        
        # Select first client by default
        if self.client_buttons:
            first_button = list(self.client_buttons.values())[0]
            first_button.setChecked(True)
            self.switch_client(list(self.client_buttons.keys())[0])
    
    def create_client_content(self, client_id: str, client_name: str) -> QWidget:
        """Create content widget for a specific client."""
        widget = QWidget()
        widget.setProperty("client_id", client_id)
        layout = QVBoxLayout(widget)
        
        # Client instructions
        instructions = QLabel(self.get_client_instructions(client_id))
        instructions.setWordWrap(True)
        instructions.setObjectName("instructionsLabel")
        layout.addWidget(instructions)
        
        # Configuration section with tabs
        config_tabs = QTabWidget()
        config_tabs.setObjectName("configTabs")
        
        # JSON Configuration Tab
        json_tab = self.create_json_tab(client_id)
        config_tabs.addTab(json_tab, "JSON Configuration")
        
        # Bash Commands Tab
        bash_tab = self.create_bash_tab(client_id)
        config_tabs.addTab(bash_tab, "Bash Commands")
        
        # File Paths Tab
        paths_tab = self.create_paths_tab(client_id)
        config_tabs.addTab(paths_tab, "File Paths")
        
        # Generic STDIO Tab
        stdio_tab = self.create_stdio_tab(client_id)
        config_tabs.addTab(stdio_tab, "Generic STDIO")
        
        layout.addWidget(config_tabs)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        
        copy_button = QPushButton("📋 Copy to Clipboard")
        copy_button.setObjectName("copyButton")
        copy_button.clicked.connect(lambda: self.copy_to_clipboard(client_id, config_tabs))
        buttons_layout.addWidget(copy_button)
        
        add_button = QPushButton("➕ Add to Client")
        add_button.setObjectName("installButton")
        add_button.clicked.connect(lambda: self.add_to_client(client_id))
        buttons_layout.addWidget(add_button)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        # Detected footnote
        footnote = QLabel(self.get_footnote_text(client_id))
        footnote.setObjectName("footnoteKey")
        layout.addWidget(footnote)
        
        layout.addStretch()
        return widget
    
    def create_json_tab(self, client_id: str) -> QWidget:
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
        
        # JSON snippet block
        json_block = QTextEdit()
        json_block.setObjectName("codeBlock")
        json_block.setReadOnly(True)
        json_block.setText(self.get_json_snippet(client_id))
        layout.addWidget(json_block)
        
        return tab_widget
    
    def create_bash_tab(self, client_id: str) -> QWidget:
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
        
        # Bash command block
        bash_block = QTextEdit()
        bash_block.setObjectName("codeBlock")
        bash_block.setReadOnly(True)
        bash_block.setText(self.get_bash_command(client_id))
        layout.addWidget(bash_block)
        
        return tab_widget
    
    def create_paths_tab(self, client_id: str) -> QWidget:
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
        
        # Paths information block
        paths_block = QTextEdit()
        paths_block.setObjectName("codeBlock")
        paths_block.setReadOnly(True)
        paths_block.setText(self.get_file_paths_info(client_id))
        layout.addWidget(paths_block)
        
        return tab_widget
    
    def create_stdio_tab(self, client_id: str) -> QWidget:
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
        
        # STDIO configuration block
        stdio_block = QTextEdit()
        stdio_block.setObjectName("codeBlock")
        stdio_block.setReadOnly(True)
        stdio_block.setText(self.get_stdio_config(client_id))
        layout.addWidget(stdio_block)
        
        return tab_widget
    
    def get_file_paths_info(self, client_id: str) -> str:
        """Get file paths information for a specific client."""
        info_lines = []
        
        # System information
        info_lines.append(f"System: {self.system}")
        info_lines.append(f"User Home: {self.user_home}")
        info_lines.append(f"mcp-proxy path: {self.mcp_proxy_path}")
        info_lines.append(f"Server URL: {self.server_url}")
        info_lines.append(f"Server Port: {self.server_port}")
        
        if client_id in self.client_paths:
            info_lines.append(f"Client Installation: {self.client_paths[client_id]}")
        
        # Add configuration file paths based on system
        if self.system == "Darwin":  # macOS
            info_lines.extend([
                "",
                "Configuration Paths:",
                f"  Claude Desktop: {self.user_home}/.config/claude/desktop/settings.json",
                f"  Claude Code: {self.user_home}/.config/claude-code/config.json",
                f"  VS Code: {self.user_home}/Library/Application Support/Code/User/settings.json"
            ])
        elif self.system == "Windows":
            info_lines.extend([
                "",
                "Configuration Paths:",
                f"  Claude Desktop: {self.user_home}\\AppData\\Roaming\\Claude\\settings.json",
                f"  VS Code: {self.user_home}\\AppData\\Roaming\\Code\\User\\settings.json"
            ])
        elif self.system == "Linux":
            info_lines.extend([
                "",
                "Configuration Paths:",
                f"  Claude Desktop: {self.user_home}/.config/claude/settings.json",
                f"  VS Code: {self.user_home}/.config/Code/User/settings.json"
            ])
        
        return "\n".join(info_lines)
    
    def get_stdio_config(self, client_id: str) -> str:
        """Get STDIO configuration for a specific client."""
        return f'''{{
  "transport": "stdio",
  "command": ["{self.mcp_proxy_path}", "--port", "{self.server_port}"],
  "name": "Hive MCP Gateway"
}}'''
    
    def get_path_info(self, client_id: str) -> str:
        """Get dynamic path information for a client."""
        info_lines = []
        
        if self.mcp_proxy_path:
            info_lines.append(f"mcp-proxy path: {self.mcp_proxy_path}")
        
        if client_id in self.client_paths:
            info_lines.append(f"Client installation: {self.client_paths[client_id]}")
        
        info_lines.append(f"Server URL: {self.server_url}")
        
        return "\n".join(info_lines)
    
    def get_client_instructions(self, client_id: str) -> str:
        """Get instructions for a specific client."""
        instructions = {
            "claude_desktop": f"To integrate with Claude Desktop, add the following configuration to your settings. The server will be available at {self.server_url}.",
            "claude_code": f"To integrate with Claude Code, use the OAuth setup wizard or manually configure the connection. The server will be available at {self.server_url}.",
            "gemini_cli": f"To integrate with Gemini CLI, ensure the CLI tool is installed and configured with OAuth. The server will be available at {self.server_url}.",
            "vscode_continue": f"To integrate with VS Code using Continue, install the extension and add this configuration. The server will be available at {self.server_url}.",
            "cursor_ide": f"To integrate with Cursor IDE, add this configuration to your Cursor settings. The server will be available at {self.server_url}.",
            "generic_stdio": f"For generic stdio-based MCP clients, use this standard configuration template. The server will be available at {self.server_url}."
        }
        return instructions.get(client_id, f"Instructions for this client are not available. The server will be available at {self.server_url}.")
    
    def get_json_snippet(self, client_id: str) -> str:
        """Get JSON snippet for a specific client with real values."""
        if client_id in ["claude_desktop", "claude_code", "cursor_ide"]:
            return f'''{{
  "mcpServers": {{
    "hive-gateway": {{
      "command": "{self.mcp_proxy_path}",
      "args": ["--port", "{self.server_port}"]
    }}
  }}
}}'''
        elif client_id == "vscode_continue":
            return f'''{{
  "continue.mcpServers": {{
    "hive-gateway": {{
      "command": "{self.mcp_proxy_path}",
      "args": ["--port", "{self.server_port}"]
    }}
  }}
}}'''
        elif client_id == "gemini_cli":
            return f'''# Add to your Gemini configuration
mcp-server hive-gateway --command {self.mcp_proxy_path} --args "--port {self.server_port}"'''
        elif client_id == "generic_stdio":
            return f'''{{
  "mcpServers": {{
    "hive-gateway": {{
      "command": "{self.mcp_proxy_path}",
      "args": ["--port", "{self.server_port}"]
    }}
  }}
}}'''
        else:
            return "{}"
    
    def get_bash_command(self, client_id: str) -> str:
        """Get BASH command for a specific client with real values."""
        commands = {
            "claude_desktop": f'''# Configuration path: ~/.config/claude/desktop/settings.json
# Add the following to your Claude Desktop configuration:
echo 'Configuration for Claude Desktop at {self.server_url}' ''',
            "claude_code": f"{self.mcp_proxy_path} --port {self.server_port}",
            "gemini_cli": f"export MCP_SERVER_HIVE_GATEWAY='{self.mcp_proxy_path} --port {self.server_port}'",
            "vscode_continue": f'''code --install-extension continue.continue
# Add the following to your VS Code settings.json:
# {{
#   "continue.mcpServers": {{
#     "hive-gateway": {{
#       "command": "{self.mcp_proxy_path}",
#       "args": ["--port", "{self.server_port}"]
#     }}
#   }}
# }}''',
            "cursor_ide": f'''# Add the following to your Cursor IDE settings:
# {{
#   "mcpServers": {{
#     "hive-gateway": {{
#       "command": "{self.mcp_proxy_path}",
#       "args": ["--port", "{self.server_port}"]
#     }}
#   }}
# }}''',
            "generic_stdio": f"export MCP_SERVER_HIVE_GATEWAY='{self.mcp_proxy_path} --port {self.server_port}'"
        }
        return commands.get(client_id, f"# No BASH command available for this client. Server at {self.server_url}")
    
    def get_footnote_text(self, client_id: str) -> str:
        """Get footnote text for a specific client."""
        detected_status = {}
        
        if "claude_desktop" in self.client_paths:
            detected_status["claude_desktop"] = "💡 Claude Desktop installation detected"
        else:
            detected_status["claude_desktop"] = "⚠️ Claude Desktop not detected"
            
        if "claude_code" in self.client_paths:
            detected_status["claude_code"] = "💡 Claude Code installation detected"
        else:
            detected_status["claude_code"] = "⚠️ Claude Code not detected"
            
        if "vscode" in self.client_paths:
            detected_status["vscode_continue"] = "💡 VS Code installation detected"
        else:
            detected_status["vscode_continue"] = "⚠️ VS Code not detected"
        
        # Default messages
        footnotes = {
            "claude_desktop": detected_status.get("claude_desktop", "Installation status unknown"),
            "claude_code": detected_status.get("claude_code", "Installation status unknown"),
            "gemini_cli": "💡 Gemini CLI tool detection not implemented",
            "vscode_continue": detected_status.get("vscode_continue", "Installation status unknown"),
            "cursor_ide": "💡 Cursor IDE detection not implemented",
            "generic_stdio": "💡 Generic stdio configuration - adapt to your client"
        }
        return footnotes.get(client_id, "Installation status unknown")
    
    def switch_client(self, client_id: str):
        """Switch to display content for a specific client."""
        # Uncheck all buttons except the selected one
        for cid, button in self.client_buttons.items():
            if cid != client_id:
                button.setChecked(False)
        
        # Show the corresponding content
        for i in range(self.content_stack.count()):
            widget = self.content_stack.widget(i)
            if widget and widget.property("client_id") == client_id:
                self.content_stack.setCurrentIndex(i)
                break
    
    def copy_to_clipboard(self, client_id: str, config_tabs: QTabWidget):
        """Copy the current configuration to clipboard."""
        try:
            # Get current tab information
            current_tab_index = config_tabs.currentIndex()
            current_tab_name = config_tabs.tabText(current_tab_index)
            
            # Get text from current tab
            current_tab_widget = config_tabs.widget(current_tab_index)
            if current_tab_widget and hasattr(current_tab_widget, 'layout'):
                layout = current_tab_widget.layout()
                if layout and hasattr(layout, 'count') and hasattr(layout, 'itemAt'):
                    if layout.count() > 1:
                        # Get the QTextEdit widget (should be the second widget in layout)
                        text_edit = None
                        for j in range(layout.count()):
                            item = layout.itemAt(j)
                            if item and hasattr(item, 'widget') and item.widget() and isinstance(item.widget(), QTextEdit):
                                text_edit = item.widget()
                                break
                        
                        if text_edit and isinstance(text_edit, QTextEdit):
                            text = text_edit.toPlainText()
                            if text:
                                clipboard = QApplication.clipboard()
                                if clipboard:
                                    clipboard.setText(text)
                                    from PyQt6.QtWidgets import QMessageBox
                                    QMessageBox.information(self, "Copied", f"Configuration copied to clipboard!\n\nTab: {current_tab_name}")
                                    return
        except Exception as e:
            # Ignore errors and use fallback
            pass
        
        # Fallback if we can't get the specific tab content
        # Get current JSON and BASH content
        json_content = self.get_json_snippet(client_id)
        bash_content = self.get_bash_command(client_id)
        
        # Combine content
        content = f"JSON Configuration:\n{json_content}\n\nBASH Command:\n{bash_content}"
        
        try:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(content)
        except Exception:
            pass
    
    def add_to_client(self, client_id: str):
        """Add configuration to client (placeholder for actual implementation)."""
        # This would be implemented based on the specific client
        # For now, just show a message
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, 
            "Add to Client", 
            f"Adding configuration to {client_id} is not yet implemented.\n\n"
            f"Please manually copy the configuration and add it to your client settings.\n\n"
            f"Server URL: {self.server_url}\n"
            f"mcp-proxy path: {self.mcp_proxy_path}"
        )