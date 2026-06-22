"""
Secure Logging Utilities for HieraChain

This module provides secure logging functions that prevent log injection attacks
by sanitizing user input before logging and using structured log formats.
"""

import logging
import json
import re
from typing import Any
from datetime import datetime, timezone


# Characters that can be used for log injection
LOG_INJECTION_CHARS = {
    "\n": "\\n",
    "\r": "\\r",
    "\x00": "\\x00",
    "\x1b": "\\x1b",  # ANSI escape
    "\t": "\\t",
}

# Translation table for log sanitization (pre-computed for performance)
_LOG_SANITIZE_TABLE = str.maketrans(LOG_INJECTION_CHARS)

# Maximum string length before truncation
MAX_LOG_STRING_LENGTH = 500

_SENSITIVE_KEYS = (
    "api[_-]?key|secret|password|private[_-]?key|passwd|"
    "token|credentials?|auth[_-]?token|access[_-]?key|session[_-]?id"
)
_JSON_SENSITIVE = re.compile(rf'(?i)("(?:{_SENSITIVE_KEYS})"\s*:\s*)"[^"]*"')
_KV_SENSITIVE = re.compile(rf'(?i)((?:{_SENSITIVE_KEYS})\s*[:=]\s*)(?:[^\s"\'&,;)}}]+)')

_SEVERITY_MAP = {
    "critical": logging.CRITICAL,
    "high": logging.ERROR,
    "medium": logging.WARNING,
    "low": logging.INFO,
}

def _redact_sensitive_patterns(value: str) -> str:
    """Replace sensitive values (keys, tokens, passwords) with '***'."""
    value = _JSON_SENSITIVE.sub(r'\1"***"', value)
    value = _KV_SENSITIVE.sub(r'\1***', value)
    return value


def _sanitize_string(value: str) -> str:
    """Sanitize a string for logging - replaces dangerous chars, redacts secrets, and truncates."""
    result = value.translate(_LOG_SANITIZE_TABLE)
    result = _redact_sensitive_patterns(result)
    if len(result) > MAX_LOG_STRING_LENGTH:
        result = result[:MAX_LOG_STRING_LENGTH] + "...[truncated]"
    return result


def sanitize_for_log(value: Any) -> str:
    """
    Sanitize a value before logging to prevent log injection.
    
    Args:
        value: Value to sanitize (string, dict, list, or other)
        
    Returns:
        Safe string representation
    """
    match value:
        case None:
            return "null"
        case bool() | int() | float():
            return str(value)
        case str():
            return _sanitize_string(value)
        case dict():
            return json.dumps(
                {k: sanitize_for_log(v) for k, v in value.items()},
                ensure_ascii=True
            )
        case list() | tuple():
            return json.dumps([sanitize_for_log(item) for item in value])
        case _:
            return _sanitize_string(str(value))


class SecureLogger:
    """
    Secure logger wrapper that automatically sanitizes user input in log messages.
    Uses structured logging format for better security and parseability.
    """
    
    def __init__(self, name: str, level: int = logging.INFO) -> None:
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
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": level,
            "logger": self.name,
            "message": sanitize_for_log(message),
        }
        
        # Add extra fields with sanitization
        if kwargs:
            log_entry["data"] = {k: sanitize_for_log(v) for k, v in kwargs.items()}
        
        return json.dumps(log_entry, ensure_ascii=True)
    
    def info(self, message: str, *args: Any, **kwargs: Any):
        """Log info with sanitized data."""
        if args:
            try:
                message = message % args
            except (TypeError, ValueError):
                pass
        self.logger.log(logging.INFO, self._format_structured("INFO", message, **kwargs))
    
    def warning(self, message: str, *args: Any, **kwargs: Any):
        """Log warning with sanitized data."""
        if args:
            try:
                message = message % args
            except (TypeError, ValueError):
                pass
        self.logger.log(logging.WARNING, self._format_structured("WARNING", message, **kwargs))
    
    def error(self, message: str, *args: Any, **kwargs: Any):
        """Log error with sanitized data."""
        if args:
            try:
                message = message % args
            except (TypeError, ValueError):
                pass
        self.logger.log(logging.ERROR, self._format_structured("ERROR", message, **kwargs))
    
    def debug(self, message: str, *args: Any, **kwargs: Any):
        """Log debug with sanitized data."""
        if args:
            try:
                message = message % args
            except (TypeError, ValueError):
                pass
        self.logger.log(logging.DEBUG, self._format_structured("DEBUG", message, **kwargs))
    
    def critical(self, message: str, *args: Any, **kwargs: Any):
        """Log critical with sanitized data."""
        if args:
            try:
                message = message % args
            except (TypeError, ValueError):
                pass
        self.logger.log(logging.CRITICAL, self._format_structured("CRITICAL", message, **kwargs))
    
    def security_event(
        self,
        event_type: str,
        message: str,
        severity: str = "medium",
        **kwargs: Any
    ) -> None:
        """
        Log a security-related event with full context.
        
        Args:
            event_type: Type of security event (e.g., "auth_failure", "access_denied")
            message: Human-readable message
            severity: Event severity (low, medium, high, critical)
            **kwargs: Additional context data
        """
        self.logger.log(
            _SEVERITY_MAP.get(severity, logging.INFO),
            json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "type": "security_event",
                "event_type": sanitize_for_log(event_type),
                "severity": severity,
                "logger": self.name,
                "message": sanitize_for_log(message),
                **({"context": {k: sanitize_for_log(v) for k, v in kwargs.items()}} if kwargs else {})
            }, ensure_ascii=True)
        )
    
    def audit(
        self,
        action: str,
        resource: str,
        user_id: str | None = None,
        org_id: str | None = None,
        success: bool = True,
        **kwargs: Any
    ) -> None:
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
        self.logger.log(
            logging.INFO,
            json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "type": "audit",
                "action": sanitize_for_log(action),
                "resource": sanitize_for_log(resource),
                "success": success,
                "logger": self.name,
                **({"user_id": sanitize_for_log(user_id)} if user_id else {}),
                **({"org_id": sanitize_for_log(org_id)} if org_id else {}),
                **({"details": {k: sanitize_for_log(v) for k, v in kwargs.items()}} if kwargs else {}),
            }, ensure_ascii=True)
        )


# Pre-configured loggers for different modules
def get_security_logger() -> SecureLogger:
    """Get secure logger for security events."""
    return SecureLogger("hierachain.security")


def get_storage_logger() -> SecureLogger:
    """Get secure logger for storage and database operations."""
    return SecureLogger("hierachain.storage")


# Convenience function for quick sanitized logging
def log_user_action(
    logger: logging.Logger,
    level: int,
    message: str,
    user_input: Any = None,
    **kwargs: Any
) -> None:
    """
    Log a message with user input safely sanitized.
    
    Args:
        logger: Standard Python logger
        level: Log level (logging.INFO, etc.)
        message: Log message template
        user_input: User-provided input to sanitize
        **kwargs: Additional data to include
    """
    logger.log(level, json.dumps({
        "message": message,
        "user_input": sanitize_for_log(user_input) if user_input is not None else None,
        **({k: sanitize_for_log(v) for k, v in kwargs.items()} if kwargs else {}),
    }, ensure_ascii=True))
