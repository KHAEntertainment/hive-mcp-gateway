"""Credential management GUI for Hive MCP Gateway with ENV/Secrets tabs."""

import json
import logging
from typing import Optional, Dict, Any, List, Set
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QLineEdit, QLabel, QTextEdit,
    QMessageBox, QInputDialog, QGroupBox, QCheckBox, QComboBox,
    QSplitter, QFrame, QHeaderView, QAbstractItemView, QDialog,
    QDialogButtonBox, QFormLayout, QSpinBox, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QBrush, QColor

from hive_mcp_gateway.services.credential_manager import (
    CredentialManager, CredentialType, CredentialEntry
)

logger = logging.getLogger(__name__)


class AddCredentialDialog(QDialog):
    """Dialog for adding or editing credentials."""
    
    def __init__(self, parent=None, credential: Optional[CredentialEntry] = None, config_manager=None):
        super().__init__(parent)
        self.credential = credential
        self.config_manager = config_manager
        self.setWindowTitle("Add Credential" if credential is None else "Edit Credential")
        self.setModal(True)
        self.resize(500, 380)  # Increased height to accommodate server selection
        
        self.load_stylesheet()
        self.setup_ui()
        
        if credential:
            self.load_credential()
    
    def load_stylesheet(self):
        """Load and apply the Hive Night theme stylesheet."""
        try:
            # Try to load from absolute path first
            stylesheet_path = Path(__file__).parent / "assets" / "styles.qss"
            
            # If not found, try relative path
            if not stylesheet_path.exists():
                stylesheet_path = "gui/assets/styles.qss"
                
            with open(stylesheet_path, "r") as f:
                stylesheet = f.read()
                self.setStyleSheet(stylesheet)
        except FileNotFoundError:
            logger.warning("Stylesheet not found")
        except Exception as e:
            logger.error(f"Error loading stylesheet: {e}")
    
    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Form layout
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        
        # Key field
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("e.g., EXA_API_KEY, REGION, LOG_LEVEL")
        form_layout.addRow("Key:", self.key_edit)
        
        # Value field
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("Enter the credential value")
        form_layout.addRow("Value:", self.value_edit)
        
        # Type selection
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Auto-detect", "Environment Variable", "Secret (Keyring)"])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        form_layout.addRow("Storage Type:", self.type_combo)
        
        # Server association
        server_widget = QWidget()
        server_layout = QVBoxLayout(server_widget)
        server_layout.setContentsMargins(0, 0, 0, 0)
        
        server_label = QLabel("Server Association:")
        server_label.setToolTip("Select which MCP servers can use this credential")
        server_layout.addWidget(server_label)
        
        self.server_list = QListWidget()
        self.server_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        server_layout.addWidget(self.server_list)
        
        # Add SYSTEM option
        system_item = QListWidgetItem("SYSTEM (Hive MCP Gateway)")
        self.server_list.addItem(system_item)
        
        # Load servers from config if available
        self.load_server_list()
        
        form_layout.addRow("", server_widget)
        
        # Description field
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        self.description_edit.setPlaceholderText("Optional description for this credential")
        form_layout.addRow("Description:", self.description_edit)
        
        layout.addWidget(form_widget)
        
        # Preview section
        preview_group = QGroupBox("Type Detection Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("Enter a key and value to see auto-detection results")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("color: #666; font-style: italic;")
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
    
    def on_type_changed(self):
        """Handle type selection change."""
        self.update_preview()
    
    def update_preview(self):
        """Update the type detection preview."""
        key = self.key_edit.text().strip()
        value = self.value_edit.text().strip()
        
        if not key or not value:
            self.preview_label.setText("Enter a key and value to see auto-detection results")
            self.preview_label.setStyleSheet("color: #666; font-style: italic;")
            return
        
        # Import here to avoid circular imports
        from hive_mcp_gateway.services.credential_manager import SensitivityDetector
        
        is_sensitive, reason = SensitivityDetector.is_sensitive(key, value)
        
        if self.type_combo.currentText() == "Auto-detect":
            detected_type = "Secret (Keyring)" if is_sensitive else "Environment Variable"
            self.preview_label.setText(f"Auto-detected as: {detected_type}\nReason: {reason}")
            
            if is_sensitive:
                self.preview_label.setStyleSheet("color: #d32f2f; font-weight: bold;")
            else:
                self.preview_label.setStyleSheet("color: #388e3c; font-weight: bold;")
        else:
            selected_type = self.type_combo.currentText()
            self.preview_label.setText(f"Manual selection: {selected_type}")
            self.preview_label.setStyleSheet("color: #1976d2; font-weight: bold;")
    
    def load_server_list(self):
        """Load MCP server list from config manager."""
        if not self.config_manager:
            return
            
        try:
            servers = self.config_manager.get_backend_servers()
            
            for server_name in servers.keys():
                item = QListWidgetItem(server_name)
                self.server_list.addItem(item)
                
        except Exception as e:
            logger.error(f"Failed to load server list: {e}")
            
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
            
        # Select servers in list
        if hasattr(self.credential, 'server_ids') and self.credential.server_ids and self.server_list is not None:
            for i in range(self.server_list.count()):
                item = self.server_list.item(i)
                if item is None:
                    continue
                    
                if item.text() == "SYSTEM (Hive MCP Gateway)":
                    # Select SYSTEM if no server IDs (legacy behavior)
                    if not self.credential.server_ids:
                        item.setSelected(True)
                elif item.text() in self.credential.server_ids:
                    item.setSelected(True)
    
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
        
        # Get selected servers
        server_ids = set()
        for item in self.server_list.selectedItems():
            text = item.text()
            # Skip the SYSTEM option when building server_ids
            if text != "SYSTEM (Hive MCP Gateway)":
                server_ids.add(text)
        
        return {
            "key": key,
            "value": value,
            "credential_type": credential_type,
            "description": description,
            "server_ids": server_ids
        }


class CredentialTableWidget(QTableWidget):
    """Custom table widget for displaying credentials."""
    
    credential_changed = pyqtSignal()
    
    def __init__(self, credential_type: CredentialType, parent=None):
        super().__init__(parent)
        self.credential_type = credential_type
        self.credential_manager: Optional[CredentialManager] = None
        
        self.setup_table()
        self.setup_context_menu()
    
    def setup_table(self):
        """Setup the table structure."""
        # Column setup
        columns = ["Key", "Value", "Description", "Server", "Actions"]
        
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        
        # Table properties
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        
        # Column resizing
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Key
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Value
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Description
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # Server
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # Actions
        
        # Set column widths
        self.setColumnWidth(0, 150)  # Key
        self.setColumnWidth(3, 120)  # Server
        self.setColumnWidth(4, 100)  # Actions
    
    def setup_context_menu(self):
        """Setup context menu."""
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def show_context_menu(self, position):
        """Show context menu."""
        from PyQt6.QtWidgets import QMenu
        
        menu = QMenu(self)
        
        # Edit action
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(self.edit_selected)
        
        # Delete action
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected)
        
        menu.addSeparator()
        
        # Copy actions
        copy_key_action = menu.addAction("Copy Key")
        copy_key_action.triggered.connect(self.copy_key)
        
        copy_value_action = menu.addAction("Copy Value")
        copy_value_action.triggered.connect(self.copy_value)
        
        # Migrate action (if applicable)
        if self.credential_type == CredentialType.ENVIRONMENT:
            menu.addSeparator()
            migrate_action = menu.addAction("Move to Secrets")
            migrate_action.triggered.connect(self.migrate_to_secrets)
        elif self.credential_type == CredentialType.SECRET:
            menu.addSeparator()
            migrate_action = menu.addAction("Move to Environment")
            migrate_action.triggered.connect(self.migrate_to_environment)
        
        # Show menu
        if self.rowCount() > 0:
            menu.exec(self.mapToGlobal(position))
    
    def edit_selected(self):
        """Edit the selected credential."""
        current_row = self.currentRow()
        if current_row >= 0:
            key = self.item(current_row, 0).text()
            if self.credential_manager:
                credential = self.credential_manager.get_credential(key)
                if credential:
                    self.edit_credential(credential)
    
    def delete_selected(self):
        """Delete the selected credential."""
        current_row = self.currentRow()
        if current_row >= 0:
            key = self.item(current_row, 0).text()
            
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Are you sure you want to delete credential '{key}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes and self.credential_manager:
                if self.credential_manager.delete_credential(key):
                    self.credential_changed.emit()
                else:
                    QMessageBox.warning(self, "Error", f"Failed to delete credential '{key}'")
    
    def copy_key(self):
        """Copy the key to clipboard."""
        current_row = self.currentRow()
        if current_row >= 0:
            key = self.item(current_row, 0).text()
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(key)
    
    def copy_value(self):
        """Copy the value to clipboard."""
        current_row = self.currentRow()
        if current_row >= 0:
            key = self.item(current_row, 0).text()
            if self.credential_manager:
                credential = self.credential_manager.get_credential(key)
                if credential:
                    from PyQt6.QtWidgets import QApplication
                    QApplication.clipboard().setText(credential.value)
    
    def migrate_to_secrets(self):
        """Migrate credential to secrets."""
        current_row = self.currentRow()
        if current_row >= 0:
            key = self.item(current_row, 0).text()
            if self.credential_manager:
                if self.credential_manager.migrate_sensitivity(key, CredentialType.SECRET):
                    self.credential_changed.emit()
                    QMessageBox.information(self, "Success", f"Moved '{key}' to secure storage")
                else:
                    QMessageBox.warning(self, "Error", f"Failed to migrate '{key}'")
    
    def migrate_to_environment(self):
        """Migrate credential to environment."""
        current_row = self.currentRow()
        if current_row >= 0:
            key = self.item(current_row, 0).text()
            if self.credential_manager:
                if self.credential_manager.migrate_sensitivity(key, CredentialType.ENVIRONMENT):
                    self.credential_changed.emit()
                    QMessageBox.information(self, "Success", f"Moved '{key}' to environment storage")
                else:
                    QMessageBox.warning(self, "Error", f"Failed to migrate '{key}'")
    
    def edit_credential(self, credential: CredentialEntry):
        """Edit a credential."""
        # Pass the config_manager directly from this widget
        dialog = AddCredentialDialog(self, credential, config_manager=self.config_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_credential_data()
            
            if not data["key"] or not data["value"]:
                QMessageBox.warning(self, "Invalid Input", "Key and value are required")
                return
            
            if self.credential_manager:
                try:
                    # Delete old credential if key changed
                    if data["key"] != credential.key:
                        self.credential_manager.delete_credential(credential.key)
                    
                    # Set new credential
                    self.credential_manager.set_credential(
                        data["key"], data["value"],
                        data["credential_type"], data["description"],
                        data["server_ids"]
                    )
                    
                    self.credential_changed.emit()
                    
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to save credential: {e}")
    
    def load_credentials(self, credential_manager: CredentialManager):
        """Load credentials into the table."""
        self.credential_manager = credential_manager
        
        # Get all credentials of the specified type
        all_credentials = credential_manager.list_credentials()
        credentials = [c for c in all_credentials if c.credential_type == self.credential_type]
        
        # Clear and populate table
        self.setRowCount(len(credentials))
        
        for row, credential in enumerate(credentials):
            # Key
            self.setItem(row, 0, QTableWidgetItem(credential.key))
            
            # Value (masked for secrets)
            if credential.credential_type == CredentialType.SECRET:
                value_item = QTableWidgetItem("••••••••")
                value_item.setToolTip("Click to reveal value")
            else:
                value_item = QTableWidgetItem(credential.value)
            self.setItem(row, 1, value_item)
            
            # Description
            description = credential.description or ""
            if credential.auto_detected:
                description = f"[Auto] {description}"
            self.setItem(row, 2, QTableWidgetItem(description))
            
            # Server associations
            if hasattr(credential, 'server_ids') and credential.server_ids:
                server_text = ", ".join(sorted(credential.server_ids))
            else:
                server_text = "SYSTEM"
                
            server_item = QTableWidgetItem(server_text)
            if server_text == "SYSTEM":
                server_item.setToolTip("Global credential for Hive MCP Gateway")
            self.setItem(row, 3, server_item)
            
            # Actions (placeholder)
            self.setItem(row, 4, QTableWidgetItem("Edit | Delete"))


class CredentialManagementWidget(QWidget):
    """Main credential management widget with tabbed interface."""
    
    def __init__(self, parent=None, config_manager=None):
        super().__init__(parent)
        self.credential_manager = CredentialManager()
        self.config_manager = config_manager
        
        self.load_stylesheet()
        self.setup_ui()
        self.load_credentials()
        
        # Validate keyring access
        self.validate_keyring()
    
    def load_stylesheet(self):
        """Load and apply the Hive Night theme stylesheet."""
        try:
            # Try to load from absolute path first
            stylesheet_path = Path(__file__).parent / "assets" / "styles.qss"
            
            # If not found, try relative path
            if not stylesheet_path.exists():
                stylesheet_path = "gui/assets/styles.qss"
                
            with open(stylesheet_path, "r") as f:
                stylesheet = f.read()
                self.setStyleSheet(stylesheet)
        except FileNotFoundError:
            logger.warning("Stylesheet not found")
        except Exception as e:
            logger.error(f"Error loading stylesheet: {e}")
    
    def setup_ui(self):
        """Setup the main UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("Credential Management")
        title.setObjectName("headerLabel")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Action buttons
        self.add_btn = QPushButton("Add Credential")
        self.add_btn.setObjectName("addButton")
        self.add_btn.clicked.connect(self.add_credential)
        header_layout.addWidget(self.add_btn)
        
        self.import_btn = QPushButton("Import from JSON")
        self.import_btn.setObjectName("importButton")
        self.import_btn.clicked.connect(self.import_credentials)
        header_layout.addWidget(self.import_btn)
        
        self.export_btn = QPushButton("Export All")
        self.export_btn.setObjectName("exportButton")
        self.export_btn.clicked.connect(self.export_credentials)
        header_layout.addWidget(self.export_btn)
        
        layout.addLayout(header_layout)
        
        # Intro text
        intro_label = QLabel("Secrets are stored securely via the OS's secret store. Environment variables are passed through to the MCP configuration for easy maintenance/changes.")
        intro_label.setObjectName("introLabel")
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)
        
        # Question about mapping
        question_label = QLabel("The system uses key matching to determine which ENV's/Secrets belong to which MCP entry. The Auto-Detect ENV's/Secrets feature is implemented - when you use the Add MCP Server wizard, it will auto-detect and add them to the credentials section.")
        question_label.setObjectName("descriptionLabel")
        question_label.setWordWrap(True)
        layout.addWidget(question_label)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("credentialTabs")
        
        # Environment variables tab
        self.env_table = CredentialTableWidget(CredentialType.ENVIRONMENT)
        self.env_table.credential_changed.connect(self.load_credentials)
        self.tab_widget.addTab(self.env_table, "Environment Variables")
        
        # Secrets tab
        self.secrets_table = CredentialTableWidget(CredentialType.SECRET)
        self.secrets_table.credential_changed.connect(self.load_credentials)
        self.tab_widget.addTab(self.secrets_table, "Secrets (Keyring)")
        
        layout.addWidget(self.tab_widget)
        
        # Status bar
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.keyring_status = QLabel("Keyring: Unknown")
        self.keyring_status.setObjectName("keyringStatusLabel")
        status_layout.addWidget(self.keyring_status)
        
        layout.addLayout(status_layout)
    
    def validate_keyring(self):
        """Validate keyring access and update status."""
        success, message = self.credential_manager.validate_keyring_access()
        
        if success:
            self.keyring_status.setText("Keyring: ✓ Available")
            self.keyring_status.setStyleSheet("color: #388e3c;")
        else:
            self.keyring_status.setText("Keyring: ✗ Error")
            self.keyring_status.setStyleSheet("color: #d32f2f;")
            self.keyring_status.setToolTip(f"Keyring error: {message}")
    
    def load_credentials(self):
        """Load credentials into both tables."""
        try:
            self.env_table.load_credentials(self.credential_manager)
            self.secrets_table.load_credentials(self.credential_manager)
            
            # Update counts
            env_count = self.env_table.rowCount()
            secrets_count = self.secrets_table.rowCount()
            
            self.tab_widget.setTabText(0, f"Environment Variables ({env_count})")
            self.tab_widget.setTabText(1, f"Secrets ({secrets_count})")
            
            self.status_label.setText(f"Loaded {env_count + secrets_count} credentials")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load credentials: {e}")
            logger.error(f"Failed to load credentials: {e}")
    
    def add_credential(self):
        """Add a new credential."""
        dialog = AddCredentialDialog(self, config_manager=self.config_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_credential_data()
            
            if not data["key"] or not data["value"]:
                QMessageBox.warning(self, "Invalid Input", "Key and value are required")
                return
            
            try:
                self.credential_manager.set_credential(
                    data["key"], data["value"],
                    data["credential_type"], data["description"],
                    data["server_ids"]
                )
                
                self.load_credentials()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save credential: {e}")
    
    def import_credentials(self):
        """Import credentials from JSON."""
        from PyQt6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Credentials", "", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                import json
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                if not isinstance(data, dict):
                    QMessageBox.warning(self, "Invalid Format", "JSON file must contain a dictionary")
                    return
                
                # Ask about auto-detection
                reply = QMessageBox.question(
                    self, "Import Options",
                    "Enable automatic sensitivity detection?\\n\\n"
                    "Yes: Automatically detect sensitive data and store in keyring\\n"
                    "No: Store all as environment variables",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                auto_detect = reply == QMessageBox.StandardButton.Yes
                
                entries = self.credential_manager.import_from_dict(data, auto_detect)
                
                self.load_credentials()
                
                QMessageBox.information(
                    self, "Import Complete",
                    f"Imported {len(entries)} credentials successfully"
                )
                
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import credentials: {e}")
    
    def export_credentials(self):
        """Export all credentials."""
        from PyQt6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Credentials", "credentials.json", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                credentials = self.credential_manager.get_all_for_export()
                
                import json
                with open(file_path, 'w') as f:
                    json.dump(credentials, f, indent=2)
                
                QMessageBox.information(
                    self, "Export Complete",
                    f"Exported {len(credentials)} credentials to {file_path}"
                )
                
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export credentials: {e}")