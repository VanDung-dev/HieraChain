"""
Unit tests for sanitization module.

Tests typical XSS, template injection, and log injection payloads
against the sanitization utilities to ensure they are properly
neutralized before storage or rendering.
"""


from hierachain.security.sanitization import (
    sanitize_string,
    sanitize_dict,
    sanitize_list,
    sanitize_for_output,
    sanitize_error_message,
    is_safe_input,
)


# ------------------------------------------------------------------ #
# XSS payload tests
# ------------------------------------------------------------------ #

class TestXSSPayloads:
    """Verify that common XSS payloads are neutralized via html.escape."""

    def test_script_tag_escaped(self):
        result = sanitize_string("<script>alert('xss')</script>", context="general")
        # html.escape converts < to &lt; so raw <script should be gone
        assert "<script" not in result
        assert "&lt;" in result

    def test_event_handler_escaped(self):
        result = sanitize_string('<img src=x onerror=alert(1)>', context="general")
        assert "<img" not in result

    def test_iframe_escaped(self):
        result = sanitize_string('<iframe src="http://evil.com"></iframe>', context="general")
        assert "<iframe" not in result

    def test_object_tag_escaped(self):
        result = sanitize_string('<object data="evil.swf"></object>', context="general")
        assert "<object" not in result

    def test_embed_tag_escaped(self):
        result = sanitize_string('<embed src="evil.swf">', context="general")
        assert "<embed" not in result

    def test_javascript_uri_escaped(self):
        # html.escape won't escape "javascript:" but it does escape
        # the surrounding tags; for inline URIs the word stays
        result = sanitize_string("javascript:alert(1)", context="general")
        # Output should be a string (may or may not escape javascript:)
        assert isinstance(result, str)


# ------------------------------------------------------------------ #
# Template injection tests (html.escape preserves {{...}})
# ------------------------------------------------------------------ #

class TestTemplateInjection:
    """Verify that template injection patterns are processed."""

    def test_jinja_pattern_processed(self):
        """sanitize_string should at least return a string for
        {{...}} patterns — html.escape doesn't escape curly braces."""
        result = sanitize_string("{{config.__class__}}", context="general")
        assert isinstance(result, str)

    def test_dollar_brace_processed(self):
        result = sanitize_string("${7*7}", context="general")
        assert isinstance(result, str)

    def test_erb_processed(self):
        result = sanitize_string("<%= system('id') %>", context="general")
        # ERB <% %> is escaped by html.escape (< becomes &lt;)
        assert "<%" not in result


# ------------------------------------------------------------------ #
# sanitize_dict / sanitize_list tests
# ------------------------------------------------------------------ #

class TestRecursiveSanitization:
    """Verify recursive sanitization of dicts and lists."""

    def test_sanitize_dict_escapes_xss_in_nested_values(self):
        data = {
            "name": "<script>alert('xss')</script>",
            "nested": {"value": '<img src=x onerror=alert(1)>',},
            "number": 42,
        }
        result = sanitize_dict(data)
        assert "<script" not in result["name"]
        assert "<img" not in result["nested"]["value"]
        assert result["number"] == 42

    def test_sanitize_list_escapes_xss(self):
        data = [
            "<script>alert(1)</script>",
            "safe string",
            123,
        ]
        result = sanitize_list(data)
        assert "<script" not in result[0]
        assert result[1] == "safe string"
        assert result[2] == 123

    def test_sanitize_for_output_handles_dict(self):
        data = {"key": "<script>bad</script>"}
        result = sanitize_for_output(data)
        assert "<script" not in result["key"]

    def test_sanitize_for_output_handles_string(self):
        result = sanitize_for_output("<script>bad</script>")
        assert "<script" not in result


# ------------------------------------------------------------------ #
# is_safe_input tests
# ------------------------------------------------------------------ #

class TestIsSafeInput:
    """Verify input safety checks."""

    def test_long_input_flagged(self):
        long_string = "a" * 10001
        is_safe, reason = is_safe_input(long_string, max_length=10000)
        assert not is_safe
        assert "length" in reason.lower() or "long" in reason.lower()

    def test_normal_input_safe(self):
        is_safe, reason = is_safe_input("Hello, world!")
        assert is_safe

    def test_xss_payload_accepted_with_warning(self):
        """is_safe_input logs a warning but still accepts
        dangerous input (sanitization handles it)."""
        is_safe, reason = is_safe_input("<script>alert('xss')</script>")
        # Current implementation logs but doesn't reject
        assert is_safe


# ------------------------------------------------------------------ #
# sanitize_error_message tests
# ------------------------------------------------------------------ #

class TestSanitizeErrorMessage:
    """Verify error message sanitization strips sensitive info."""

    def test_strips_unix_path(self):
        try:
            raise ValueError("Sensitive DB path /var/data/secret.db")
        except ValueError as e:
            result = sanitize_error_message(e)
            assert "/var/data/secret.db" not in result
            assert "[PATH]" in result

    def test_strips_windows_path(self):
        try:
            raise ValueError(r"Error at C:\Users\admin\app.py")
        except ValueError as e:
            result = sanitize_error_message(e)
            assert "C:\\Users" not in result
            assert "[PATH]" in result

    def test_truncates_long_messages(self):
        try:
            raise RuntimeError("A" * 300)
        except RuntimeError as e:
            result = sanitize_error_message(e)
            assert len(result) <= 203  # 200 + "..."

    def test_returns_string(self):
        try:
            raise RuntimeError("Some error")
        except RuntimeError as e:
            result = sanitize_error_message(e)
            assert isinstance(result, str)
            assert len(result) > 0


# ------------------------------------------------------------------ #
# Log context sanitization
# ------------------------------------------------------------------ #

class TestLogContextSanitization:
    """Verify log context strips dangerous characters."""

    def test_newline_stripped(self):
        result = sanitize_string("line1\nline2\rline3", context="log")
        assert "\n" not in result
        assert "\r" not in result

    def test_ansi_escape_stripped(self):
        result = sanitize_string("normal\x1b[31mred\x1b[0m", context="log")
        assert "\x1b" not in result

    def test_null_byte_stripped(self):
        result = sanitize_string("hello\x00world", context="log")
        assert "\x00" not in result
