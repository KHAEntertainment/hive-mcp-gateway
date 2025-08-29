"""Enhanced monitoring service for real-time authentication status tracking in Hive MCP Gateway."""

import asyncio
import logging
import json
import psutil
from typing import Dict, Any, List, Optional, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import weakref

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread, QMutex, QMutexLocker

from .auth_detector import AuthDetector, AuthEvent, AuthStatus, AuthRequirement
from .oauth_manager import OAuthManager
from .credential_manager import CredentialManager
from .notification_manager import NotificationManager, NotificationType
from .llm_client_manager import LLMClientManager

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Overall health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ServiceStatus(Enum):
    """Individual service status."""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    STARTING = "starting"
    STOPPING = "stopping"


@dataclass
class HealthMetric:
    """Individual health metric."""
    name: str
    value: Any
    status: HealthStatus
    message: str
    last_updated: datetime = field(default_factory=datetime.now)
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "status": self.status.value,
            "message": self.message,
            "last_updated": self.last_updated.isoformat(),
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical
        }


@dataclass
class ServiceHealth:
    """Health status for a service."""
    name: str
    status: ServiceStatus
    health: HealthStatus
    metrics: List[HealthMetric] = field(default_factory=list)
    last_check: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "health": self.health.value,
            "metrics": [m.to_dict() for m in self.metrics],
            "last_check": self.last_check.isoformat(),
            "error_message": self.error_message
        }


class MonitoringWorker(QThread):
    """Background worker for monitoring tasks."""
    
    health_updated = pyqtSignal(str, dict)  # service_name, health_data
    auth_event_detected = pyqtSignal(dict)  # auth_event
    system_alert = pyqtSignal(str, str, str)  # level, title, message
    
    def __init__(self, monitoring_service):
        super().__init__()
        self.monitoring_service = weakref.ref(monitoring_service)
        self.running = False
        self.mutex = QMutex()
    
    def run(self):
        """Main monitoring loop."""
        self.running = True
        
        while self.running:
            try:
                monitoring_service = self.monitoring_service()
                if monitoring_service:
                    # Perform monitoring checks
                    monitoring_service._perform_health_checks()
                    monitoring_service._check_auth_status()
                    monitoring_service._check_system_resources()
                    monitoring_service._check_oauth_expiry()
                
                # Sleep for monitoring interval
                self.msleep(5000)  # 5 seconds
                
            except Exception as e:
                logger.error(f"Monitoring worker error: {e}")
                self.msleep(10000)  # Wait longer on error
    
    def stop(self):
        """Stop the monitoring worker."""
        with QMutexLocker(self.mutex):
            self.running = False


class MonitoringService(QObject):
    """Enhanced monitoring service with real-time status tracking."""
    
    # Signals
    health_status_changed = pyqtSignal(str, dict)  # service_name, health_data
    overall_status_changed = pyqtSignal(str, dict)  # status, summary
    auth_event_detected = pyqtSignal(dict)  # auth_event
    oauth_expiry_warning = pyqtSignal(str, datetime)  # server_name, expires_at
    system_alert = pyqtSignal(str, str, str)  # level, title, message
    
    def __init__(self, 
                 auth_detector: AuthDetector,
                 oauth_manager: OAuthManager,
                 credential_manager: CredentialManager,
                 notification_manager: NotificationManager,
                 llm_client_manager: Optional[LLMClientManager] = None):
        super().__init__()
        
        self.auth_detector = auth_detector
        self.oauth_manager = oauth_manager
        self.credential_manager = credential_manager
        self.notification_manager = notification_manager
        self.llm_client_manager = llm_client_manager
        
        # Monitoring state
        self.service_health: Dict[str, ServiceHealth] = {}
        self.overall_health = HealthStatus.UNKNOWN
        self.monitoring_enabled = True
        self.monitoring_interval = 5  # seconds
        
        # Thresholds
        self.cpu_warning_threshold = 80.0
        self.cpu_critical_threshold = 95.0
        self.memory_warning_threshold = 80.0
        self.memory_critical_threshold = 95.0
        self.disk_warning_threshold = 85.0
        self.disk_critical_threshold = 95.0
        
        # Callbacks
        self.health_callbacks: Dict[str, Callable[[ServiceHealth], None]] = {}
        
        # Background worker
        self.monitoring_worker = MonitoringWorker(self)
        self.monitoring_worker.health_updated.connect(self.health_status_changed.emit)
        self.monitoring_worker.auth_event_detected.connect(self.auth_event_detected.emit)
        self.monitoring_worker.system_alert.connect(self.system_alert.emit)
        
        # Setup auth detector callbacks
        self.auth_detector.add_event_callback(self._on_auth_event)
        
        # Initialize service monitoring
        self._initialize_service_monitoring()
        
        logger.info("Enhanced monitoring service initialized")
    
    def start_monitoring(self):
        """Start the monitoring service."""
        if not self.monitoring_worker.isRunning():
            self.monitoring_worker.start()
            logger.info("Monitoring service started")
    
    def stop_monitoring(self):
        """Stop the monitoring service."""
        if self.monitoring_worker.isRunning():
            self.monitoring_worker.stop()
            self.monitoring_worker.wait(5000)  # Wait up to 5 seconds
            logger.info("Monitoring service stopped")
    
    def _initialize_service_monitoring(self):
        """Initialize monitoring for core services."""
        services = [
            "authentication",
            "oauth_manager", 
            "credential_manager",
            "notification_manager",
            "system_resources",
            "mcp_gateway"
        ]
        
        if self.llm_client_manager:
            services.append("llm_clients")
        
        for service_name in services:
            self.service_health[service_name] = ServiceHealth(
                name=service_name,
                status=ServiceStatus.UNKNOWN,
                health=HealthStatus.UNKNOWN
            )
    
    def _perform_health_checks(self):
        """Perform health checks for all monitored services."""
        try:
            # Check authentication status
            self._check_authentication_health()
            
            # Check OAuth manager
            self._check_oauth_health()
            
            # Check credential manager
            self._check_credential_health()
            
            # Check notification manager
            self._check_notification_health()
            
            # Check LLM clients if available
            if self.llm_client_manager:
                self._check_llm_clients_health()
            
            # Check MCP gateway
            self._check_mcp_gateway_health()
            
            # Update overall health
            self._update_overall_health()
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
    
    def _check_authentication_health(self):
        """Check authentication system health."""
        try:
            metrics = []
            overall_health = HealthStatus.HEALTHY
            error_message = None
            
            # Get auth summary
            auth_summary = self.auth_detector.get_auth_summary()
            
            # Check for servers requiring authentication
            servers_requiring_auth = auth_summary.get("requiring_auth", 0)
            servers_with_issues = auth_summary.get("with_issues", 0)
            expiring_soon = auth_summary.get("expiring_soon", 0)
            
            # Create metrics
            metrics.append(HealthMetric(
                name="servers_requiring_auth",
                value=servers_requiring_auth,
                status=HealthStatus.WARNING if servers_requiring_auth > 0 else HealthStatus.HEALTHY,
                message=f"{servers_requiring_auth} servers require authentication"
            ))
            
            metrics.append(HealthMetric(
                name="servers_with_auth_issues",
                value=servers_with_issues,
                status=HealthStatus.CRITICAL if servers_with_issues > 0 else HealthStatus.HEALTHY,
                message=f"{servers_with_issues} servers have authentication issues"
            ))
            
            metrics.append(HealthMetric(
                name="tokens_expiring_soon",
                value=expiring_soon,
                status=HealthStatus.WARNING if expiring_soon > 0 else HealthStatus.HEALTHY,
                message=f"{expiring_soon} tokens expiring soon"
            ))
            
            # Determine overall health
            if servers_with_issues > 0:
                overall_health = HealthStatus.CRITICAL
                error_message = f"{servers_with_issues} servers have authentication issues"
            elif servers_requiring_auth > 0 or expiring_soon > 0:
                overall_health = HealthStatus.WARNING
                
            # Update service health
            self.service_health["authentication"] = ServiceHealth(
                name="authentication",
                status=ServiceStatus.RUNNING,
                health=overall_health,
                metrics=metrics,
                error_message=error_message
            )
            
        except Exception as e:
            logger.error(f"Authentication health check error: {e}")
            self.service_health["authentication"] = ServiceHealth(
                name="authentication",
                status=ServiceStatus.ERROR,
                health=HealthStatus.CRITICAL,
                error_message=str(e)
            )
    
    def _check_oauth_health(self):
        """Check OAuth manager health."""
        try:
            metrics = []
            overall_health = HealthStatus.HEALTHY
            
            # Check active flows
            active_flows = len(self.oauth_manager.active_flows)
            metrics.append(HealthMetric(
                name="active_oauth_flows",
                value=active_flows,
                status=HealthStatus.WARNING if active_flows > 10 else HealthStatus.HEALTHY,
                message=f"{active_flows} active OAuth flows",
                threshold_warning=10.0
            ))
            
            # Check expired flows
            expired_flows = len([
                flow for flow in self.oauth_manager.active_flows.values()
                if flow.expires_at < datetime.now()
            ])
            
            metrics.append(HealthMetric(
                name="expired_oauth_flows",
                value=expired_flows,
                status=HealthStatus.WARNING if expired_flows > 0 else HealthStatus.HEALTHY,
                message=f"{expired_flows} expired OAuth flows"
            ))
            
            if expired_flows > 0:
                overall_health = HealthStatus.WARNING
            
            self.service_health["oauth_manager"] = ServiceHealth(
                name="oauth_manager",
                status=ServiceStatus.RUNNING,
                health=overall_health,
                metrics=metrics
            )
            
        except Exception as e:
            logger.error(f"OAuth health check error: {e}")
            self.service_health["oauth_manager"] = ServiceHealth(
                name="oauth_manager",
                status=ServiceStatus.ERROR,
                health=HealthStatus.CRITICAL,
                error_message=str(e)
            )
    
    def _check_credential_health(self):
        """Check credential manager health."""
        try:
            metrics = []
            overall_health = HealthStatus.HEALTHY
            error_message = None
            
            # Test keyring access
            keyring_ok, keyring_msg = self.credential_manager.validate_keyring_access()
            
            metrics.append(HealthMetric(
                name="keyring_access",
                value=keyring_ok,
                status=HealthStatus.HEALTHY if keyring_ok else HealthStatus.CRITICAL,
                message=keyring_msg
            ))
            
            # Count credentials
            credentials = self.credential_manager.list_credentials()
            env_count = len([c for c in credentials if c.credential_type.value == "environment"])
            secret_count = len([c for c in credentials if c.credential_type.value == "secret"])
            
            metrics.append(HealthMetric(
                name="environment_credentials",
                value=env_count,
                status=HealthStatus.HEALTHY,
                message=f"{env_count} environment credentials"
            ))
            
            metrics.append(HealthMetric(
                name="secret_credentials",
                value=secret_count,
                status=HealthStatus.HEALTHY,
                message=f"{secret_count} secret credentials"
            ))
            
            if not keyring_ok:
                overall_health = HealthStatus.CRITICAL
                error_message = "Keyring access failed"
            
            self.service_health["credential_manager"] = ServiceHealth(
                name="credential_manager",
                status=ServiceStatus.RUNNING,
                health=overall_health,
                metrics=metrics,
                error_message=error_message
            )
            
        except Exception as e:
            logger.error(f"Credential health check error: {e}")
            self.service_health["credential_manager"] = ServiceHealth(
                name="credential_manager",
                status=ServiceStatus.ERROR,
                health=HealthStatus.CRITICAL,
                error_message=str(e)
            )
    
    def _check_notification_health(self):
        """Check notification manager health."""
        try:
            metrics = []
            
            # Get notification summary
            summary = self.notification_manager.get_notification_summary()
            
            metrics.append(HealthMetric(
                name="active_notifications",
                value=summary["total_active"],
                status=HealthStatus.WARNING if summary["total_active"] > 20 else HealthStatus.HEALTHY,
                message=f"{summary['total_active']} active notifications",
                threshold_warning=20.0
            ))
            
            metrics.append(HealthMetric(
                name="oauth_pending",
                value=summary["oauth_pending"],
                status=HealthStatus.WARNING if summary["oauth_pending"] > 0 else HealthStatus.HEALTHY,
                message=f"{summary['oauth_pending']} OAuth authentications pending"
            ))
            
            metrics.append(HealthMetric(
                name="auth_expired",
                value=summary["auth_expired"],
                status=HealthStatus.WARNING if summary["auth_expired"] > 0 else HealthStatus.HEALTHY,
                message=f"{summary['auth_expired']} expired authentications"
            ))
            
            metrics.append(HealthMetric(
                name="errors",
                value=summary["errors"],
                status=HealthStatus.CRITICAL if summary["errors"] > 0 else HealthStatus.HEALTHY,
                message=f"{summary['errors']} error notifications"
            ))
            
            overall_health = HealthStatus.HEALTHY
            if summary["errors"] > 0:
                overall_health = HealthStatus.CRITICAL
            elif summary["oauth_pending"] > 0 or summary["auth_expired"] > 0:
                overall_health = HealthStatus.WARNING
            
            self.service_health["notification_manager"] = ServiceHealth(
                name="notification_manager",
                status=ServiceStatus.RUNNING,
                health=overall_health,
                metrics=metrics
            )
            
        except Exception as e:
            logger.error(f"Notification health check error: {e}")
            self.service_health["notification_manager"] = ServiceHealth(
                name="notification_manager",
                status=ServiceStatus.ERROR,
                health=HealthStatus.CRITICAL,
                error_message=str(e)
            )
    
    def _check_llm_clients_health(self):
        """Check LLM clients health."""
        if not self.llm_client_manager:
            return
        
        try:
            metrics = []
            overall_health = HealthStatus.HEALTHY
            
            # Get provider information
            providers = self.llm_client_manager.list_providers()
            enabled_providers = self.llm_client_manager.list_enabled_providers()
            
            metrics.append(HealthMetric(
                name="total_providers",
                value=len(providers),
                status=HealthStatus.HEALTHY,
                message=f"{len(providers)} LLM providers configured"
            ))
            
            metrics.append(HealthMetric(
                name="enabled_providers",
                value=len(enabled_providers),
                status=HealthStatus.WARNING if len(enabled_providers) == 0 else HealthStatus.HEALTHY,
                message=f"{len(enabled_providers)} LLM providers enabled"
            ))
            
            # Check authentication requirements
            auth_requirements = self.llm_client_manager.get_auth_requirements()
            needs_auth = len([
                req for req in auth_requirements.values()
                if req["auth_status"] != "authenticated"
            ])
            
            metrics.append(HealthMetric(
                name="providers_needing_auth",
                value=needs_auth,
                status=HealthStatus.WARNING if needs_auth > 0 else HealthStatus.HEALTHY,
                message=f"{needs_auth} providers need authentication"
            ))
            
            if len(enabled_providers) == 0:
                overall_health = HealthStatus.WARNING
            elif needs_auth > len(enabled_providers) / 2:  # More than half need auth
                overall_health = HealthStatus.WARNING
            
            self.service_health["llm_clients"] = ServiceHealth(
                name="llm_clients",
                status=ServiceStatus.RUNNING,
                health=overall_health,
                metrics=metrics
            )
            
        except Exception as e:
            logger.error(f"LLM clients health check error: {e}")
            self.service_health["llm_clients"] = ServiceHealth(
                name="llm_clients",
                status=ServiceStatus.ERROR,
                health=HealthStatus.CRITICAL,
                error_message=str(e)
            )
    
    def _check_mcp_gateway_health(self):
        """Check MCP gateway health."""
        try:
            metrics = []
            overall_health = HealthStatus.HEALTHY
            
            # This would check the actual MCP gateway status
            # For now, we'll create a placeholder
            metrics.append(HealthMetric(
                name="gateway_status",
                value="running",
                status=HealthStatus.HEALTHY,
                message="MCP gateway is running"
            ))
            
            self.service_health["mcp_gateway"] = ServiceHealth(
                name="mcp_gateway",
                status=ServiceStatus.RUNNING,
                health=overall_health,
                metrics=metrics
            )
            
        except Exception as e:
            logger.error(f"MCP gateway health check error: {e}")
            self.service_health["mcp_gateway"] = ServiceHealth(
                name="mcp_gateway",
                status=ServiceStatus.ERROR,
                health=HealthStatus.CRITICAL,
                error_message=str(e)
            )
    
    def _check_system_resources(self):
        """Check system resource utilization."""
        try:
            metrics = []
            overall_health = HealthStatus.HEALTHY
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_status = HealthStatus.HEALTHY
            if cpu_percent >= self.cpu_critical_threshold:
                cpu_status = HealthStatus.CRITICAL
                overall_health = HealthStatus.CRITICAL
            elif cpu_percent >= self.cpu_warning_threshold:
                cpu_status = HealthStatus.WARNING
                if overall_health == HealthStatus.HEALTHY:
                    overall_health = HealthStatus.WARNING
            
            metrics.append(HealthMetric(
                name="cpu_usage",
                value=cpu_percent,
                status=cpu_status,
                message=f"CPU usage: {cpu_percent:.1f}%",
                threshold_warning=self.cpu_warning_threshold,
                threshold_critical=self.cpu_critical_threshold
            ))
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_status = HealthStatus.HEALTHY
            if memory_percent >= self.memory_critical_threshold:
                memory_status = HealthStatus.CRITICAL
                overall_health = HealthStatus.CRITICAL
            elif memory_percent >= self.memory_warning_threshold:
                memory_status = HealthStatus.WARNING
                if overall_health == HealthStatus.HEALTHY:
                    overall_health = HealthStatus.WARNING
            
            metrics.append(HealthMetric(
                name="memory_usage",
                value=memory_percent,
                status=memory_status,
                message=f"Memory usage: {memory_percent:.1f}%",
                threshold_warning=self.memory_warning_threshold,
                threshold_critical=self.memory_critical_threshold
            ))
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_status = HealthStatus.HEALTHY
            if disk_percent >= self.disk_critical_threshold:
                disk_status = HealthStatus.CRITICAL
                overall_health = HealthStatus.CRITICAL
            elif disk_percent >= self.disk_warning_threshold:
                disk_status = HealthStatus.WARNING
                if overall_health == HealthStatus.HEALTHY:
                    overall_health = HealthStatus.WARNING
            
            metrics.append(HealthMetric(
                name="disk_usage",
                value=disk_percent,
                status=disk_status,
                message=f"Disk usage: {disk_percent:.1f}%",
                threshold_warning=self.disk_warning_threshold,
                threshold_critical=self.disk_critical_threshold
            ))
            
            self.service_health["system_resources"] = ServiceHealth(
                name="system_resources",
                status=ServiceStatus.RUNNING,
                health=overall_health,
                metrics=metrics
            )
            
        except Exception as e:
            logger.error(f"System resources check error: {e}")
            self.service_health["system_resources"] = ServiceHealth(
                name="system_resources",
                status=ServiceStatus.ERROR,
                health=HealthStatus.CRITICAL,
                error_message=str(e)
            )
    
    def _check_auth_status(self):
        """Check for authentication status changes."""
        try:
            # Get servers with auth issues
            servers_with_issues = self.auth_detector.get_servers_with_auth_issues()
            
            for server_info in servers_with_issues:
                # Check if this is a new issue
                if server_info.failure_count == 1:  # First failure
                    self.notification_manager.notify_error(
                        f"Authentication Failed - {server_info.server_name}",
                        f"Authentication failed for {server_info.server_name}. Please check credentials.",
                        server_info.server_name
                    )
                
                # Check for OAuth requirement
                if server_info.auth_requirement == AuthRequirement.OAUTH and server_info.oauth_url:
                    self.notification_manager.notify_oauth_required(
                        server_info.server_name,
                        server_info.oauth_url
                    )
            
        except Exception as e:
            logger.error(f"Auth status check error: {e}")
    
    def _check_oauth_expiry(self):
        """Check for expiring OAuth tokens."""
        try:
            expiring_tokens = self.auth_detector.get_expiring_tokens(hours_ahead=1)
            
            for server_info in expiring_tokens:
                if server_info.token_expires_at:
                    self.oauth_expiry_warning.emit(server_info.server_name, server_info.token_expires_at)
                    
                    self.notification_manager.add_notification(
                        title=f"Token Expiring - {server_info.server_name}",
                        message=f"OAuth token for {server_info.server_name} expires at {server_info.token_expires_at}",
                        notification_type=NotificationType.WARNING,
                        server_name=server_info.server_name
                    )
            
        except Exception as e:
            logger.error(f"OAuth expiry check error: {e}")
    
    def _update_overall_health(self):
        """Update overall system health status."""
        try:
            critical_count = len([
                h for h in self.service_health.values()
                if h.health == HealthStatus.CRITICAL
            ])
            
            warning_count = len([
                h for h in self.service_health.values()
                if h.health == HealthStatus.WARNING
            ])
            
            if critical_count > 0:
                new_status = HealthStatus.CRITICAL
            elif warning_count > 0:
                new_status = HealthStatus.WARNING
            else:
                new_status = HealthStatus.HEALTHY
            
            if new_status != self.overall_health:
                self.overall_health = new_status
                summary = self.get_health_summary()
                self.overall_status_changed.emit(new_status.value, summary)
                
                # Send system alert for critical status
                if new_status == HealthStatus.CRITICAL:
                    self.system_alert.emit(
                        "critical",
                        "System Health Critical",
                        f"System health is critical. {critical_count} services have critical issues."
                    )
            
        except Exception as e:
            logger.error(f"Overall health update error: {e}")
    
    def _on_auth_event(self, event: AuthEvent):
        """Handle authentication events."""
        self.auth_event_detected.emit({
            "timestamp": event.timestamp.isoformat(),
            "server_name": event.server_name,
            "event_type": event.event_type,
            "auth_requirement": event.auth_requirement.value,
            "error_message": event.error_message,
            "oauth_url": event.oauth_url,
            "suggested_action": event.suggested_action
        })
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary."""
        return {
            "overall_health": self.overall_health.value,
            "services": {name: health.to_dict() for name, health in self.service_health.items()},
            "summary": {
                "total_services": len(self.service_health),
                "healthy": len([h for h in self.service_health.values() if h.health == HealthStatus.HEALTHY]),
                "warning": len([h for h in self.service_health.values() if h.health == HealthStatus.WARNING]),
                "critical": len([h for h in self.service_health.values() if h.health == HealthStatus.CRITICAL]),
                "unknown": len([h for h in self.service_health.values() if h.health == HealthStatus.UNKNOWN])
            },
            "last_updated": datetime.now().isoformat()
        }
    
    def get_service_health(self, service_name: str) -> Optional[ServiceHealth]:
        """Get health status for a specific service."""
        return self.service_health.get(service_name)
    
    def register_health_callback(self, callback_id: str, callback: Callable[[ServiceHealth], None]):
        """Register a callback for health changes."""
        self.health_callbacks[callback_id] = callback
    
    def unregister_health_callback(self, callback_id: str):
        """Unregister a health callback."""
        if callback_id in self.health_callbacks:
            del self.health_callbacks[callback_id]
    
    def set_monitoring_enabled(self, enabled: bool):
        """Enable or disable monitoring."""
        self.monitoring_enabled = enabled
        if enabled:
            self.start_monitoring()
        else:
            self.stop_monitoring()
    
    def set_monitoring_interval(self, seconds: int):
        """Set monitoring interval in seconds."""
        self.monitoring_interval = max(1, min(300, seconds))  # Between 1 and 300 seconds
    
    def force_health_check(self):
        """Force an immediate health check."""
        try:
            self._perform_health_checks()
        except Exception as e:
            logger.error(f"Forced health check error: {e}")
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get monitoring service status."""
        return {
            "enabled": self.monitoring_enabled,
            "running": self.monitoring_worker.isRunning(),
            "interval": self.monitoring_interval,
            "overall_health": self.overall_health.value,
            "services_monitored": len(self.service_health),
            "last_check": max([h.last_check for h in self.service_health.values()]).isoformat() if self.service_health else None
        }