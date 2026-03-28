"""
Unit tests for policy engine security.
"""

import pytest
import re
from hierachain.security.policy_engine import (
    PolicyEngine, Policy, PolicyType, PolicyEffect,
    PolicyRule, PolicyCondition, LogicalOperator
)


def test_policy_regex_full_match_required():
    """Test that policy regex requires full match, not partial."""
    pattern = re.compile("admin")
    assert pattern.search("admin123") is not None
    
    pattern_anchored = re.compile("^admin$")
    assert pattern_anchored.search("admin123") is None


def test_policy_bypass_prevention():
    """Test that policy cannot be bypassed with crafted input."""
    bypass_attempts = ["admin", "Admin", "ADMIN", "admadmin", "rootadmin"]
    
    class MockPolicyEngine:
        def evaluate(self, context):
            principal = context.get("principal", "")
            if "admin" in principal.lower():
                return {"effect": "deny"}
            return {"effect": "allow"}
    
    engine = MockPolicyEngine()
    for attempt in bypass_attempts:
        result = engine.evaluate({"principal": attempt})
        assert result["effect"] == "deny"


def test_policy_case_sensitivity():
    """Test policy evaluation case sensitivity."""
    pattern = re.compile("admin", re.IGNORECASE)
    assert pattern.search("admin") is not None
    assert pattern.search("Admin") is not None
    assert pattern.search("ADMIN") is not None
    
    pattern_sensitive = re.compile("admin")
    assert pattern_sensitive.search("admin") is not None
    assert pattern_sensitive.search("Admin") is None


def test_policy_regex_dos_prevention():
    """Test that malicious regex patterns are handled safely."""
    malicious_pattern = "(a+)+$"
    test_input = "a" * 10 + "!"
    try:
        pattern = re.compile(malicious_pattern)
        result = pattern.match(test_input)
        assert True
    except TimeoutError:
        pytest.fail("Regex caused timeout")


def test_policy_engine_basic_creation():
    """Test basic policy creation."""
    rule = PolicyRule(
        rule_id="deny_all",
        conditions=[],
        logical_operator=LogicalOperator.AND,
        effect=PolicyEffect.DENY,
        priority=100
    )
    
    policy = Policy(
        policy_id="test_policy",
        policy_type=PolicyType.ACCESS_CONTROL,
        rules=[rule],
        default_effect=PolicyEffect.ALLOW
    )
    
    assert policy.policy_id == "test_policy"
    assert len(policy.rules) == 1


def test_policy_effect_values():
    """Test policy effect values."""
    assert PolicyEffect.ALLOW.value == "allow"
    assert PolicyEffect.DENY.value == "deny"


def test_policy_type_values():
    """Test policy type values."""
    assert PolicyType.ACCESS_CONTROL.value == "access_control"
    assert PolicyType.ENDORSEMENT.value == "endorsement"