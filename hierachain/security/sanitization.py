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


def _sanitize_html_context(value: str) -> str:
    """Sanitize for HTML/general context - prevents XSS and template injection."""
    result = html.escape(value)

    def _neutralize_match(match: re.Match[str]) -> str:
        return html.escape(match.group(0))

    # Neutralize template expressions with single regex pass
    combined_pattern = "|".join(TEMPLATE_PATTERNS)
    return re.sub(combined_pattern, _neutralize_match, result)


def _sanitize_log_context(value: str) -> str:
    """Sanitize for log context - prevents log injection."""
    return value.translate({ord(c): ord(" ") for c in LOG_INJECTION_CHARS})


def _sanitize_filename_context(value: str) -> str:
    """Sanitize for filename context - prevents path traversal."""
    result = re.sub(r"[\\/:*?\"<>|]", "_", value)
    return result.replace("..", "_")


# Context-specific sanitizers mapping
_CONTEXT_SANITIZERS = {
    "general": _sanitize_html_context,
    "html": _sanitize_html_context,
    "log": _sanitize_log_context,
    "filename": _sanitize_filename_context,
}


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
    
    sanitizer = _CONTEXT_SANITIZERS.get(context)
    return sanitizer(value) if sanitizer else value


def _sanitize_value(value: Any, context: str) -> Any:
    """Sanitize a single value based on its type using pattern matching."""
    match value:
        case str():
            return sanitize_string(value, context)
        case dict():
            return sanitize_dict(value, context)
        case list():
            return sanitize_list(value, context)
        case _:
            return value


def sanitize_dict(data: dict[str, Any], context: str = "general") -> dict[str, Any]:
    """
    Recursively sanitize all string values in a dictionary.
    
    Args:
        data: Dictionary to sanitize
        context: Sanitization context
        
    Returns:
        Sanitized dictionary
    """
    return {
        sanitize_string(str(key), context)
        if isinstance(key, str) else key: _sanitize_value(value, context)
        for key, value in data.items()
    }


def sanitize_list(data: list[Any], context: str = "general") -> list[Any]:
    """
    Recursively sanitize all string values in a list.
    
    Args:
        data: List to sanitize
        context: Sanitization context
        
    Returns:
        Sanitized list
    """
    return [_sanitize_value(item, context) for item in data]


def sanitize_for_output(data: Any, context: str = "general") -> Any:
    """
    Sanitize data before returning in API response.
    
    Args:
        data: Data to sanitize (string, dict, list, or other)
        context: Sanitization context
        
    Returns:
        Sanitized data
    """
    match data:
        case str():
            return sanitize_string(data, context)
        case dict():
            return sanitize_dict(data, context)
        case list():
            return sanitize_list(data, context)
        case _:
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
    error_str = re.sub(r'[A-Za-z]:\\\S+', '[PATH]', error_str)
    error_str = re.sub(r'/\S+\.(?:py|so|dll|dylib|json|yaml|yml|ini|db|log|txt|xml|toml)', '[PATH]/[FILE]', error_str)
    error_str = re.sub(r'/(?:home|var|app|opt|tmp|usr|etc|lib|bin|sbin)/\S+', '[PATH]', error_str)
    
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
            logger.warning("Potentially dangerous input rejected: %s", reason)
            # Reject dangerous input instead of just logging
            return False, f"Input rejected: {reason}"
    
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


class ValidationError(ValueError):
    """Custom exception for validation failures."""
    pass


def validate_numeric_bounds(
    value: int | float,
    min_val: int | float | None = None,
    max_val: int | float | None = None,
    field_name: str = "value"
) -> int | float:
    """
    Validate that a numeric value is within specified bounds.

    Args:
        value: The numeric value to validate.
        min_val: Minimum allowed value (inclusive). None means no lower bound.
        max_val: Maximum allowed value (inclusive). None means no upper bound.
        field_name: Name of the field for error messages.

    Returns:
        The validated value if within bounds.

    Raises:
        ValidationError: If value is outside bounds or not a number.
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(
            f"{field_name} must be numeric, got {type(value).__name__}"
        )

    if min_val is not None and value < min_val:
        raise ValidationError(f"{field_name} must be >= {min_val}, got {value}")

    if max_val is not None and value > max_val:
        raise ValidationError(f"{field_name} must be <= {max_val}, got {value}")

    return value


def validate_timestamp(
    timestamp: float, max_drift_seconds: float = 300.0
) -> float:
    """
    Validate that a timestamp is within acceptable drift from current time.

    Prevents replay attacks and clock-skew manipulation.

    Args:
        timestamp: Unix timestamp to validate.
        max_drift_seconds: Maximum allowed drift from current time (default 5 min).

    Returns:
        The validated timestamp.

    Raises:
        ValidationError: If timestamp is too far from current time.
    """
    import time
    current_time = time.time()

    if timestamp < 0:
        raise ValidationError(f"Timestamp must be positive, got {timestamp}")

    drift = abs(current_time - timestamp)
    if drift > max_drift_seconds:
        raise ValidationError(
            f"Timestamp drift {drift:.1f}s exceeds max {max_drift_seconds}s"
        )

    return timestamp


def validate_block_index(block_index: int, max_index: int | None = None) -> int:
    """
    Validate that a block index is valid.

    Args:
        block_index: Block index to validate.
        max_index: Maximum allowed block index (optional, for chain-aware validation).

    Returns:
        The validated block index.

    Raises:
        ValidationError: If block index is invalid.
    """
    if not isinstance(block_index, int):
        raise ValidationError(
            f"block_index must be int, got {type(block_index).__name__}"
        )

    if block_index < 0:
        raise ValidationError(f"block_index must be >= 0, got {block_index}")

    if max_index is not None and block_index > max_index:
        raise ValidationError(
            f"block_index {block_index} exceeds max allowed {max_index}"
        )

    return block_index


def validate_amount(
    amount: int | float,
    min_amount: float = 0.0,
    max_amount: float | None = None
) -> int | float:
    """
    Validate that an amount (e.g., token amount) is valid.

    Args:
        amount: The amount to validate.
        min_amount: Minimum allowed amount (default 0, no negative amounts).
        max_amount: Maximum allowed amount (optional, for overflow prevention).

    Returns:
        The validated amount.

    Raises:
        ValidationError: If amount is invalid.
    """
    return validate_numeric_bounds(
        amount,
        min_val=min_amount,
        max_val=max_amount,
        field_name="amount"
    )
