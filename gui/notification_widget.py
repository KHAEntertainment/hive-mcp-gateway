"""Custom notification widget for the Hive MCP Gateway."""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal

class NotificationWidget(QWidget):
    """Custom widget for displaying a notification."""
    
    dismissed = pyqtSignal(str)  # Signal emitted when notification is dismissed
    
    def __init__(self, notification_id: str, message: str, level: str = "info", parent=None):
        """
        Initialize the notification widget.
        
        Args:
            notification_id (str): Unique identifier for the notification
            message (str): Notification message
            level (str): Notification level ("info", "warning", "error", "success")
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.notification_id = notification_id
        self.message = message
        self.level = level
        
        self.setObjectName("notificationItem")
        self.setProperty("level", level)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the notification widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Level indicator
        self.level_icon = QLabel()
        self.level_icon.setStyleSheet("font-size: 16px; margin-right: 8px;")
        self.update_level_icon()
        layout.addWidget(self.level_icon)
        
        # Message
        self.message_label = QLabel(self.message)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("margin-right: 8px;")
        layout.addWidget(self.message_label)
        layout.addStretch()
        
        # Dismiss button
        self.dismiss_button = QPushButton("✕")
        self.dismiss_button.setFixedSize(24, 24)
        self.dismiss_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #a0a3a8;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #f2f3f5;
            }
        """)
        self.dismiss_button.clicked.connect(self.on_dismiss)
        layout.addWidget(self.dismiss_button)
    
    def update_level_icon(self):
        """Update the level indicator icon based on the notification level."""
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅"
        }
        self.level_icon.setText(icons.get(self.level, "ℹ️"))
        
        # Update colors based on level
        colors = {
            "info": "#8c62ff",
            "warning": "#fde047",
            "error": "#d9534f",
            "success": "#5cb85c"
        }
        color = colors.get(self.level, "#8c62ff")
        self.level_icon.setStyleSheet(f"font-size: 16px; color: {color}; margin-right: 8px;")
    
    def on_dismiss(self):
        """Handle dismiss button click."""
        self.dismissed.emit(self.notification_id)
        self.setParent(None)  # Remove from parent
        self.deleteLater()  # Schedule for deletion