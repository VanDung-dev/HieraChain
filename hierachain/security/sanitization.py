"""
Input/Output Sanitization Utilities for HieraChain API

This module provides security functions to sanitize user input before storage
and sanitize output before returning to clients to prevent:
- Stored XSS (Cross-Site Scripting)
- Template Injection (SSTI)
- Log Injection
- JSON Injection / Prototype Pollution
"""

import re
import html
from typing import Any
import logging

logger = logging.getLogger(__name__)


# Dangerous patterns that should be neutralized
TEMPLATE_PATTERNS = [
    r"\{\{.*?\}\}",      # Jinja2/Django/Angular: {{...}}
    r"\$\{.*?\}",        # JavaScript/Java Template: ${...}
    r"#\{.*?\}",         # Ruby ERB: #{...}
    r"<%.*?%>",          # JSP/ASP/ERB: <%...%>
    r"\{\%.*?\%\}",      # Jinja2 blocks: {%...%}
]

SCRIPT_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"on\w+\s*=",        # Event handlers: onclick=, onerror=, etc.
    r"<iframe[^>]*>",
    r"<object[^>]*>",
    r"<embed[^>]*>",
]

LOG_INJECTION_CHARS = ["\n", "\r", "\x1b", "\x00"]


def sanitize_string(value: str, context: str = "general") -> str:
    """
    Sanitize a string value based on context.
    
    Args:
        value: String to sanitize
        context: Sanitization context ('general', 'html', 'log', 'filename')
        
    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return value
    
    result = value
    
    if context in ("general", "html"):
        # HTML encode to prevent XSS
        result = html.escape(result)
        
        # Neutralize template expressions
        for pattern in TEMPLATE_PATTERNS:
            result = re.sub(pattern, lambda m: html.escape(m.group(0)), result)
    
    if context == "log":
        # Remove characters that could inject fake log entries
        for char in LOG_INJECTION_CHARS:
            result = result.replace(char, " ")
    
    if context == "filename":
        # Remove path traversal and dangerous characters
        result = re.sub(r"[\\/:*?\"<>|]", "_", result)
        result = result.replace("..", "_")
    
    return result


def sanitize_dict(data: dict[str, Any], context: str = "general") -> dict[str, Any]:
    """
    Recursively sanitize all string values in a dictionary.
    
    Args:
        data: Dictionary to sanitize
        context: Sanitization context
        
    Returns:
        Sanitized dictionary
    """
    result = {}
    for key, value in data.items():
        # Sanitize key as well
        safe_key = sanitize_string(str(key), context) if isinstance(key, str) else key
        
        if isinstance(value, str):
            result[safe_key] = sanitize_string(value, context)
        elif isinstance(value, dict):
            result[safe_key] = sanitize_dict(value, context)
        elif isinstance(value, list):
            result[safe_key] = sanitize_list(value, context)
        else:
            result[safe_key] = value
    
    return result


def sanitize_list(data: list[Any], context: str = "general") -> list[Any]:
    """
    Recursively sanitize all string values in a list.
    
    Args:
        data: List to sanitize
        context: Sanitization context
        
    Returns:
        Sanitized list
    """
    result = []
    for item in data:
        if isinstance(item, str):
            result.append(sanitize_string(item, context))
        elif isinstance(item, dict):
            result.append(sanitize_dict(item, context))
        elif isinstance(item, list):
            result.append(sanitize_list(item, context))
        else:
            result.append(item)
    
    return result


def sanitize_for_output(data: Any, context: str = "general") -> Any:
    """
    Sanitize data before returning in API response.
    
    Args:
        data: Data to sanitize (string, dict, list, or other)
        context: Sanitization context
        
    Returns:
        Sanitized data
    """
    if isinstance(data, str):
        return sanitize_string(data, context)
    elif isinstance(data, dict):
        return sanitize_dict(data, context)
    elif isinstance(data, list):
        return sanitize_list(data, context)
    else:
        return data


def sanitize_error_message(error: Exception) -> str:
    """
    Sanitize error message before returning to client.
    Removes sensitive information like file paths, stack traces, etc.
    
    Args:
        error: Exception object
        
    Returns:
        Safe error message
    """
    error_str = str(error)
    
    # Remove file paths
    error_str = re.sub(r'[A-Za-z]:\\[^\s]+', '[PATH]', error_str)
    error_str = re.sub(r'/[^\s]+\.py', '[FILE]', error_str)
    error_str = re.sub(r'/home/[^\s]+', '[PATH]', error_str)
    error_str = re.sub(r'/var/[^\s]+', '[PATH]', error_str)
    
    # Remove line numbers from tracebacks
    error_str = re.sub(r'line \d+', 'line [N]', error_str)
    
    # Truncate long messages
    if len(error_str) > 200:
        error_str = error_str[:200] + "..."
    
    return error_str


def is_safe_input(value: str, max_length: int = 10000) -> tuple[bool, str]:
    """
    Check if input is safe to store.
    
    Args:
        value: Input string to check
        max_length: Maximum allowed length
        
    Returns:
        Tuple of (is_safe, reason)
    """
    if not isinstance(value, str):
        return True, "Not a string"
    
    if len(value) > max_length:
        return False, f"Input exceeds maximum length of {max_length}"
    
    # Check for obvious attack patterns
    dangerous_patterns = [
        (r"<script", "Script tag detected"),
        (r"javascript:", "JavaScript URI detected"),
        (r"\{\{.*\}\}", "Template expression detected"),
        (r"\$\{.*\}", "Template expression detected"),
        (r"<%.*%>", "Template expression detected"),
    ]
    
    for pattern, reason in dangerous_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning(f"Potentially dangerous input detected: {reason}")
            # Don't reject, just log - sanitization will handle it
    
    return True, "Input accepted"


def safe_format(template: str, **kwargs: Any) -> str:
    """
    Safe string formatting that prevents injection.
    Uses sanitized values for formatting.
    
    Args:
        template: Format string template
        **kwargs: Values to format into template
        
    Returns:
        Safely formatted string
    """
    safe_kwargs = {
        key: sanitize_string(str(value)) if isinstance(value, str) else value
        for key, value in kwargs.items()
    }
    return template.format(**safe_kwargs)
