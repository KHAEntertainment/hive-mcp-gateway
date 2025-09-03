"""Custom server card widget for displaying MCP server status."""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from .animated_toggle import AnimatedToggle

class ServerCard(QWidget):
    """Custom widget for displaying an MCP server with status and controls."""
    
    edit_requested = pyqtSignal(str)  # Signal emitted when edit button is clicked
    delete_requested = pyqtSignal(str)  # Signal emitted when delete button is clicked
    restart_requested = pyqtSignal(str)  # Signal emitted when restart button is clicked
    toggle_requested = pyqtSignal(str, bool)  # Signal emitted when toggle is changed
    
    def __init__(self, server_id: str, name: str, tools_count: int, status: str, parent=None):
        """
        Initialize the server card.
        
        Args:
            server_id (str): Unique identifier for the server
            name (str): Display name of the server
            tools_count (int): Number of tools provided by the server
            status (str): Current status ("connected", "disconnected", "disabled")
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.server_id = server_id
        self.name = name
        self.tools_count = tools_count
        self.status = status
        self._updating = False  # Flag to prevent feedback loops
        
        self.setObjectName("serverCard")
        self.setup_ui()
        self.update_status()
    
    def setup_ui(self):
        """Setup the server card UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Status dot indicator
        self.status_dot = QLabel()
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setProperty("status", self.status)
        layout.addWidget(self.status_dot)
        
        # Server info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        self.name_label = QLabel(self.name)
        self.name_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.name_label)
        
        self.tools_label = QLabel(f"{self.tools_count} tools")
        self.tools_label.setStyleSheet("color: #a0a3a8; font-size: 11px;")
        info_layout.addWidget(self.tools_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # Controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        
        # Reconnect button (only shown for disconnected servers)
        self.reconnect_button = QPushButton("🔄 Reconnect")
        self.reconnect_button.setObjectName("reconnectButton")
        self.reconnect_button.clicked.connect(self.on_restart_clicked)
        self.reconnect_button.setVisible(self.status == "disconnected")
        self.reconnect_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 4px;
                color: #f2f3f5;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        controls_layout.addWidget(self.reconnect_button)
        
        # Animated toggle switch
        self.toggle_switch = AnimatedToggle()
        self.toggle_switch.setChecked(self.status != "disabled")
        self.toggle_switch.stateChanged.connect(self.on_toggle_changed)
        
        controls_layout.addWidget(self.toggle_switch)
        
        # Edit button
        self.edit_button = QPushButton("✏️")
        self.edit_button.setObjectName("editButton")
        self.edit_button.setFixedSize(28, 28)  # Slightly larger
        self.edit_button.setToolTip("Edit Server")
        self.edit_button.clicked.connect(self.on_edit_clicked)
        self.edit_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        controls_layout.addWidget(self.edit_button)
        
        # Delete button
        self.delete_button = QPushButton("🗑️")
        self.delete_button.setObjectName("deleteButton")
        self.delete_button.setFixedSize(28, 28)  # Slightly larger
        self.delete_button.setToolTip("Delete Server")
        self.delete_button.clicked.connect(self.on_delete_clicked)
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: rgba(255, 100, 100, 0.2);
            }
            QPushButton:pressed {
                background-color: rgba(255, 100, 100, 0.4);
            }
        """)
        controls_layout.addWidget(self.delete_button)
        layout.addLayout(controls_layout)
    
    def update_status(self):
        """Update the status display."""
        # Set updating flag to prevent feedback loops
        self._updating = True
        
        try:
            # Update status dot
            self.status_dot.setProperty("status", self.status)
            
            # Update style
            if self.status == "connected":
                self.status_dot.setText("🟢")
            elif self.status == "disconnected":
                self.status_dot.setText("🔴")
            else:  # disabled
                self.status_dot.setText("⚫")
            
            # Update toggle without triggering the signal
            self.toggle_switch.blockSignals(True)
            self.toggle_switch.setChecked(self.status != "disabled")
            self.toggle_switch.blockSignals(False)
            
            # Show/hide reconnect button based on status
            if hasattr(self, 'reconnect_button'):
                self.reconnect_button.setVisible(self.status == "disconnected")
            
            # Update labels
            if self.status == "connected":
                self.name_label.setStyleSheet("font-weight: bold; color: #f2f3f5;")
            elif self.status == "disconnected":
                self.name_label.setStyleSheet("font-weight: bold; color: #f2f3f5;")
            else:  # disabled
                self.name_label.setStyleSheet("font-weight: bold; color: #a0a3a8;")
        finally:
            # Reset updating flag
            self._updating = False
    
    def on_edit_clicked(self):
        """Handle edit button click."""
        self.edit_requested.emit(self.server_id)
    
    def on_delete_clicked(self):
        """Handle delete button click."""
        self.delete_requested.emit(self.server_id)
    
    def on_restart_clicked(self):
        """Handle restart button click."""
        self.restart_requested.emit(self.server_id)
    
    def on_toggle_changed(self, checked):
        """Handle toggle switch change."""
        # Only emit signal if we're not in the middle of an update
        if not self._updating:
            # For context7, add an extra block to prevent bounce-back
            if self.server_id == "context7" and not checked:
                # When explicitly turning off context7, apply additional measures
                # to prevent it from turning itself back on
                self.status = "disabled"
                self.update_status()  # Will set the toggle without emitting signals
            
            # Emit the signal
            self.toggle_requested.emit(self.server_id, checked)
    
    def set_status(self, status: str):
        """
        Set the server status.
        
        Args:
            status (str): New status ("connected", "disconnected", "disabled")
        """
        self.status = status
        self.update_status()
        
    def set_tool_count(self, count: int):
        """
        Update the tool count display.
        
        Args:
            count (int): New tool count
        """
        self.tools_count = count
        if hasattr(self, 'tools_label'):
            self.tools_label.setText(f"{count} tools")
