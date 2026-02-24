"""
Unit tests for BruteForceProtector module.

Tests cover failure tracking, lockout enforcement, expiry,
multi-IP independence, security logging, and integration with
APIKeyVerifier returning HTTP 429.
"""

import time
import pytest
import asyncio
from unittest.mock import Mock, patch
from fastapi import HTTPException

from hierachain.security.verify.api_key_verifier import APIKeyVerifier
from hierachain.security.brute_force_protector import BruteForceProtector


# --- Fixtures ---

@pytest.fixture
def default_protector():
    """Create a BruteForceProtector with default settings."""
    return BruteForceProtector()


@pytest.fixture
def strict_protector():
    """Create a strict protector (low thresholds for testing)."""
    return BruteForceProtector({
        "max_failures": 3,
        "lockout_duration": 2,
        "tracking_window": 5,
    })


# --- Test: Basic Failure Tracking ---

def test_no_lockout_below_threshold(default_protector):
    """Failures below threshold should not cause lockout."""
    for _ in range(4):  # Default max is 5
        result = default_protector.record_failure("1.2.3.4", "hrc_test")
        assert result is False

    assert not default_protector.is_locked_out("1.2.3.4")


def test_lockout_at_threshold(strict_protector):
    """Reaching the threshold should trigger lockout."""
    for i in range(2):
        result = strict_protector.record_failure("1.2.3.4", "hrc_test")
        assert result is False

    # Third attempt (at threshold) should trigger lockout
    result = strict_protector.record_failure("1.2.3.4", "hrc_test")
    assert result is True
    assert strict_protector.is_locked_out("1.2.3.4")


def test_failure_count_tracking(strict_protector):
    """Test failure count is tracked correctly."""
    assert strict_protector.get_failure_count("1.2.3.4") == 0

    strict_protector.record_failure("1.2.3.4", "key1")
    assert strict_protector.get_failure_count("1.2.3.4") == 1

    strict_protector.record_failure("1.2.3.4", "key2")
    assert strict_protector.get_failure_count("1.2.3.4") == 2


# --- Test: Lockout Expiry ---

def test_lockout_expires(strict_protector):
    """Lockout should expire after lockout_duration."""
    # Trigger lockout (threshold = 3, lockout = 2s)
    for _ in range(3):
        strict_protector.record_failure("1.2.3.4", "hrc_test")

    assert strict_protector.is_locked_out("1.2.3.4")
    assert strict_protector.get_remaining_lockout("1.2.3.4") > 0

    # Wait for lockout to expire
    time.sleep(2.1)

    assert not strict_protector.is_locked_out("1.2.3.4")
    assert strict_protector.get_remaining_lockout("1.2.3.4") == 0.0


def test_remaining_lockout_not_locked(default_protector):
    """Remaining lockout should be 0 when not locked out."""
    assert default_protector.get_remaining_lockout("1.2.3.4") == 0.0


# --- Test: Tracking Window ---

def test_tracking_window_expiry():
    """Failures outside tracking window should not count."""
    protector = BruteForceProtector({
        "max_failures": 3,
        "lockout_duration": 60,
        "tracking_window": 1,  # 1 second window
    })

    protector.record_failure("1.2.3.4", "key1")
    protector.record_failure("1.2.3.4", "key2")
    assert protector.get_failure_count("1.2.3.4") == 2

    # Wait for tracking window to expire
    time.sleep(1.2)

    # Old failures should be expired
    assert protector.get_failure_count("1.2.3.4") == 0

    # New failure should start fresh
    protector.record_failure("1.2.3.4", "key3")
    assert protector.get_failure_count("1.2.3.4") == 1


# --- Test: Multi-IP Independence ---

def test_independent_ip_tracking(strict_protector):
    """Different IPs should be tracked independently."""
    # Lock out IP 1
    for _ in range(3):
        strict_protector.record_failure("1.1.1.1", "key1")

    assert strict_protector.is_locked_out("1.1.1.1")
    assert not strict_protector.is_locked_out("2.2.2.2")

    # IP 2 can still fail without being locked
    strict_protector.record_failure("2.2.2.2", "key2")
    assert not strict_protector.is_locked_out("2.2.2.2")


# --- Test: Manual Reset ---

def test_manual_reset(strict_protector):
    """Manual reset should clear lockout and failures."""
    for _ in range(3):
        strict_protector.record_failure("1.2.3.4", "key1")

    assert strict_protector.is_locked_out("1.2.3.4")

    strict_protector.reset("1.2.3.4")

    assert not strict_protector.is_locked_out("1.2.3.4")
    assert strict_protector.get_failure_count("1.2.3.4") == 0


def test_reset_nonexistent_ip(default_protector):
    """Reset on a non-tracked IP should not raise errors."""
    default_protector.reset("9.9.9.9")  # Should not raise


# --- Test: Security Logging ---

def test_brute_force_detection_logged(strict_protector):
    """Security event should be logged when brute-force is detected."""
    with patch.object(
        BruteForceProtector,
        '_log_brute_force_detected'
    ) as mock_log:
        for _ in range(3):
            strict_protector.record_failure("1.2.3.4", "hrc_att")

        mock_log.assert_called_once_with("1.2.3.4", "hrc_att", 3)


# --- Test: Failures Reset After Lockout ---

def test_failures_reset_after_lockout(strict_protector):
    """Failure count should be reset to 0 after lockout is triggered."""
    for _ in range(3):
        strict_protector.record_failure("1.2.3.4", "key1")

    assert strict_protector.is_locked_out("1.2.3.4")
    # After lockout, failure count should be reset
    assert strict_protector.get_failure_count("1.2.3.4") == 0


# --- Test: Integration with APIKeyVerifier ---

def test_api_key_verifier_returns_429_when_locked_out():
    """APIKeyVerifier should return 429 when IP is locked out."""
    config = {
        "enabled": True,
        "key_location": "header",
        "key_name": "x-api-key",
        "brute_force": {
            "max_failures": 2,
            "lockout_duration": 60,
            "tracking_window": 300,
        },
    }

    verifier = APIKeyVerifier(config)

    # Create mock request with client IP
    mock_request = Mock()
    mock_request.client = Mock()
    mock_request.client.host = "10.0.0.1"

    # Mock key_manager to always return invalid
    verifier.key_manager.is_valid = Mock(return_value=False)

    # Trigger failures to cause lockout
    for _ in range(2):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                verifier(mock_request, "invalid_key_12345678")
            )
        assert exc_info.value.status_code == 401

    # Next attempt should be 429 (locked out)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.get_event_loop().run_until_complete(
            verifier(mock_request, "any_key_123456789")
        )
    assert exc_info.value.status_code == 429
    assert "Too many failed" in exc_info.value.detail


def test_api_key_verifier_records_failure_on_invalid_key():
    """APIKeyVerifier should record failure on invalid API key."""
    config = {
        "enabled": True,
        "key_location": "header",
        "key_name": "x-api-key",
        "brute_force": {
            "max_failures": 10,
            "lockout_duration": 60,
            "tracking_window": 300,
        },
    }

    verifier = APIKeyVerifier(config)

    mock_request = Mock()
    mock_request.client = Mock()
    mock_request.client.host = "10.0.0.2"

    verifier.key_manager.is_valid = Mock(return_value=False)

    with pytest.raises(HTTPException):
        asyncio.get_event_loop().run_until_complete(
            verifier(mock_request, "invalid_key_12345678")
        )

    # Verify failure was recorded
    count = verifier.brute_force_protector.get_failure_count(
        "10.0.0.2"
    )
    assert count == 1


# --- Test: Default Configuration ---

def test_default_configuration():
    """Test BruteForceProtector with default configuration."""
    protector = BruteForceProtector()

    assert protector.max_failures == 5
    assert protector.lockout_duration == 900
    assert protector.tracking_window == 300


def test_custom_configuration():
    """Test BruteForceProtector with custom configuration."""
    protector = BruteForceProtector({
        "max_failures": 10,
        "lockout_duration": 1800,
        "tracking_window": 600,
    })

    assert protector.max_failures == 10
    assert protector.lockout_duration == 1800
    assert protector.tracking_window == 600
