"""Comprehensive error handling and recovery system for Hive MCP Gateway."""

import logging
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio

from ..models.config import ServerStatus

logger = logging.getLogger(__name__)


class MCPError(Exception):
    """Base exception class for MCP-related errors."""
    def __init__(self, message: str, error_code: str = "MCP_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(MCPError):
    """Exception for configuration-related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFIG_ERROR", details)


class ConnectionError(MCPError):
    """Exception for connection-related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONNECTION_ERROR", details)


class AuthenticationError(MCPError):
    """Exception for authentication-related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "AUTH_ERROR", details)


class ToolExecutionError(MCPError):
    """Exception for tool execution errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "TOOL_EXEC_ERROR", details)


class HealthCheckError(MCPError):
    """Exception for health check errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "HEALTH_CHECK_ERROR", details)


class ErrorHandler:
    """Comprehensive error handling and recovery system."""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.error_timestamps: Dict[str, List[datetime]] = {}
        self.recovery_actions: Dict[str, List[str]] = {}
        self.max_errors_per_minute = 10
        self.error_window = timedelta(minutes=1)
        
    def handle_error(self, server_name: str, error: Exception, context: str = "") -> Dict[str, Any]:
        """Handle an error and determine appropriate recovery action."""
        try:
            # Log the error
            error_info = self._log_error(server_name, error, context)
            
            # Update error tracking
            self._track_error(server_name, error_info)
            
            # Determine recovery action
            recovery_action = self._determine_recovery_action(server_name, error, error_info)
            
            # Execute recovery action if needed
            if recovery_action:
                self._execute_recovery_action(server_name, recovery_action, error_info)
            
            return {
                "status": "handled",
                "error_info": error_info,
                "recovery_action": recovery_action,
                "needs_retry": recovery_action.get("retry", False)
            }
            
        except Exception as handler_error:
            logger.error(f"Error in error handler: {handler_error}")
            return {
                "status": "handler_failed",
                "error_info": {"message": str(error)},
                "recovery_action": None,
                "needs_retry": False
            }
    
    def _log_error(self, server_name: str, error: Exception, context: str) -> Dict[str, Any]:
        """Log error details and return error information."""
        error_info = {
            "server_name": server_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "timestamp": datetime.now().isoformat(),
            "traceback": traceback.format_exc()
        }
        
        # Log with appropriate level based on error type
        if isinstance(error, (ConfigurationError, AuthenticationError)):
            logger.error(f"Server {server_name} - {error_info['error_type']}: {error_info['error_message']}")
        elif isinstance(error, (ConnectionError, HealthCheckError)):
            logger.warning(f"Server {server_name} - {error_info['error_type']}: {error_info['error_message']}")
        elif isinstance(error, ToolExecutionError):
            logger.info(f"Server {server_name} - {error_info['error_type']}: {error_info['error_message']}")
        else:
            logger.error(f"Server {server_name} - Unexpected error: {error_info['error_message']}")
        
        return error_info
    
    def _track_error(self, server_name: str, error_info: Dict[str, Any]) -> None:
        """Track error occurrences for rate limiting and pattern detection."""
        if server_name not in self.error_counts:
            self.error_counts[server_name] = 0
            self.error_timestamps[server_name] = []
        
        self.error_counts[server_name] += 1
        self.error_timestamps[server_name].append(datetime.now())
        
        # Clean up old timestamps
        cutoff_time = datetime.now() - self.error_window
        self.error_timestamps[server_name] = [
            ts for ts in self.error_timestamps[server_name] 
            if ts > cutoff_time
        ]
    
    def _determine_recovery_action(self, server_name: str, error: Exception, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """Determine appropriate recovery action based on error type and frequency."""
        recovery_action = {
            "action": "none",
            "retry": False,
            "delay": 0,
            "details": {}
        }
        
        # Check error rate
        recent_errors = len(self.error_timestamps.get(server_name, []))
        if recent_errors > self.max_errors_per_minute:
            logger.warning(f"High error rate for {server_name}: {recent_errors} errors per minute")
            recovery_action.update({
                "action": "throttle",
                "delay": 30,  # Wait 30 seconds
                "details": {"reason": "high_error_rate", "error_count": recent_errors}
            })
            return recovery_action
        
        # Determine action based on error type
        if isinstance(error, ConfigurationError):
            recovery_action.update({
                "action": "reload_config",
                "details": {"reason": "configuration_error"}
            })
        elif isinstance(error, AuthenticationError):
            recovery_action.update({
                "action": "refresh_auth",
                "retry": True,
                "delay": 5,
                "details": {"reason": "authentication_failed"}
            })
        elif isinstance(error, ConnectionError):
            recovery_action.update({
                "action": "reconnect",
                "retry": True,
                "delay": 10,
                "details": {"reason": "connection_failed"}
            })
        elif isinstance(error, HealthCheckError):
            recovery_action.update({
                "action": "health_check",
                "retry": True,
                "delay": 15,
                "details": {"reason": "health_check_failed"}
            })
        elif isinstance(error, ToolExecutionError):
            recovery_action.update({
                "action": "retry_tool",
                "retry": True,
                "delay": 2,
                "details": {"reason": "tool_execution_failed"}
            })
        
        return recovery_action
    
    def _execute_recovery_action(self, server_name: str, recovery_action: Dict[str, Any], error_info: Dict[str, Any]) -> None:
        """Execute the determined recovery action."""
        action = recovery_action.get("action", "none")
        delay = recovery_action.get("delay", 0)
        
        if delay > 0:
            logger.info(f"Delaying recovery action for {server_name} by {delay} seconds")
            # In a real implementation, this would be handled asynchronously
            # await asyncio.sleep(delay)
        
        logger.info(f"Executing recovery action '{action}' for server {server_name}")
        
        # Log the recovery action for potential future analysis
        if server_name not in self.recovery_actions:
            self.recovery_actions[server_name] = []
        
        self.recovery_actions[server_name].append({
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "error_info": error_info
        })
    
    def get_server_error_stats(self, server_name: str) -> Dict[str, Any]:
        """Get error statistics for a specific server."""
        return {
            "total_errors": self.error_counts.get(server_name, 0),
            "recent_errors": len(self.error_timestamps.get(server_name, [])),
            "recovery_actions": self.recovery_actions.get(server_name, [])
        }
    
    def reset_error_tracking(self, server_name: str) -> None:
        """Reset error tracking for a specific server."""
        if server_name in self.error_counts:
            del self.error_counts[server_name]
        if server_name in self.error_timestamps:
            del self.error_timestamps[server_name]
        if server_name in self.recovery_actions:
            del self.recovery_actions[server_name]
        logger.info(f"Reset error tracking for server {server_name}")
    
    def update_server_status_from_error(self, server_name: str, server_status: ServerStatus, error: Exception) -> None:
        """Update server status based on error information."""
        server_status.error_message = str(error)
        
        # Update health status based on error type
        if isinstance(error, (ConfigurationError, AuthenticationError)):
            server_status.health_status = "unhealthy"
        elif isinstance(error, (ConnectionError, HealthCheckError)):
            server_status.health_status = "degraded"
        elif isinstance(error, ToolExecutionError):
            server_status.health_status = "degraded"
        else:
            server_status.health_status = "unknown"
        
        server_status.last_health_check = datetime.now().isoformat()
    
    async def retry_with_backoff(self, func, *args, max_retries=3, base_delay=1.0, **kwargs):
        """Execute a function with exponential backoff retry logic."""
        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"Max retries exceeded for {func.__name__}: {e}")
                    raise
                
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
    
    def should_circuit_break(self, server_name: str) -> bool:
        """Determine if circuit breaker should be triggered for a server."""
        recent_errors = len(self.error_timestamps.get(server_name, []))
        return recent_errors > self.max_errors_per_minute * 2  # Trigger at 2x error rate
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get a summary of all errors across servers."""
        return {
            "total_servers_with_errors": len(self.error_counts),
            "error_counts": self.error_counts,
            "recent_errors_by_server": {
                server: len(timestamps) 
                for server, timestamps in self.error_timestamps.items()
            }
        }