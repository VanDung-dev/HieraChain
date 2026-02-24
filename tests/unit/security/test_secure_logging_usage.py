"""
Unit tests to verify SecureLogger usage in security-sensitive modules.

Ensures that modules handling security events use SecureLogger instead of
raw logging.getLogger, and that security_event() is called for key actions.
"""

import ast
import os
from unittest.mock import patch

import pytest

from hierachain.security.secure_logging import SecureLogger


# ------------------------------------------------------------------ #
# Source code analysis: verify SecureLogger is instantiated
# ------------------------------------------------------------------ #

# Modules that MUST use SecureLogger (not logging.getLogger)
SECURITY_MODULES = [
    os.path.join("hierachain", "security", "key_manager.py"),
    os.path.join("hierachain", "security", "identity.py"),
    os.path.join("hierachain", "api", "v1", "endpoints.py"),
    os.path.join("hierachain", "api", "v3", "endpoints.py"),
]

# Project root: two levels above 'tests/unit'
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir)
)


def _get_top_level_assignments(filepath: str) -> list[str]:
    """Parse a Python file and return top-level assignment source lines."""
    abs_path = os.path.join(_PROJECT_ROOT, filepath)
    with open(abs_path, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    lines = source.splitlines()
    assignments = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for line_no in range(node.lineno, node.end_lineno + 1):
                assignments.append(lines[line_no - 1])
    return assignments


class TestSecureLoggerAdoption:
    """Verify that security-sensitive modules use SecureLogger."""

    @pytest.mark.parametrize("module_path", SECURITY_MODULES)
    def test_module_uses_secure_logger(self, module_path):
        """Module should contain SecureLogger instantiation, not
        logging.getLogger for its main logger."""
        abs_path = os.path.join(_PROJECT_ROOT, module_path)
        with open(abs_path, encoding="utf-8") as f:
            source = f.read()

        assert "SecureLogger" in source, (
            f"{module_path} does not use SecureLogger"
        )

    @pytest.mark.parametrize("module_path", SECURITY_MODULES)
    def test_module_does_not_use_raw_getlogger_for_main_logger(
        self, module_path
    ):
        """The main logger variable should NOT be logging.getLogger."""
        assignments = _get_top_level_assignments(module_path)
        for line in assignments:
            stripped = line.strip()
            if stripped.startswith("logger") and "=" in stripped:
                assert "logging.getLogger" not in stripped, (
                    f"{module_path} still uses logging.getLogger "
                    f"for its main logger: {stripped}"
                )


# ------------------------------------------------------------------ #
# SecureLogger behaviour
# ------------------------------------------------------------------ #

class TestSecureLoggerSanitization:
    """Verify that SecureLogger sanitizes dangerous characters."""

    def test_newline_in_log_message_sanitized(self):
        """Newlines in log messages should be escaped."""
        secure = SecureLogger("test.sanitize")
        with patch.object(
            secure.logger, "info"
        ) as mock_info:
            secure.info("line1\nline2", user_data="a\nb")
            mock_info.assert_called_once()
            call_arg = mock_info.call_args[0][0]
            # The structured JSON output should not contain raw newlines
            assert "\n" not in call_arg

    def test_ansi_escape_in_log_sanitized(self):
        """ANSI escape codes should be stripped."""
        secure = SecureLogger("test.ansi")
        with patch.object(
            secure.logger, "warning"
        ) as mock_warn:
            secure.warning("normal\x1b[31mred\x1b[0m")
            mock_warn.assert_called_once()
            call_arg = mock_warn.call_args[0][0]
            assert "\x1b" not in call_arg


# ------------------------------------------------------------------ #
# security_event() smoke test
# ------------------------------------------------------------------ #

class TestSecurityEventLogging:
    """Verify security_event() produces structured output."""

    def test_security_event_outputs_structured_json(self):
        secure = SecureLogger("test.events")
        with patch.object(
            secure.logger, "error"
        ) as mock_error:
            secure.security_event(
                event_type="test_event",
                message="Something happened",
                severity="high",
                extra_key="extra_value",
            )
            mock_error.assert_called_once()
            call_arg = mock_error.call_args[0][0]
            assert "test_event" in call_arg
            assert "security_event" in call_arg

    def test_audit_outputs_structured_json(self):
        secure = SecureLogger("test.audit")
        with patch.object(
            secure.logger, "info"
        ) as mock_info:
            secure.audit(
                action="create",
                resource="chain",
                user_id="user_1",
                success=True,
            )
            mock_info.assert_called_once()
            call_arg = mock_info.call_args[0][0]
            assert "audit" in call_arg
            assert "create" in call_arg
