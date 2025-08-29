"""Notification manager for system alerts and GUI notifications in Hive MCP Gateway."""

import logging
import platform
import subprocess
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json

from PyQt6.QtWidgets import QSystemTrayIcon, QWidget
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"
    OAUTH_REQUIRED = "oauth_required"
    AUTH_EXPIRED = "auth_expired"
    SERVICE_STATUS = "service_status"
    UPDATE_AVAILABLE = "update_available"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Notification:
    """Represents a notification."""
    id: str
    title: str
    message: str
    notification_type: NotificationType
    priority: NotificationPriority
    timestamp: datetime
    server_name: Optional[str] = None
    action_data: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    shown: bool = False
    dismissed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "type": self.notification_type.value,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "server_name": self.server_name,
            "action_data": self.action_data,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "shown": self.shown,
            "dismissed": self.dismissed
        }


class NotificationManager(QObject):
    """Manages system notifications and alerts."""
    
    # Signals
    notification_added = pyqtSignal(dict)  # notification dict
    notification_clicked = pyqtSignal(str)  # notification id
    oauth_authentication_requested = pyqtSignal(str, dict)  # server_name, config
    
    def __init__(self, system_tray: Optional[QSystemTrayIcon] = None):
        super().__init__()
        
        self.system_tray = system_tray
        self.notifications: Dict[str, Notification] = {}
        self.callbacks: Dict[str, Callable[[Notification], None]] = {}
        
        # Configuration
        self.max_notifications = 50
        self.default_expire_minutes = 30
        self.show_system_notifications = True
        self.show_tray_notifications = True
        
        # Platform detection
        self.platform = platform.system().lower()
        
        # Cleanup timer
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_expired_notifications)
        self.cleanup_timer.start(60000)  # Cleanup every minute
        
        logger.info("Notification manager initialized")
    
    def add_notification(self, 
                        title: str,
                        message: str,
                        notification_type: NotificationType = NotificationType.INFO,
                        priority: NotificationPriority = NotificationPriority.NORMAL,
                        server_name: Optional[str] = None,
                        action_data: Optional[Dict[str, Any]] = None,
                        expire_minutes: Optional[int] = None) -> str:
        """
        Add a new notification.
        
        Args:
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            priority: Priority level
            server_name: Associated server name
            action_data: Data for notification actions
            expire_minutes: Minutes until expiration (None for default)
            
        Returns:
            Notification ID
        """
        # Generate ID
        notification_id = f"{notification_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Calculate expiration
        expires_at = None
        if expire_minutes is not None:
            expires_at = datetime.now() + timedelta(minutes=expire_minutes)
        elif self.default_expire_minutes > 0:
            expires_at = datetime.now() + timedelta(minutes=self.default_expire_minutes)
        
        # Create notification
        notification = Notification(
            id=notification_id,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            timestamp=datetime.now(),
            server_name=server_name,
            action_data=action_data,
            expires_at=expires_at
        )
        
        # Store notification
        self.notifications[notification_id] = notification
        
        # Show notification
        self._show_notification(notification)
        
        # Emit signal
        self.notification_added.emit(notification.to_dict())
        
        # Cleanup old notifications if needed
        self._cleanup_old_notifications()
        
        logger.info(f"Added notification: {title} ({notification_type.value})")
        return notification_id
    
    def _show_notification(self, notification: Notification):
        """Show a notification using appropriate method."""
        try:
            # Show system notification
            if self.show_system_notifications:
                self._show_system_notification(notification)
            
            # Show system tray notification
            if self.show_tray_notifications and self.system_tray:
                self._show_tray_notification(notification)
            
            notification.shown = True
            
        except Exception as e:
            logger.error(f"Failed to show notification: {e}")
    
    def _show_system_notification(self, notification: Notification):
        """Show system notification using platform-specific method."""
        try:
            if self.platform == "darwin":  # macOS
                self._show_macos_notification(notification)
            elif self.platform == "linux":
                self._show_linux_notification(notification)
            elif self.platform == "windows":
                self._show_windows_notification(notification)
        except Exception as e:
            logger.error(f"Failed to show system notification: {e}")
    
    def _show_macos_notification(self, notification: Notification):
        """Show macOS notification using osascript."""
        # Map notification type to sound
        sound_map = {
            NotificationType.ERROR: "Basso",
            NotificationType.WARNING: "Sosumi", 
            NotificationType.SUCCESS: "Glass",
            NotificationType.OAUTH_REQUIRED: "Tink",
            NotificationType.AUTH_EXPIRED: "Tink"
        }
        
        sound = sound_map.get(notification.notification_type, "default")
        
        # Build AppleScript
        script = f'''
        display notification "{notification.message}" \\
            with title "Hive MCP Gateway" \\
            subtitle "{notification.title}" \\
            sound name "{sound}"
        '''
        
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    
    def _show_linux_notification(self, notification: Notification):
        """Show Linux notification using notify-send."""
        # Map notification type to icon
        icon_map = {
            NotificationType.INFO: "dialog-information",
            NotificationType.WARNING: "dialog-warning",
            NotificationType.ERROR: "dialog-error", 
            NotificationType.SUCCESS: "dialog-information",
            NotificationType.OAUTH_REQUIRED: "dialog-question",
            NotificationType.AUTH_EXPIRED: "dialog-warning"
        }
        
        icon = icon_map.get(notification.notification_type, "dialog-information")
        
        subprocess.run([
            "notify-send",
            "--icon", icon,
            "--app-name", "Hive MCP Gateway",
            notification.title,
            notification.message
        ], check=False, capture_output=True)
    
    def _show_windows_notification(self, notification: Notification):
        """Show Windows notification using PowerShell."""
        # Use Windows Toast notifications via PowerShell
        script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        
        $template = @"
        <toast>
            <visual>
                <binding template="ToastGeneric">
                    <text>{notification.title}</text>
                    <text>{notification.message}</text>
                </binding>
            </visual>
        </toast>
        "@
        
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Hive MCP Gateway").Show($toast)
        '''
        
        subprocess.run(["powershell", "-Command", script], check=False, capture_output=True)
    
    def _show_tray_notification(self, notification: Notification):
        """Show system tray notification."""
        if not self.system_tray or not self.system_tray.isVisible():
            return
        
        # Map notification type to QSystemTrayIcon icon
        icon_map = {
            NotificationType.INFO: QSystemTrayIcon.MessageIcon.Information,
            NotificationType.WARNING: QSystemTrayIcon.MessageIcon.Warning,
            NotificationType.ERROR: QSystemTrayIcon.MessageIcon.Critical,
            NotificationType.SUCCESS: QSystemTrayIcon.MessageIcon.Information,
            NotificationType.OAUTH_REQUIRED: QSystemTrayIcon.MessageIcon.Warning,
            NotificationType.AUTH_EXPIRED: QSystemTrayIcon.MessageIcon.Warning
        }
        
        icon = icon_map.get(notification.notification_type, QSystemTrayIcon.MessageIcon.Information)
        
        # Show tray notification
        self.system_tray.showMessage(
            notification.title,
            notification.message,
            icon,
            5000  # 5 seconds
        )
    
    def dismiss_notification(self, notification_id: str) -> bool:
        """Dismiss a notification."""
        if notification_id in self.notifications:
            self.notifications[notification_id].dismissed = True
            logger.debug(f"Dismissed notification: {notification_id}")
            return True
        return False
    
    def get_notification(self, notification_id: str) -> Optional[Notification]:
        """Get a notification by ID."""
        return self.notifications.get(notification_id)
    
    def get_active_notifications(self) -> List[Notification]:
        """Get all active (not dismissed and not expired) notifications."""
        now = datetime.now()
        return [
            notification for notification in self.notifications.values()
            if (not notification.dismissed and 
                (notification.expires_at is None or notification.expires_at > now))
        ]
    
    def get_notifications_by_type(self, notification_type: NotificationType) -> List[Notification]:
        """Get notifications by type."""
        return [
            notification for notification in self.notifications.values()
            if notification.notification_type == notification_type
        ]
    
    def get_notifications_by_server(self, server_name: str) -> List[Notification]:
        """Get notifications for a specific server."""
        return [
            notification for notification in self.notifications.values()
            if notification.server_name == server_name
        ]
    
    def cleanup_expired_notifications(self):
        """Remove expired notifications."""
        now = datetime.now()
        expired_ids = [
            notification_id for notification_id, notification in self.notifications.items()
            if (notification.expires_at and notification.expires_at <= now)
        ]
        
        for notification_id in expired_ids:
            del self.notifications[notification_id]
            logger.debug(f"Removed expired notification: {notification_id}")
    
    def _cleanup_old_notifications(self):
        """Remove old notifications if we exceed the limit."""
        if len(self.notifications) <= self.max_notifications:
            return
        
        # Sort by timestamp (oldest first)
        sorted_notifications = sorted(
            self.notifications.items(),
            key=lambda x: x[1].timestamp
        )
        
        # Remove oldest notifications
        to_remove = len(self.notifications) - self.max_notifications
        for i in range(to_remove):
            notification_id = sorted_notifications[i][0]
            del self.notifications[notification_id]
            logger.debug(f"Removed old notification: {notification_id}")
    
    def register_callback(self, callback_id: str, callback: Callable[[Notification], None]):
        """Register a callback for notification events."""
        self.callbacks[callback_id] = callback
    
    def unregister_callback(self, callback_id: str):
        """Unregister a notification callback."""
        if callback_id in self.callbacks:
            del self.callbacks[callback_id]
    
    def handle_notification_click(self, notification_id: str):
        """Handle notification click."""
        notification = self.get_notification(notification_id)
        if not notification:
            return
        
        # Execute callbacks
        for callback in self.callbacks.values():
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"Notification callback failed: {e}")
        
        # Handle specific notification types
        if notification.notification_type == NotificationType.OAUTH_REQUIRED:
            self._handle_oauth_notification_click(notification)
        
        # Emit signal
        self.notification_clicked.emit(notification_id)
    
    def _handle_oauth_notification_click(self, notification: Notification):
        """Handle OAuth notification click."""
        if notification.server_name and notification.action_data:
            self.oauth_authentication_requested.emit(
                notification.server_name, 
                notification.action_data
            )
    
    # Convenience methods for common notification types
    
    def notify_oauth_required(self, server_name: str, oauth_url: Optional[str] = None):
        """Notify that OAuth authentication is required."""
        action_data = {"oauth_url": oauth_url} if oauth_url else None
        
        self.add_notification(
            title=f"OAuth Required - {server_name}",
            message=f"Server '{server_name}' requires OAuth authentication. Click to authenticate.",
            notification_type=NotificationType.OAUTH_REQUIRED,
            priority=NotificationPriority.HIGH,
            server_name=server_name,
            action_data=action_data,
            expire_minutes=60  # OAuth notifications last longer
        )
    
    def notify_auth_expired(self, server_name: str):
        """Notify that authentication has expired."""
        self.add_notification(
            title=f"Authentication Expired - {server_name}",
            message=f"Authentication for '{server_name}' has expired. Please re-authenticate.",
            notification_type=NotificationType.AUTH_EXPIRED,
            priority=NotificationPriority.HIGH,
            server_name=server_name
        )
    
    def notify_service_status(self, service_name: str, status: str, details: Optional[str] = None):
        """Notify about service status changes."""
        message = f"Service '{service_name}' is now {status}"
        if details:
            message += f": {details}"
        
        notification_type = NotificationType.SUCCESS if status == "running" else NotificationType.WARNING
        
        self.add_notification(
            title="Service Status Update",
            message=message,
            notification_type=notification_type,
            priority=NotificationPriority.NORMAL
        )
    
    def notify_error(self, title: str, message: str, server_name: Optional[str] = None):
        """Notify about errors."""
        self.add_notification(
            title=title,
            message=message,
            notification_type=NotificationType.ERROR,
            priority=NotificationPriority.HIGH,
            server_name=server_name
        )
    
    def notify_success(self, title: str, message: str, server_name: Optional[str] = None):
        """Notify about successful operations."""
        self.add_notification(
            title=title,
            message=message,
            notification_type=NotificationType.SUCCESS,
            priority=NotificationPriority.NORMAL,
            server_name=server_name
        )
    
    def clear_server_notifications(self, server_name: str):
        """Clear all notifications for a specific server."""
        to_remove = [
            notification_id for notification_id, notification in self.notifications.items()
            if notification.server_name == server_name
        ]
        
        for notification_id in to_remove:
            del self.notifications[notification_id]
        
        logger.info(f"Cleared notifications for server: {server_name}")
    
    def get_notification_summary(self) -> Dict[str, Any]:
        """Get a summary of current notifications."""
        active_notifications = self.get_active_notifications()
        
        # Count by type
        type_counts = {}
        for notification in active_notifications:
            notification_type = notification.notification_type.value
            type_counts[notification_type] = type_counts.get(notification_type, 0) + 1
        
        # Count by priority
        priority_counts = {}
        for notification in active_notifications:
            priority = notification.priority.value
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        return {
            "total_active": len(active_notifications),
            "total_stored": len(self.notifications),
            "by_type": type_counts,
            "by_priority": priority_counts,
            "oauth_pending": len(self.get_notifications_by_type(NotificationType.OAUTH_REQUIRED)),
            "auth_expired": len(self.get_notifications_by_type(NotificationType.AUTH_EXPIRED)),
            "errors": len(self.get_notifications_by_type(NotificationType.ERROR))
        }