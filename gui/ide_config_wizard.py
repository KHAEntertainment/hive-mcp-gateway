"""Selective import/export wizard for IDE configuration management."""

import json
import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWizard, QWizardPage, QLabel,
    QTreeWidget, QTreeWidgetItem, QPushButton, QCheckBox, QTextEdit,
    QGroupBox, QRadioButton, QButtonGroup, QComboBox, QMessageBox,
    QFileDialog, QProgressBar, QSplitter, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QFont, QIcon

from hive_mcp_gateway.services.ide_detector import IDEDetector, IDEInfo, IDEType
from hive_mcp_gateway.services.config_injector import ConfigInjector, InjectionOperation, InjectionResult

logger = logging.getLogger(__name__)


class IDEConfigWizard(QWizard):
    """Wizard for importing/exporting IDE configurations."""
    
    # Wizard page IDs
    PAGE_OPERATION_SELECT = 0
    PAGE_IDE_SELECT = 1
    PAGE_PREVIEW = 2
    PAGE_EXECUTION = 3
    PAGE_RESULTS = 4
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("IDE Configuration Wizard")
        self.setMinimumSize(800, 600)
        
        # Initialize services
        self.detector = IDEDetector()
        self.injector = ConfigInjector()
        
        # Wizard data
        self.operation_type = "import"  # "import", "export", "remove"
        self.selected_ides: List[IDEInfo] = []
        self.server_selections: Dict[str, bool] = {}
        self.operation_results: List[InjectionOperation] = []
        
        # Setup wizard pages
        self.setup_pages()
    
    def setup_pages(self):
        """Setup all wizard pages."""
        self.addPage(OperationSelectPage(self))
        self.addPage(IDESelectPage(self))
        self.addPage(PreviewPage(self))
        self.addPage(ExecutionPage(self))
        self.addPage(ResultsPage(self))


class OperationSelectPage(QWizardPage):
    """Page for selecting the operation type."""
    
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        
        self.setTitle("Select Operation")
        self.setSubTitle("Choose what you want to do with IDE configurations")
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the operation selection UI."""
        layout = QVBoxLayout(self)
        
        # Operation selection
        self.operation_group = QButtonGroup(self)
        
        self.import_radio = QRadioButton("Import Hive MCP Gateway configuration to IDEs")
        self.import_radio.setChecked(True)
        self.import_radio.toggled.connect(self.on_operation_changed)
        
        self.export_radio = QRadioButton("Export existing IDE configurations")
        self.export_radio.toggled.connect(self.on_operation_changed)
        
        self.remove_radio = QRadioButton("Remove Hive MCP Gateway from IDEs")
        self.remove_radio.toggled.connect(self.on_operation_changed)
        
        self.operation_group.addButton(self.import_radio, 0)
        self.operation_group.addButton(self.export_radio, 1)
        self.operation_group.addButton(self.remove_radio, 2)
        
        layout.addWidget(self.import_radio)
        layout.addWidget(self.export_radio)
        layout.addWidget(self.remove_radio)
        
        # Operation descriptions
        descriptions_group = QGroupBox("Operation Details")
        descriptions_layout = QVBoxLayout(descriptions_group)
        
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("padding: 10px; background-color: #f5f5f5; border-radius: 5px;")
        descriptions_layout.addWidget(self.description_label)
        
        layout.addWidget(descriptions_group)
        layout.addStretch()
        
        # Set initial description
        self.on_operation_changed()
    
    def on_operation_changed(self):
        """Handle operation type change."""
        if self.import_radio.isChecked():
            self.wizard.operation_type = "import"
            self.description_label.setText(
                "<b>Import Configuration:</b><br>"
                "This will add Hive MCP Gateway configuration to your selected IDEs. "
                "Existing configurations will be backed up automatically. "
                "You can choose to overwrite existing Hive entries or skip IDEs that already have them."
            )
        elif self.export_radio.isChecked():
            self.wizard.operation_type = "export"
            self.description_label.setText(
                "<b>Export Configuration:</b><br>"
                "This will save the current IDE configurations to a JSON file. "
                "You can use this for backup purposes or to share configurations between systems."
            )
        elif self.remove_radio.isChecked():
            self.wizard.operation_type = "remove"
            self.description_label.setText(
                "<b>Remove Configuration:</b><br>"
                "This will remove Hive MCP Gateway configuration from your selected IDEs. "
                "Other MCP servers will remain unchanged. "
                "Configurations will be backed up before removal."
            )


class IDESelectPage(QWizardPage):
    """Page for selecting IDEs to work with."""
    
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        
        self.setTitle("Select IDEs")
        self.setSubTitle("Choose which IDEs to configure")
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the IDE selection UI."""
        layout = QVBoxLayout(self)
        
        # IDE table
        self.ide_table = QTableWidget()
        self.ide_table.setColumnCount(5)
        self.ide_table.setHorizontalHeaderLabels([
            "Select", "IDE", "Version", "Status", "Current MCP Servers"
        ])
        
        # Configure table
        header = self.ide_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Select
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # IDE
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Version
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Status
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Servers
        
        self.ide_table.setColumnWidth(0, 60)
        self.ide_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.ide_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_none_btn = QPushButton("Select None")
        self.refresh_btn = QPushButton("Refresh")
        
        self.select_all_btn.clicked.connect(self.select_all)
        self.select_none_btn.clicked.connect(self.select_none)
        self.refresh_btn.clicked.connect(self.refresh_ides)
        
        button_layout.addWidget(self.select_all_btn)
        button_layout.addWidget(self.select_none_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(button_layout)
        
        # Load IDEs
        self.refresh_ides()
    
    def initializePage(self):
        """Initialize the page when entered."""
        self.refresh_ides()
    
    def refresh_ides(self):
        """Refresh the IDE list."""
        detected_ides = self.wizard.detector.detect_all_ides()
        
        self.ide_table.setRowCount(len(detected_ides))
        
        for row, ide_info in enumerate(detected_ides):
            # Checkbox
            checkbox = QCheckBox()
            checkbox.setProperty("ide_index", row)
            checkbox.stateChanged.connect(self.on_selection_changed)
            self.ide_table.setCellWidget(row, 0, checkbox)
            
            # IDE name
            self.ide_table.setItem(row, 1, QTableWidgetItem(ide_info.name))
            
            # Version
            version = ide_info.version or "Unknown"
            self.ide_table.setItem(row, 2, QTableWidgetItem(version))
            
            # Status
            if not ide_info.is_installed:
                status = "Not Installed"
                status_color = "#d32f2f"
            elif not ide_info.config_exists:
                status = "No Config"
                status_color = "#ff9800"
            elif "hive-mcp-gateway" in ide_info.mcp_servers:
                status = "Has Hive"
                status_color = "#388e3c"
            else:
                status = "Ready"
                status_color = "#1976d2"
            
            status_item = QTableWidgetItem(status)
            status_item.setForeground(Qt.GlobalColor.white)
            status_item.setBackground(Qt.GlobalColor.fromString(status_color))
            self.ide_table.setItem(row, 3, status_item)
            
            # Current servers
            servers = list(ide_info.mcp_servers.keys())
            servers_text = ", ".join(servers) if servers else "None"
            self.ide_table.setItem(row, 4, QTableWidgetItem(servers_text))
        
        # Store IDE info for later use
        self.detected_ides = detected_ides
    
    def select_all(self):
        """Select all IDEs."""
        for row in range(self.ide_table.rowCount()):
            checkbox = self.ide_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(True)
    
    def select_none(self):
        """Deselect all IDEs."""
        for row in range(self.ide_table.rowCount()):
            checkbox = self.ide_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)
    
    def on_selection_changed(self):
        """Handle selection change."""
        self.wizard.selected_ides = []
        
        for row in range(self.ide_table.rowCount()):
            checkbox = self.ide_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                ide_index = checkbox.property("ide_index")
                if ide_index is not None and ide_index < len(self.detected_ides):
                    self.wizard.selected_ides.append(self.detected_ides[ide_index])
    
    def validatePage(self):
        """Validate page before proceeding."""
        if not self.wizard.selected_ides:
            QMessageBox.warning(self, "No Selection", "Please select at least one IDE to proceed.")
            return False
        return True


class PreviewPage(QWizardPage):
    """Page for previewing the operations."""
    
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        
        self.setTitle("Preview Changes")
        self.setSubTitle("Review what will be changed")
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the preview UI."""
        layout = QVBoxLayout(self)
        
        # Summary
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-weight: bold; padding: 10px; background-color: #e3f2fd; border-radius: 5px;")
        layout.addWidget(self.summary_label)
        
        # Preview tree
        self.preview_tree = QTreeWidget()
        self.preview_tree.setHeaderLabels(["Item", "Action", "Details"])
        layout.addWidget(self.preview_tree)
        
        # Options (for import)
        self.options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(self.options_group)
        
        self.force_checkbox = QCheckBox("Overwrite existing Hive MCP Gateway configurations")
        self.backup_checkbox = QCheckBox("Create backup before making changes")
        self.backup_checkbox.setChecked(True)
        self.backup_checkbox.setEnabled(False)  # Always enabled
        
        options_layout.addWidget(self.force_checkbox)
        options_layout.addWidget(self.backup_checkbox)
        
        layout.addWidget(self.options_group)
    
    def initializePage(self):
        """Initialize the page when entered."""
        self.update_preview()
    
    def update_preview(self):
        """Update the preview based on current selections."""
        self.preview_tree.clear()
        
        operation = self.wizard.operation_type
        ides = self.wizard.selected_ides
        
        if operation == "import":
            self.summary_label.setText(f"Will import Hive MCP Gateway configuration to {len(ides)} IDE(s)")
            self.options_group.setVisible(True)
            
            for ide_info in ides:
                ide_item = QTreeWidgetItem([ide_info.name, "Configure", ""])
                
                # Check if Hive already exists
                has_hive = "hive-mcp-gateway" in ide_info.mcp_servers
                if has_hive:
                    if self.force_checkbox.isChecked():
                        action_item = QTreeWidgetItem(["hive-mcp-gateway", "Update", "Overwrite existing configuration"])
                    else:
                        action_item = QTreeWidgetItem(["hive-mcp-gateway", "Skip", "Already exists"])
                else:
                    action_item = QTreeWidgetItem(["hive-mcp-gateway", "Add", "New configuration"])
                
                ide_item.addChild(action_item)
                
                # Backup info
                backup_item = QTreeWidgetItem(["Backup", "Create", f"Save to backup directory"])
                ide_item.addChild(backup_item)
                
                self.preview_tree.addTopLevelItem(ide_item)
                
        elif operation == "export":
            self.summary_label.setText(f"Will export configurations from {len(ides)} IDE(s)")
            self.options_group.setVisible(False)
            
            for ide_info in ides:
                ide_item = QTreeWidgetItem([ide_info.name, "Export", f"{len(ide_info.mcp_servers)} servers"])
                
                for server_name in ide_info.mcp_servers:
                    server_item = QTreeWidgetItem([server_name, "Include", ""])
                    ide_item.addChild(server_item)
                
                self.preview_tree.addTopLevelItem(ide_item)
                
        elif operation == "remove":
            self.summary_label.setText(f"Will remove Hive MCP Gateway from {len(ides)} IDE(s)")
            self.options_group.setVisible(False)
            
            for ide_info in ides:
                ide_item = QTreeWidgetItem([ide_info.name, "Configure", ""])
                
                has_hive = "hive-mcp-gateway" in ide_info.mcp_servers
                if has_hive:
                    action_item = QTreeWidgetItem(["hive-mcp-gateway", "Remove", "Delete configuration"])
                else:
                    action_item = QTreeWidgetItem(["hive-mcp-gateway", "Skip", "Not found"])
                
                ide_item.addChild(action_item)
                
                # Backup info
                backup_item = QTreeWidgetItem(["Backup", "Create", "Save before removal"])
                ide_item.addChild(backup_item)
                
                self.preview_tree.addTopLevelItem(ide_item)
        
        self.preview_tree.expandAll()


class ExecutionPage(QWizardPage):
    """Page for executing the operations."""
    
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        
        self.setTitle("Executing Operations")
        self.setSubTitle("Please wait while changes are applied")
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the execution UI."""
        layout = QVBoxLayout(self)
        
        # Progress
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Status
        self.status_label = QLabel("Ready to start...")
        layout.addWidget(self.status_label)
        
        # Log
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        layout.addWidget(self.log_text)
    
    def initializePage(self):
        """Initialize and start execution."""
        self.execute_operations()
    
    def execute_operations(self):
        """Execute the selected operations."""
        operation = self.wizard.operation_type
        ides = self.wizard.selected_ides
        
        self.progress_bar.setMaximum(len(ides))
        self.progress_bar.setValue(0)
        
        self.wizard.operation_results = []
        
        for i, ide_info in enumerate(ides):
            self.status_label.setText(f"Processing {ide_info.name}...")
            self.log_text.append(f"\\n--- Processing {ide_info.name} ---")
            
            try:
                if operation == "import":
                    force = self.wizard.page(self.wizard.PAGE_PREVIEW).force_checkbox.isChecked()
                    result = self.wizard.injector.inject_hive_config(ide_info, force=force)
                    
                elif operation == "remove":
                    result = self.wizard.injector.remove_hive_config(ide_info)
                    
                elif operation == "export":
                    # Export operation (would save to file)
                    result = None  # Placeholder
                
                if result:
                    self.wizard.operation_results.append(result)
                    
                    if result.result == InjectionResult.SUCCESS:
                        self.log_text.append(f"✓ Success: {ide_info.name}")
                    else:
                        self.log_text.append(f"✗ Failed: {ide_info.name} - {result.error_message}")
                
            except Exception as e:
                self.log_text.append(f"✗ Error: {ide_info.name} - {str(e)}")
                logger.error(f"Operation failed for {ide_info.name}: {e}")
            
            self.progress_bar.setValue(i + 1)
        
        self.status_label.setText("Operations completed")
        self.log_text.append("\\n--- All operations completed ---")


class ResultsPage(QWizardPage):
    """Page for showing operation results."""
    
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        
        self.setTitle("Operation Results")
        self.setSubTitle("Summary of completed operations")
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the results UI."""
        layout = QVBoxLayout(self)
        
        # Summary
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-weight: bold; padding: 10px; background-color: #e8f5e8; border-radius: 5px;")
        layout.addWidget(self.summary_label)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([
            "IDE", "Operation", "Result", "Details"
        ])
        
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.results_table)
        
        # Actions
        actions_layout = QHBoxLayout()
        self.view_backups_btn = QPushButton("View Backups")
        self.save_report_btn = QPushButton("Save Report")
        
        actions_layout.addWidget(self.view_backups_btn)
        actions_layout.addWidget(self.save_report_btn)
        actions_layout.addStretch()
        
        layout.addLayout(actions_layout)
    
    def initializePage(self):
        """Initialize the results page."""
        self.update_results()
    
    def update_results(self):
        """Update the results display."""
        results = self.wizard.operation_results
        
        success_count = sum(1 for r in results if r.result == InjectionResult.SUCCESS)
        total_count = len(results)
        
        self.summary_label.setText(f"Completed {success_count}/{total_count} operations successfully")
        
        self.results_table.setRowCount(len(results))
        
        for row, result in enumerate(results):
            # IDE name
            self.results_table.setItem(row, 0, QTableWidgetItem(result.ide_info.name))
            
            # Operation
            self.results_table.setItem(row, 1, QTableWidgetItem(result.operation_type.title()))
            
            # Result
            result_text = "Success" if result.result == InjectionResult.SUCCESS else "Failed"
            result_item = QTableWidgetItem(result_text)
            
            if result.result == InjectionResult.SUCCESS:
                result_item.setBackground(Qt.GlobalColor.green)
            else:
                result_item.setBackground(Qt.GlobalColor.red)
            
            self.results_table.setItem(row, 2, result_item)
            
            # Details
            details = result.error_message or "Operation completed successfully"
            self.results_table.setItem(row, 3, QTableWidgetItem(details))