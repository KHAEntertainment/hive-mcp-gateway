"""Enhanced credential management GUI for Hive MCP Gateway with new Hive Night theme."""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QLineEdit, QLabel, QTextEdit,
    QMessageBox, QInputDialog, QGroupBox, QCheckBox, QComboBox,
    QSplitter, QFrame, QHeaderView, QAbstractItemView, QDialog,
    QDialogButtonBox, QFormLayout, QSpinBox, QTextBrowser
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QBrush, QColor

from hive_mcp_gateway.services.credential_manager import (
    CredentialManager, CredentialType, CredentialEntry
)

logger = logging.getLogger(__name__)


class EnhancedAddCredentialDialog(QDialog):
    """Enhanced dialog for adding or editing credentials with new styling."""
    
    def __init__(self, parent=None, credential: Optional[CredentialEntry] = None):
        super().__init__(parent)
        self.credential = credential
        self.setWindowTitle("Add Credential" if credential is None else "Edit Credential")
        self.setModal(True)
        self.resize(500, 350)
        
        self.setup_ui()
        
        if credential:
            self.load_credential()
    
    def setup_ui(self):
        """Setup the dialog UI with new styling."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header = QLabel("Credential Management" if self.credential is None else "Edit Credential")
        header.setObjectName("dialogHeader")
        layout.addWidget(header)
        
        # Description text
        desc_text = QTextBrowser()
        desc_text.setObjectName("descriptionText")
        desc_text.setMaximumHeight(60)
        desc_text.setHtml("""
        <p><b>Secure Storage:</b> Secrets are stored securely via your OS's secret store (Keyring). 
        Environment variables are passed through to MCP configurations for easy maintenance.</p>
        """)
        desc_text.setOpenExternalLinks(False)
        layout.addWidget(desc_text)
        
        # Form layout
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        # Key field
        self.key_edit = QLineEdit()
        self.key_edit.setObjectName("keyEdit")
        self.key_edit.setPlaceholderText("e.g., EXA_API_KEY, REGION, LOG_LEVEL")
        form_layout.addRow("Key:", self.key_edit)
        
        # Value field
        self.value_edit = QLineEdit()
        self.value_edit.setObjectName("valueEdit")
        self.value_edit.setPlaceholderText("Enter the credential value")
        self.value_edit.setEchoMode(QLineEdit.EchoMode.Password if self.credential is None else QLineEdit.EchoMode.Normal)
        form_layout.addRow("Value:", self.value_edit)
        
        # Type selection
        self.type_combo = QComboBox()
        self.type_combo.setObjectName("typeCombo")
        self.type_combo.addItems(["Auto-detect", "Environment Variable", "Secret (Keyring)"])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        form_layout.addRow("Storage Type:", self.type_combo)
        
        # Description field
        self.description_edit = QTextEdit()
        self.description_edit.setObjectName("descriptionEdit")
        self.description_edit.setMaximumHeight(60)
        self.description_edit.setPlaceholderText("Optional description for this credential")
        form_layout.addRow("Description:", self.description_edit)
        
        layout.addWidget(form_widget)
        
        # Preview section
        preview_group = QGroupBox("Type Detection Preview")
        preview_group.setObjectName("previewGroup")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("Enter a key and value to see auto-detection results")
        self.preview_label.setObjectName("previewLabel")
        self.preview_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_label)
        
        layout.addWidget(preview_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Connect signals for real-time preview
        self.key_edit.textChanged.connect(self.update_preview)
        self.value_edit.textChanged.connect(self.update_preview)
    
    def load_credential(self):
        """Load existing credential data."""
        if not self.credential:
            return
        
        self.key_edit.setText(self.credential.key)
        self.value_edit.setText(self.credential.value)
        self.description_edit.setPlainText(self.credential.description or "")
        
        # Set type
        if self.credential.credential_type == CredentialType.SECRET:
            self.type_combo.setCurrentText("Secret (Keyring)")
        elif self.credential.credential_type == CredentialType.ENVIRONMENT:
            self.type_combo.setCurrentText("Environment Variable")
    
    def on_type_changed(self):
        """Handle type selection change."""
        self.update_preview()
    
    def update_preview(self):
        """Update the type detection preview."""
        key = self.key_edit.text().strip()
        value = self.value_edit.text().strip()
        
        if not key or not value:
            self.preview_label.setText("Enter a key and value to see auto-detection results")
            self.preview_label.setStyleSheet("color: #a0a3a8; font-style: italic;")
            return
        
        # Import here to avoid circular imports
        from hive_mcp_gateway.services.credential_manager import SensitivityDetector
        
        is_sensitive, reason = SensitivityDetector.is_sensitive(key, value)
        
        if self.type_combo.currentText() == "Auto-detect":
            detected_type = "Secret (Keyring)" if is_sensitive else "Environment Variable"
            self.preview_label.setText(f"Auto-detected as: {detected_type}\\nReason: {reason}")
            
            if is_sensitive:
                self.preview_label.setStyleSheet("color: #d9534f; font-weight: bold;")
            else:
                self.preview_label.setStyleSheet("color: #5cb85c; font-weight: bold;")
        else:
            selected_type = self.type_combo.currentText()
            self.preview_label.setText(f"Manual selection: {selected_type}")
            self.preview_label.setStyleSheet("color: #8c62ff; font-weight: bold;")
    
    def get_credential_data(self) -> Dict[str, Any]:
        """Get the credential data from the form."""
        key = self.key_edit.text().strip()
        value = self.value_edit.text().strip()
        description = self.description_edit.toPlainText().strip() or None
        
        # Determine credential type
        credential_type = None
        type_text = self.type_combo.currentText()
        
        if type_text == "Environment Variable":
            credential_type = CredentialType.ENVIRONMENT
        elif type_text == "Secret (Keyring)":
            credential_type = CredentialType.SECRET
        # Auto-detect leaves credential_type as None
        
        return {
            "key": key,
            "value": value,
            "credential_type": credential_type,
            "description": description
        }


class EnhancedCredentialTableWidget(QTableWidget):
    """Enhanced table widget for displaying credentials with new styling."""
    
    credential_changed = pyqtSignal()
    
    def __init__(self, credential_type: CredentialType, parent=None):
        super().__init__(parent)
        self.credential_type = credential_type
        self.credential_manager: Optional[CredentialManager] = None
        
        self.setup_table()
        self.setup_context_menu()
    
    def setup_table(self):
        """Setup the table structure with new styling."""
        # Column setup
        columns = ["Key", "Value", "Description", "Actions"]
        
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        self.setObjectName("credentialTable")
        
        # Table properties
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        
        # Column resizing
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Key
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Value
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Description
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # Actions
        
        # Set column widths
        self.setColumnWidth(0, 200)  # Key
        self.setColumnWidth(3, 120)  # Actions
        
        # Hide grid lines for cleaner look
        self.setShowGrid(False)
        
        # Set selection behavior
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    
    def setup_context_menu(self):
        """Setup context menu for the table."""
        # Implementation would go here
        pass


class EnhancedCredentialManagementWidget(QWidget):
    """Enhanced credential management widget with new Hive Night theme."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.credential_manager = CredentialManager()
        
        self.setup_ui()
        self.load_credentials()
    
    def setup_ui(self):
        """Setup the enhanced UI with new styling."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header = QLabel("Credential Management")
        header.setObjectName("headerLabel")
        layout.addWidget(header)
        
        # Description text
        desc_text = QTextBrowser()
        desc_text.setObjectName("descriptionText")
        desc_text.setMaximumHeight(80)
        desc_text.setHtml("""
        <p><b>Secure Storage:</b> Secrets are stored securely via your OS's secret store (Keyring). 
        Environment variables are passed through to MCP configurations for easy maintenance.</p>
        <p><b>Auto-Detect:</b> The system automatically detects whether entries should be stored as 
        environment variables or secrets based on naming patterns and sensitivity analysis.</p>
        """)
        desc_text.setOpenExternalLinks(False)
        layout.addWidget(desc_text)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        self.add_credential_btn = QPushButton("➕ Add Credential")
        self.add_credential_btn.setObjectName("addCredentialButton")
        self.add_credential_btn.clicked.connect(self.add_credential)
        buttons_layout.addWidget(self.add_credential_btn)
        
        self.import_btn = QPushButton("📥 Import from JSON")
        self.import_btn.setObjectName("importButton")
        self.import_btn.clicked.connect(self.import_credentials)
        buttons_layout.addWidget(self.import_btn)
        
        self.export_btn = QPushButton("📤 Export All")
        self.export_btn.setObjectName("exportButton")
        self.export_btn.clicked.connect(self.export_credentials)
        buttons_layout.addWidget(self.export_btn)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        # Tab widget for ENV vs Secrets
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("credentialTabs")
        
        # Environment Variables Tab
        self.env_table = EnhancedCredentialTableWidget(CredentialType.ENVIRONMENT)
        self.env_table.credential_changed.connect(self.on_credential_changed)
        self.tab_widget.addTab(self.env_table, "Environment Variables")
        
        # Secrets (Keyring) Tab
        self.secrets_table = EnhancedCredentialTableWidget(CredentialType.SECRET)
        self.secrets_table.credential_changed.connect(self.on_credential_changed)
        self.tab_widget.addTab(self.secrets_table, "Secrets (Keyring)")
        
        layout.addWidget(self.tab_widget)
        
        # Status bar
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.keyring_status = QLabel("Keyring: ✓ Available")
        self.keyring_status.setObjectName("keyringStatus")
        status_layout.addWidget(self.keyring_status)
        
        layout.addLayout(status_layout)
    
    def load_credentials(self):
        """Load credentials from the credential manager."""
        try:
            # Load environment variables
            env_credentials = self.credential_manager.list_credentials(CredentialType.ENVIRONMENT)
            self.populate_table(self.env_table, env_credentials)
            
            # Load secrets
            secret_credentials = self.credential_manager.list_credentials(CredentialType.SECRET)
            self.populate_table(self.secrets_table, secret_credentials)
            
            self.status_label.setText(f"Loaded {len(env_credentials)} environment variables and {len(secret_credentials)} secrets")
        except Exception as e:
            self.status_label.setText(f"Error loading credentials: {e}")
            logger.error(f"Error loading credentials: {e}")
    
    def populate_table(self, table: EnhancedCredentialTableWidget, credentials: List[CredentialEntry]):
        """Populate a table with credentials."""
        table.setRowCount(len(credentials))
        
        for row, credential in enumerate(credentials):
            # Key
            key_item = QTableWidgetItem(credential.key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 0, key_item)
            
            # Value (masked for secrets)
            if credential.credential_type == CredentialType.SECRET:
                value_text = "••••••••"  # Masked value
            else:
                value_text = credential.value
            
            value_item = QTableWidgetItem(value_text)
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 1, value_item)
            
            # Description
            desc_item = QTableWidgetItem(credential.description or "")
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 2, desc_item)
            
            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 4, 4, 4)
            actions_layout.setSpacing(2)
            
            edit_btn = QPushButton("✏️")
            edit_btn.setObjectName("editButton")
            edit_btn.setFixedSize(24, 24)
            edit_btn.clicked.connect(lambda checked, c=credential: self.edit_credential(c))
            actions_layout.addWidget(edit_btn)
            
            delete_btn = QPushButton("🗑️")
            delete_btn.setObjectName("deleteButton")
            delete_btn.setFixedSize(24, 24)
            delete_btn.clicked.connect(lambda checked, c=credential: self.delete_credential(c))
            actions_layout.addWidget(delete_btn)
            
            actions_layout.addStretch()
            actions_widget.setLayout(actions_layout)
            table.setCellWidget(row, 3, actions_widget)
    
    def add_credential(self):
        """Add a new credential."""
        dialog = EnhancedAddCredentialDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_credential_data()
                credential = CredentialEntry(
                    key=data["key"],
                    value=data["value"],
                    credential_type=data["credential_type"],
                    description=data["description"]
                )
                self.credential_manager.add_credential(credential)
                self.load_credentials()
                self.status_label.setText("Credential added successfully")
            except Exception as e:
                self.status_label.setText(f"Error adding credential: {e}")
                logger.error(f"Error adding credential: {e}")
    
    def edit_credential(self, credential: CredentialEntry):
        """Edit an existing credential."""
        dialog = EnhancedAddCredentialDialog(self, credential)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_credential_data()
                updated_credential = CredentialEntry(
                    key=data["key"],
                    value=data["value"],
                    credential_type=data["credential_type"],
                    description=data["description"]
                )
                self.credential_manager.update_credential(credential.key, updated_credential)
                self.load_credentials()
                self.status_label.setText("Credential updated successfully")
            except Exception as e:
                self.status_label.setText(f"Error updating credential: {e}")
                logger.error(f"Error updating credential: {e}")
    
    def delete_credential(self, credential: CredentialEntry):
        """Delete a credential."""
        reply = QMessageBox.question(
            self, 
            "Delete Credential",
            f"Are you sure you want to delete the credential '{credential.key}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.credential_manager.remove_credential(credential.key)
                self.load_credentials()
                self.status_label.setText("Credential deleted successfully")
            except Exception as e:
                self.status_label.setText(f"Error deleting credential: {e}")
                logger.error(f"Error deleting credential: {e}")
    
    def import_credentials(self):
        """Import credentials from JSON."""
        # Implementation would go here
        self.status_label.setText("Import functionality not yet implemented")
    
    def export_credentials(self):
        """Export all credentials to JSON."""
        # Implementation would go here
        self.status_label.setText("Export functionality not yet implemented")
    
    def on_credential_changed(self):
        """Handle credential change events."""
        self.load_credentials()