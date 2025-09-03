"""LLM Configuration GUI following the new Hive Night theme design."""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, 
    QLineEdit, QLabel, QMessageBox, QGroupBox, QCheckBox, QComboBox,
    QFrame, QTextEdit, QSpacerItem, QSizePolicy, QTabWidget, QStackedWidget,
    QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from hive_mcp_gateway.services.llm_client_manager import (
    LLMProvider, AuthMethod, LLMConfig, LLMClientManager
)
from hive_mcp_gateway.services.credential_manager import CredentialManager, CredentialType
from hive_mcp_gateway.services.ide_detector import IDEDetector, IDEType
from hive_mcp_gateway.services.claude_code_sdk import ClaudeCodeSDK
from hive_mcp_gateway.services.gemini_cli_sdk import GeminiCLISDK

logger = logging.getLogger(__name__)


class LLMConfigWidget(QWidget):
    """LLM configuration widget following the new Hive Night theme design."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.credential_manager = CredentialManager()
        self.ide_detector = IDEDetector()
        
        # Initialize SDK integrations
        self.claude_code_sdk = ClaudeCodeSDK(self.credential_manager)
        self.gemini_cli_sdk = GeminiCLISDK(self.credential_manager)
        
        # Initialize LLM manager 
        try:
            self.llm_manager = LLMClientManager(None, self.credential_manager)
        except Exception as e:
            logger.error(f"Failed to initialize LLM manager: {e}")
            self.llm_manager = None
        
        self.setup_ui()
        self.detect_oauth_providers()
        self.load_existing_config()
    
    def setup_ui(self):
        """Setup the new UI following the Hive Night theme."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header = QLabel("LLM Provider Configuration")
        header.setObjectName("headerLabel")
        layout.addWidget(header)
        
        # Intro text
        intro_label = QLabel("Hive MCP Gateway uses an Internal LLM agent to inspect, organize, and route your tool calls.")
        intro_label.setObjectName("introLabel")
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)
        
        # Authentication tabs (CLI vs API)
        self.auth_tabs = QTabWidget()
        self.auth_tabs.setObjectName("authTabs")
        
        # CLI Authentication Tab
        cli_tab = self.create_cli_auth_tab()
        self.auth_tabs.addTab(cli_tab, "CLI Authentication")
        
        # API Authentication Tab
        api_tab = self.create_api_auth_tab()
        self.auth_tabs.addTab(api_tab, "API Authentication")
        
        layout.addWidget(self.auth_tabs)
        
        # Action buttons
        self.setup_action_buttons(layout)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def create_cli_auth_tab(self) -> QWidget:
        """Create the CLI Authentication tab."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setSpacing(15)
        
        # Provider selection
        provider_layout = QFormLayout()
        provider_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        self.provider_combo = QComboBox()
        self.provider_combo.setObjectName("providerCombo")
        self.provider_combo.addItems(["Claude Code (⚠️ Not Detected)", "Gemini CLI (✅ Detected)"])
        provider_layout.addRow("Provider Type:", self.provider_combo)
        
        # Description
        desc_label = QLabel("Uses OAuth Authentication from selected CLI app.")
        desc_label.setObjectName("descriptionLabel")
        desc_label.setWordWrap(True)
        provider_layout.addRow("", desc_label)
        
        layout.addLayout(provider_layout)
        
        # Override Paths Section
        paths_group = QGroupBox("Override Paths")
        paths_group.setObjectName("pathsGroup")
        paths_layout = QVBoxLayout(paths_group)
        
        # Note
        note_label = QLabel("If left blank, defaults will be used.")
        note_label.setObjectName("descriptionLabel")
        note_label.setWordWrap(True)
        paths_layout.addWidget(note_label)
        
        # Path overrides form
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        # Installation path
        self.cli_path_edit = QLineEdit()
        self.cli_path_edit.setObjectName("pathEdit")
        self.cli_path_edit.setPlaceholderText("e.g., /opt/claude-code")
        form_layout.addRow("Install Path:", self.cli_path_edit)
        
        # OAuth credentials path
        self.oauth_path_edit = QLineEdit()
        self.oauth_path_edit.setObjectName("pathEdit")
        self.oauth_path_edit.setPlaceholderText("e.g., ~/.config/claude/tokens.json")
        form_layout.addRow("OAuth Path:", self.oauth_path_edit)
        
        paths_layout.addLayout(form_layout)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)
        
        detect_btn = QPushButton("🔍 Auto-Detect")
        detect_btn.setObjectName("detectButton")
        detect_btn.clicked.connect(self.auto_detect_paths)
        button_layout.addWidget(detect_btn)
        
        guide_btn = QPushButton("⚙️ Guide")
        guide_btn.setObjectName("guideButton")
        guide_btn.clicked.connect(self.show_guide)
        button_layout.addWidget(guide_btn)
        
        button_layout.addStretch()
        paths_layout.addLayout(button_layout)
        
        layout.addWidget(paths_group)
        layout.addStretch()
        
        return tab_widget
    
    def create_api_auth_tab(self) -> QWidget:
        """Create the API Authentication tab."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setSpacing(15)
        
        # Provider selection with pills
        provider_label = QLabel("Provider:")
        provider_label.setObjectName("label")
        layout.addWidget(provider_label)
        
        # Provider pills
        self.pill_group = QButtonGroup()
        self.pill_group.setExclusive(True)
        
        pill_layout = QHBoxLayout()
        pill_layout.setSpacing(6)
        pill_layout.setContentsMargins(0, 0, 0, 12)
        
        providers = ["OpenAI", "Anthropic", "OpenRouter", "Custom"]
        self.pill_buttons = []
        
        for i, provider in enumerate(providers):
            pill_btn = QPushButton(provider)
            pill_btn.setObjectName("pillButton")
            pill_btn.setCheckable(True)
            if i == 0:  # Default to OpenAI
                pill_btn.setChecked(True)
            self.pill_group.addButton(pill_btn)
            self.pill_buttons.append(pill_btn)
            pill_layout.addWidget(pill_btn)
        
        pill_layout.addStretch()
        layout.addLayout(pill_layout)
        
        # API Key
        api_key_layout = QFormLayout()
        api_key_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setObjectName("apiKeyEdit")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("Enter your API key...")
        api_key_layout.addRow("API Key:", self.api_key_edit)
        
        # Key note
        key_note = QLabel("Stored securely in Apple Keychain.")
        key_note.setObjectName("keyNoteLabel")
        key_note.setWordWrap(True)
        api_key_layout.addRow("", key_note)
        
        layout.addLayout(api_key_layout)
        
        # Base URL
        base_url_layout = QFormLayout()
        base_url_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setObjectName("input")
        self.base_url_edit.setText("https://api.openai.com/v1")
        base_url_layout.addRow("Base URL:", self.base_url_edit)
        
        layout.addLayout(base_url_layout)
        layout.addStretch()
        
        return tab_widget
    
    def setup_action_buttons(self, layout):
        """Setup action buttons with proper styling."""
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        self.save_button = QPushButton("💾 Save Configuration")
        self.save_button.setObjectName("saveButton")
        self.save_button.clicked.connect(self.save_configuration)
        buttons_layout.addWidget(self.save_button)
        
        self.test_button = QPushButton("🧪 Test Connection")
        self.test_button.setObjectName("testButton")
        self.test_button.clicked.connect(self.test_connection)
        buttons_layout.addWidget(self.test_button)
        
        self.help_button = QPushButton("❓ Help")
        self.help_button.setObjectName("helpButton")
        self.help_button.clicked.connect(self.show_help)
        buttons_layout.addWidget(self.help_button)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
    
    def auto_detect_paths(self):
        """Auto-detect CLI and OAuth paths."""
        self.status_label.setText("Auto-detecting paths...")
        # Implementation would go here
        pass
    
    def show_guide(self):
        """Show setup guide."""
        # Implementation would go here
        pass
    
    def detect_oauth_providers(self):
        """Detect installed OAuth providers."""
        # Implementation would go here
        pass
    
    def load_existing_config(self):
        """Load existing LLM configuration."""
        # Implementation would go here
        pass
    
    def detect_provider(self, provider_key: str):
        """Detect a specific provider."""
        # Implementation would go here
        pass
    
    def show_setup_instructions(self, provider_key: str):
        """Show setup instructions for a provider."""
        # Implementation would go here
        pass
    
    def on_provider_changed(self, provider: str):
        """Handle provider selection change."""
        # Implementation would go here
        pass
    
    def load_preset(self, preset: str):
        """Load a provider preset."""
        # Implementation would go here
        pass
    
    def save_configuration(self):
        """Save the LLM configuration."""
        # Implementation would go here
        pass
    
    def test_connection(self):
        """Test the LLM connection."""
        # Implementation would go here
        pass
    
    def show_help(self):
        """Show help information."""
        # Implementation would go here
        pass