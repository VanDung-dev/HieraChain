"""
Secure Logging Utilities for HieraChain

This module provides secure logging functions that prevent log injection attacks
by sanitizing user input before logging and using structured log formats.
"""

import logging
import json
from typing import Any
from datetime import datetime


# Characters that can be used for log injection
LOG_INJECTION_CHARS = {
    "\n": "\\n",
    "\r": "\\r",
    "\x00": "\\x00",
    "\x1b": "\\x1b",  # ANSI escape
    "\t": "\\t",
}


def sanitize_for_log(value: Any) -> str:
    """
    Sanitize a value before logging to prevent log injection.
    
    Args:
        value: Value to sanitize (string, dict, list, or other)
        
    Returns:
        Safe string representation
    """
    if value is None:
        return "null"
    
    if isinstance(value, (int, float, bool)):
        return str(value)
    
    if isinstance(value, str):
        result = value
        # Replace dangerous characters
        for char, replacement in LOG_INJECTION_CHARS.items():
            result = result.replace(char, replacement)
        # Truncate very long strings
        if len(result) > 500:
            result = result[:500] + "...[truncated]"
        return result
    
    if isinstance(value, dict):
        return json.dumps(
            {k: sanitize_for_log(v) for k, v in value.items()},
            ensure_ascii=True
        )
    
    if isinstance(value, (list, tuple)):
        return json.dumps([sanitize_for_log(item) for item in value])
    
    # For other types, convert to string and sanitize
    return sanitize_for_log(str(value))


class SecureLogger:
    """
    Secure logger wrapper that automatically sanitizes user input in log messages.
    Uses structured logging format for better security and parseability.
    """
    
    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.name = name
    
    def _format_structured(
        self, 
        level: str, 
        message: str, 
        **kwargs: Any
    ) -> str:
        """Create a structured log entry in JSON format."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "logger": self.name,
            "message": sanitize_for_log(message),
        }
        
        # Add extra fields with sanitization
        if kwargs:
            log_entry["data"] = {
                k: sanitize_for_log(v) for k, v in kwargs.items()
            }
        
        return json.dumps(log_entry, ensure_ascii=True)
    
    def info(self, message: str, **kwargs: Any):
        """Log info with sanitized data."""
        structured = self._format_structured("INFO", message, **kwargs)
        self.logger.info(structured)
    
    def warning(self, message: str, **kwargs: Any):
        """Log warning with sanitized data."""
        structured = self._format_structured("WARNING", message, **kwargs)
        self.logger.warning(structured)
    
    def error(self, message: str, **kwargs: Any):
        """Log error with sanitized data."""
        structured = self._format_structured("ERROR", message, **kwargs)
        self.logger.error(structured)
    
    def debug(self, message: str, **kwargs: Any):
        """Log debug with sanitized data."""
        structured = self._format_structured("DEBUG", message, **kwargs)
        self.logger.debug(structured)
    
    def critical(self, message: str, **kwargs: Any):
        """Log critical with sanitized data."""
        structured = self._format_structured("CRITICAL", message, **kwargs)
        self.logger.critical(structured)
    
    def security_event(
        self, 
        event_type: str, 
        message: str, 
        severity: str = "medium",
        **kwargs: Any
    ):
        """
        Log a security-related event with full context.
        
        Args:
            event_type: Type of security event (e.g., "auth_failure", "access_denied")
            message: Human-readable message
            severity: Event severity (low, medium, high, critical)
            **kwargs: Additional context data
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "security_event",
            "event_type": sanitize_for_log(event_type),
            "severity": severity,
            "logger": self.name,
            "message": sanitize_for_log(message),
        }
        
        if kwargs:
            log_entry["context"] = {
                k: sanitize_for_log(v) for k, v in kwargs.items()
            }
        
        structured = json.dumps(log_entry, ensure_ascii=True)
        
        # Use appropriate log level based on severity
        if severity == "critical":
            self.logger.critical(structured)
        elif severity == "high":
            self.logger.error(structured)
        elif severity == "medium":
            self.logger.warning(structured)
        else:
            self.logger.info(structured)
    
    def audit(
        self,
        action: str,
        resource: str,
        user_id: str = None,
        org_id: str = None,
        success: bool = True,
        **kwargs: Any
    ):
        """
        Log an audit event for compliance and tracking.
        
        Args:
            action: Action performed (e.g., "create", "read", "update", "delete")
            resource: Resource affected (e.g., "channel", "contract", "organization")
            user_id: Optional user identifier
            org_id: Optional organization identifier
            success: Whether the action was successful
            **kwargs: Additional context
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "audit",
            "action": sanitize_for_log(action),
            "resource": sanitize_for_log(resource),
            "success": success,
            "logger": self.name,
        }
        
        if user_id:
            log_entry["user_id"] = sanitize_for_log(user_id)
        if org_id:
            log_entry["org_id"] = sanitize_for_log(org_id)
        
        if kwargs:
            log_entry["details"] = {
                k: sanitize_for_log(v) for k, v in kwargs.items()
            }
        
        self.logger.info(json.dumps(log_entry, ensure_ascii=True))


# Pre-configured loggers for different modules
def get_api_logger() -> SecureLogger:
    """Get secure logger for API layer."""
    return SecureLogger("hierachain.api")


def get_security_logger() -> SecureLogger:
    """Get secure logger for security events."""
    return SecureLogger("hierachain.security")


def get_audit_logger() -> SecureLogger:
    """Get secure logger for audit events."""
    return SecureLogger("hierachain.audit")


# Convenience function for quick sanitized logging
def log_user_action(
    logger: logging.Logger,
    level: int,
    message: str,
    user_input: Any = None,
    **kwargs: Any
):
    """
    Log a message with user input safely sanitized.
    
    Args:
        logger: Standard Python logger
        level: Log level (logging.INFO, etc.)
        message: Log message template
        user_input: User-provided input to sanitize
        **kwargs: Additional data to include
    """
    safe_input = sanitize_for_log(user_input) if user_input is not None else None
    safe_kwargs = {k: sanitize_for_log(v) for k, v in kwargs.items()}
    
    log_data = {
        "message": message,
        "user_input": safe_input,
        **safe_kwargs
    }
    
    logger.log(level, json.dumps(log_data, ensure_ascii=True))
