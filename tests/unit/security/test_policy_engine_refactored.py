"""
Additional unit tests for refactored PolicyCondition and PolicyEngine methods.
"""

import pytest
from hierachain.security.policy_engine import (
    PolicyEngine, Policy, PolicyType, PolicyEffect,
    PolicyRule, PolicyCondition, LogicalOperator, ComparisonOperator
)


class TestPolicyConditionRefactored:
    """Test refactored PolicyCondition helper methods."""

    def test_check_contains_string(self):
        """Test _check_contains with string."""
        condition = PolicyCondition(
            attribute="role",
            operator=ComparisonOperator.CONTAINS,
            value="admin"
        )
        context = {"role": "administrator"}
        assert condition.evaluate(context) is True

        context = {"role": "user"}
        assert condition.evaluate(context) is False

    def test_check_contains_list(self):
        """Test _check_contains with list."""
        condition = PolicyCondition(
            attribute="tags",
            operator=ComparisonOperator.CONTAINS,
            value="critical"
        )
        context = {"tags": ["high", "critical", "low"]}
        assert condition.evaluate(context) is True

        context = {"tags": ["high", "low"]}
        assert condition.evaluate(context) is False

    def test_check_not_contains(self):
        """Test _check_not_contains."""
        condition = PolicyCondition(
            attribute="role",
            operator=ComparisonOperator.NOT_CONTAINS,
            value="guest"
        )
        context = {"role": "admin"}
        assert condition.evaluate(context) is True

        context = {"role": "guest_user"}
        assert condition.evaluate(context) is False

    def test_check_in_string(self):
        """Test _check_in with string."""
        condition = PolicyCondition(
            attribute="status",
            operator=ComparisonOperator.IN,
            value=["active", "pending"]
        )
        context = {"status": "active"}
        assert condition.evaluate(context) is True

        context = {"status": "inactive"}
        assert condition.evaluate(context) is False

    def test_check_in_list(self):
        """Test _check_in with list membership."""
        condition = PolicyCondition(
            attribute="value",
            operator=ComparisonOperator.IN,
            value=[1, 2, 3]
        )
        context = {"value": 2}
        assert condition.evaluate(context) is True

        context = {"value": 5}
        assert condition.evaluate(context) is False

    def test_check_not_in(self):
        """Test _check_not_in."""
        condition = PolicyCondition(
            attribute="status",
            operator=ComparisonOperator.NOT_IN,
            value=["blocked", "suspended"]
        )
        context = {"status": "active"}
        assert condition.evaluate(context) is True

        context = {"status": "blocked"}
        assert condition.evaluate(context) is False

    def test_check_matches_exact(self):
        """Test _check_matches with exact pattern."""
        condition = PolicyCondition(
            attribute="email",
            operator=ComparisonOperator.MATCHES,
            value=r"^[\w\.-]+@example\.com$"
        )
        context = {"email": "user@example.com"}
        assert condition.evaluate(context) is True

        context = {"email": "user@other.com"}
        assert condition.evaluate(context) is False

    def test_check_matches_partial_not_allowed(self):
        """Test that partial matches are NOT allowed (anchors enforced)."""
        condition = PolicyCondition(
            attribute="username",
            operator=ComparisonOperator.MATCHES,
            value="admin"
        )
        # Without anchors, "admin123" would match partially, but we add anchors
        context = {"username": "admin123"}
        assert condition.evaluate(context) is False

        context = {"username": "admin"}
        assert condition.evaluate(context) is True

    def test_check_not_matches(self):
        """Test NOT_MATCHES operator."""
        condition = PolicyCondition(
            attribute="username",
            operator=ComparisonOperator.NOT_MATCHES,
            value="admin"
        )
        context = {"username": "admin123"}
        assert condition.evaluate(context) is True  # does not match exactly

        context = {"username": "admin"}
        assert condition.evaluate(context) is False  # matches exactly

    def test_numeric_comparisons(self):
        """Test numeric comparison operators."""
        # Greater than
        condition = PolicyCondition(
            attribute="age", operator=ComparisonOperator.GREATER_THAN, value=18
        )
        assert condition.evaluate({"age": 25}) is True
        assert condition.evaluate({"age": 18}) is False

        # Greater or equal
        condition = PolicyCondition(
            attribute="age", operator=ComparisonOperator.GREATER_OR_EQUAL, value=18
        )
        assert condition.evaluate({"age": 25}) is True
        assert condition.evaluate({"age": 18}) is True

        # Less than
        condition = PolicyCondition(
            attribute="age", operator=ComparisonOperator.LESS_THAN, value=18
        )
        assert condition.evaluate({"age": 15}) is True
        assert condition.evaluate({"age": 18}) is False

        # Less or equal
        condition = PolicyCondition(
            attribute="age", operator=ComparisonOperator.LESS_OR_EQUAL, value=18
        )
        assert condition.evaluate({"age": 15}) is True
        assert condition.evaluate({"age": 18}) is True

    def test_equals_and_not_equals(self):
        """Test equality operators."""
        condition = PolicyCondition(
            attribute="role", operator=ComparisonOperator.EQUALS, value="admin"
        )
        assert condition.evaluate({"role": "admin"}) is True
        assert condition.evaluate({"role": "user"}) is False

        condition = PolicyCondition(
            attribute="role", operator=ComparisonOperator.NOT_EQUALS, value="admin"
        )
        assert condition.evaluate({"role": "user"}) is True
        assert condition.evaluate({"role": "admin"}) is False


class TestPolicyEngineRefactored:
    """Test refactored PolicyEngine methods."""

    def test_combine_all_allow_all_true(self):
        """Test _combine_all_allow when all policies allow."""
        engine = PolicyEngine()
        results = [
            {"effect": "allow"},
            {"effect": "allow"},
            {"effect": "allow"}
        ]
        assert engine._combine_all_allow(results) == "allow"

    def test_combine_all_allow_one_deny(self):
        """Test _combine_all_allow with one deny."""
        engine = PolicyEngine()
        results = [
            {"effect": "allow"},
            {"effect": "deny"},
            {"effect": "allow"}
        ]
        assert engine._combine_all_allow(results) == "deny"

    def test_combine_any_allow_at_least_one(self):
        """Test _combine_any_allow with at least one allow."""
        engine = PolicyEngine()
        results = [
            {"effect": "deny"},
            {"effect": "allow"},
            {"effect": "deny"}
        ]
        assert engine._combine_any_allow(results) == "allow"

    def test_combine_any_allow_all_deny(self):
        """Test _combine_any_allow when all deny."""
        engine = PolicyEngine()
        results = [
            {"effect": "deny"},
            {"effect": "deny"}
        ]
        assert engine._combine_any_allow(results) == "deny"

    def test_combine_majority_allow_majority(self):
        """Test _combine_majority_allow with majority allow."""
        engine = PolicyEngine()
        results = [
            {"effect": "allow"},
            {"effect": "allow"},
            {"effect": "deny"}
        ]
        assert engine._combine_majority_allow(results) == "allow"

    def test_combine_majority_allow_tie(self):
        """Test _combine_majority_allow with tie (should deny)."""
        engine = PolicyEngine()
        results = [
            {"effect": "allow"},
            {"effect": "deny"}
        ]
        assert engine._combine_majority_allow(results) == "deny"

    def test_combine_majority_allow_minority(self):
        """Test _combine_majority_allow with minority allow."""
        engine = PolicyEngine()
        results = [
            {"effect": "deny"},
            {"effect": "deny"},
            {"effect": "allow"}
        ]
        assert engine._combine_majority_allow(results) == "deny"

    def test_evaluate_policy_set_all_allow(self):
        """Test evaluate_policy_set with all_allow logic."""
        engine = PolicyEngine()

        # Create two policies that both allow
        rule1 = PolicyRule(
            rule_id="rule1",
            conditions=[],
            logical_operator=LogicalOperator.AND,
            effect=PolicyEffect.ALLOW
        )
        policy1 = Policy(
            policy_id="policy1",
            policy_type=PolicyType.ACCESS_CONTROL,
            rules=[rule1]
        )

        rule2 = PolicyRule(
            rule_id="rule2",
            conditions=[],
            logical_operator=LogicalOperator.AND,
            effect=PolicyEffect.ALLOW
        )
        policy2 = Policy(
            policy_id="policy2",
            policy_type=PolicyType.ACCESS_CONTROL,
            rules=[rule2]
        )

        engine.register_policy(policy1)
        engine.register_policy(policy2)
        engine.create_policy_set("test_set", ["policy1", "policy2"])

        result = engine.evaluate_policy_set("test_set", {}, "all_allow")
        assert result["effect"] == "allow"

    def test_evaluate_policy_set_any_allow(self):
        """Test evaluate_policy_set with any_allow logic."""
        engine = PolicyEngine()

        # First policy denies, second allows
        rule1 = PolicyRule(
            rule_id="rule1",
            conditions=[],
            logical_operator=LogicalOperator.AND,
            effect=PolicyEffect.DENY
        )
        policy1 = Policy(
            policy_id="policy1",
            policy_type=PolicyType.ACCESS_CONTROL,
            rules=[rule1]
        )

        rule2 = PolicyRule(
            rule_id="rule2",
            conditions=[],
            logical_operator=LogicalOperator.AND,
            effect=PolicyEffect.ALLOW
        )
        policy2 = Policy(
            policy_id="policy2",
            policy_type=PolicyType.ACCESS_CONTROL,
            rules=[rule2]
        )

        engine.register_policy(policy1)
        engine.register_policy(policy2)
        engine.create_policy_set("test_set", ["policy1", "policy2"])

        result = engine.evaluate_policy_set("test_set", {}, "any_allow")
        assert result["effect"] == "allow"

    def test_evaluate_policy_set_majority_allow(self):
        """Test evaluate_policy_set with majority_allow logic."""
        engine = PolicyEngine()

        # 2 allow, 1 deny -> majority allow
        for i in range(2):
            rule = PolicyRule(
                rule_id=f"allow_rule_{i}",
                conditions=[],
                logical_operator=LogicalOperator.AND,
                effect=PolicyEffect.ALLOW
            )
            policy = Policy(
                policy_id=f"allow_policy_{i}",
                policy_type=PolicyType.ACCESS_CONTROL,
                rules=[rule]
            )
            engine.register_policy(policy)

        rule_deny = PolicyRule(
            rule_id="deny_rule",
            conditions=[],
            logical_operator=LogicalOperator.AND,
            effect=PolicyEffect.DENY
        )
        policy_deny = Policy(
            policy_id="deny_policy",
            policy_type=PolicyType.ACCESS_CONTROL,
            rules=[rule_deny]
        )
        engine.register_policy(policy_deny)

        engine.create_policy_set("test_set", ["allow_policy_0", "allow_policy_1", "deny_policy"])

        result = engine.evaluate_policy_set("test_set", {}, "majority_allow")
        assert result["effect"] == "allow"

    def test_evaluate_policy_set_unknown_logic(self):
        """Test evaluate_policy_set with unknown combination logic."""
        engine = PolicyEngine()
        rule = PolicyRule(
            rule_id="rule1",
            conditions=[],
            logical_operator=LogicalOperator.AND,
            effect=PolicyEffect.ALLOW
        )
        policy = Policy(
            policy_id="policy1",
            policy_type=PolicyType.ACCESS_CONTROL,
            rules=[rule]
        )
        engine.register_policy(policy)
        engine.create_policy_set("test_set", ["policy1"])

        result = engine.evaluate_policy_set("test_set", {}, "unknown_logic")
        assert result["effect"] == "deny"
        assert "Unknown combination logic" in result.get("error", "")
