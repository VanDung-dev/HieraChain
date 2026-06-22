"""
Policy Evaluation Engine for HieraChain Ledger.

Implements a comprehensive policy evaluation engine for complex organizational
policies and access control decisions.
"""

from __future__ import annotations

import time
import json
import hashlib
from typing import Any

from hierachain.security.policy_types import (
    PolicyType,
    PolicyEffect,
    ComparisonOperator,
    LogicalOperator,
    PolicyCondition,
    PolicyRule,
)

__all__ = [
    "PolicyType",
    "PolicyEffect",
    "ComparisonOperator",
    "LogicalOperator",
    "PolicyCondition",
    "PolicyRule",
    "Policy",
    "PolicyEngine",
    "_hash_context",
]


def _hash_context(context: dict[str, Any]) -> str:
    def _default_serializer(obj):
        if hasattr(obj, "schema") or hasattr(obj, "to_pylist"):
            return str(obj)
        return str(obj)

    context_str = json.dumps(context, sort_keys=True, separators=(',', ':'), default=_default_serializer)
    return hashlib.sha256(context_str.encode()).hexdigest()[:8]


class Policy:
    def __init__(
        self,
        policy_id: str,
        policy_type: PolicyType,
        rules: list[PolicyRule] | None = None,
        default_effect: PolicyEffect = PolicyEffect.DENY,
        description: str = "",
    ):
        self.policy_id = policy_id
        self.policy_type = policy_type
        self.rules = rules or []
        self.default_effect = default_effect
        self.description = description
        self.created_at = time.time()
        self.last_modified = time.time()
        self.version = 1
        self.metadata: dict[str, Any] = {
            "organization": None,
            "scope": "global",
            "tags": [],
            "enabled": True,
        }
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def add_rule(self, rule: PolicyRule) -> None:
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        self.last_modified = time.time()
        self.version += 1

    def remove_rule(self, rule_id: str) -> bool:
        for i, rule in enumerate(self.rules):
            if rule.rule_id == rule_id:
                del self.rules[i]
                self.last_modified = time.time()
                self.version += 1
                return True
        return False

    def _create_evaluation_result(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "effect": self.default_effect.value,
            "applicable_rules": [],
            "decision_path": [],
            "evaluated_at": time.time(),
            "context_hash": _hash_context(context),
        }

    def _check_disabled(self, evaluation_result: dict[str, Any]) -> bool:
        if not self.metadata.get("enabled", True):
            evaluation_result["effect"] = PolicyEffect.DENY.value
            evaluation_result["decision_path"].append("Policy is disabled")
            return True
        return False

    def _process_rule_effect(self, rule: PolicyRule, rule_effect: PolicyEffect, evaluation_result: dict[str, Any]) -> bool:
        evaluation_result["applicable_rules"].append({
            "rule_id": rule.rule_id,
            "effect": rule_effect.value,
            "priority": rule.priority,
            "description": rule.description,
        })
        if rule_effect != self.default_effect:
            effect_value = rule_effect.value if isinstance(rule_effect, PolicyEffect) else str(rule_effect)
            evaluation_result["effect"] = effect_value
            evaluation_result["decision_path"].append(f"Rule {rule.rule_id} applied with effect {effect_value}")
            return True
        evaluation_result["decision_path"].append(f"Rule {rule.rule_id} confirmed default effect")
        return False

    def _evaluate_rules(self, context: dict[str, Any], evaluation_result: dict[str, Any]) -> None:
        for rule in self.rules:
            rule_effect = rule.evaluate(context)
            if rule_effect is not None and self._process_rule_effect(rule, rule_effect, evaluation_result):
                break

    def _finalize_result(self, evaluation_result: dict[str, Any]) -> None:
        if not evaluation_result["applicable_rules"]:
            evaluation_result["decision_path"].append(f"No rules applied, using default effect {self.default_effect.value}")

    def evaluate(self, context: dict[str, Any]) -> dict[str, Any]:
        evaluation_result = self._create_evaluation_result(context)
        if self._check_disabled(evaluation_result):
            return evaluation_result
        self._evaluate_rules(context, evaluation_result)
        self._finalize_result(evaluation_result)
        return evaluation_result

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_type": self.policy_type.value,
            "rules": [rule.to_dict() for rule in self.rules],
            "default_effect": self.default_effect.value,
            "description": self.description,
            "created_at": self.created_at,
            "last_modified": self.last_modified,
            "version": self.version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Policy:
        policy = cls(
            policy_id=data["policy_id"],
            policy_type=PolicyType(data["policy_type"]),
            rules=[PolicyRule.from_dict(rule) for rule in data["rules"]],
            default_effect=PolicyEffect(data["default_effect"]),
            description=data.get("description", ""),
        )
        policy.created_at = data.get("created_at", time.time())
        policy.last_modified = data.get("last_modified", time.time())
        policy.version = data.get("version", 1)
        policy.metadata = data.get("metadata", {})
        return policy


def _summarize_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_id": context.get("entity_id"),
        "role": context.get("role"),
        "action": context.get("action"),
        "resource": context.get("resource"),
        "organization": context.get("organization"),
    }


def _create_not_found_result(policy_id: str) -> dict[str, Any]:
    return {
        "policy_id": policy_id,
        "effect": PolicyEffect.DENY.value,
        "error": f"Policy {policy_id} not found",
        "evaluated_at": time.time(),
    }


class PolicyEngine:
    def __init__(self):
        self.policies: dict[str, Policy] = {}
        self.policy_sets: dict[str, list[str]] = {}
        self.evaluation_cache: dict[str, dict[str, Any]] = {}
        self.audit_log: list[dict[str, Any]] = []
        self.cache_enabled = True
        self.cache_ttl = 300
        self.max_cache_entries = 1000
        self.audit_enabled = True
        self.statistics = {
            "total_evaluations": 0,
            "cached_evaluations": 0,
            "policy_count": 0,
            "allow_decisions": 0,
            "deny_decisions": 0,
        }

    def register_policy(self, policy: Policy) -> None:
        self.policies[policy.policy_id] = policy
        self.statistics["policy_count"] = len(self.policies)
        if self.cache_enabled:
            self.evaluation_cache.clear()
        self._log_audit_event("policy_registered", {"policy_id": policy.policy_id, "policy_type": policy.policy_type.value})

    def unregister_policy(self, policy_id: str) -> bool:
        if policy_id in self.policies:
            policy = self.policies.pop(policy_id)
            self.statistics["policy_count"] = len(self.policies)
            if self.cache_enabled:
                self.evaluation_cache.clear()
            self._log_audit_event("policy_unregistered", {"policy_id": policy_id, "policy_type": policy.policy_type.value})
            return True
        return False

    def create_policy_set(self, set_name: str, policy_ids: list[str]) -> bool:
        for policy_id in policy_ids:
            if policy_id not in self.policies:
                return False
        self.policy_sets[set_name] = policy_ids.copy()
        self._log_audit_event("policy_set_created", {"set_name": set_name, "policy_count": len(policy_ids)})
        return True

    def _get_cached_result(self, cache_key: str) -> dict[str, Any] | None:
        if not self.cache_enabled or cache_key not in self.evaluation_cache:
            return None
        cached_result = self.evaluation_cache[cache_key]
        if time.time() - cached_result["cached_at"] < self.cache_ttl:
            self.statistics["cached_evaluations"] += 1
            return cached_result["result"]
        return None

    def _update_statistics(self, effect: str) -> None:
        self.statistics["total_evaluations"] += 1
        if effect == PolicyEffect.ALLOW.value:
            self.statistics["allow_decisions"] += 1
        else:
            self.statistics["deny_decisions"] += 1

    def evaluate_policy(self, policy_id: str, context: dict[str, Any]) -> dict[str, Any]:
        cache_key = f"{policy_id}:{_hash_context(context)}"
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached
        policy = self.policies.get(policy_id)
        result = policy.evaluate(context) if policy else _create_not_found_result(policy_id)
        self._update_statistics(result["effect"])
        if self.cache_enabled:
            self._cache_result(cache_key, result)
        if self.audit_enabled:
            self._log_audit_event("policy_evaluated", {"policy_id": policy_id, "effect": result["effect"], "context_summary": _summarize_context(context)})
        return result

    def evaluate_policy_set(self, set_name: str, context: dict[str, Any], combination_logic: str = "all_allow") -> dict[str, Any]:
        if set_name not in self.policy_sets:
            return {"set_name": set_name, "effect": PolicyEffect.DENY.value, "error": f"Policy set {set_name} not found", "evaluated_at": time.time()}
        policy_ids = self.policy_sets[set_name]
        policy_results = [self.evaluate_policy(pid, context) for pid in policy_ids]
        combined = {"set_name": set_name, "combination_logic": combination_logic, "policy_results": policy_results, "evaluated_at": time.time()}
        if combination_logic == "all_allow":
            combined["effect"] = self._combine_all_allow(policy_results)
        elif combination_logic == "any_allow":
            combined["effect"] = self._combine_any_allow(policy_results)
        elif combination_logic == "majority_allow":
            combined["effect"] = self._combine_majority_allow(policy_results)
        else:
            combined["effect"] = PolicyEffect.DENY.value
            combined["error"] = f"Unknown combination logic: {combination_logic}"
        return combined

    def get_applicable_policies(self, context: dict[str, Any], policy_type: PolicyType | None = None) -> list[str]:
        _ = context
        applicable: list[str] = []
        for policy_id, policy in self.policies.items():
            if policy_type and policy.policy_type != policy_type:
                continue
            if policy.metadata.get("enabled", True):
                applicable.append(policy_id)
        return applicable

    def get_policy_info(self, policy_id: str) -> dict[str, Any] | None:
        policy = self.policies.get(policy_id)
        return policy.to_dict() if policy else None

    def get_engine_statistics(self) -> dict[str, Any]:
        cache_stats = {
            "enabled": self.cache_enabled,
            "entries": len(self.evaluation_cache),
            "hit_rate": (self.statistics["cached_evaluations"] / max(self.statistics["total_evaluations"], 1)) * 100,
        }
        return {"statistics": self.statistics, "cache_stats": cache_stats, "policy_count": len(self.policies), "policy_set_count": len(self.policy_sets), "audit_log_size": len(self.audit_log)}

    def clear_cache(self) -> None:
        self.evaluation_cache.clear()

    def get_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.audit_log[-limit:] if limit > 0 else self.audit_log

    def _cache_result(self, cache_key: str, result: dict[str, Any]) -> None:
        if len(self.evaluation_cache) >= self.max_cache_entries:
            oldest_key = min(self.evaluation_cache.keys(), key=lambda k: self.evaluation_cache[k]["cached_at"])
            del self.evaluation_cache[oldest_key]
        self.evaluation_cache[cache_key] = {"result": result, "cached_at": time.time()}

    def _log_audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        if not self.audit_enabled:
            return
        self.audit_log.append({"timestamp": time.time(), "event_type": event_type, "details": details})
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-5000:]

    @staticmethod
    def _combine_all_allow(policy_results: list[dict[str, Any]]) -> str:
        return PolicyEffect.ALLOW.value if all(r["effect"] == PolicyEffect.ALLOW.value for r in policy_results) else PolicyEffect.DENY.value

    @staticmethod
    def _combine_any_allow(policy_results: list[dict[str, Any]]) -> str:
        return PolicyEffect.ALLOW.value if any(r["effect"] == PolicyEffect.ALLOW.value for r in policy_results) else PolicyEffect.DENY.value

    @staticmethod
    def _combine_majority_allow(policy_results: list[dict[str, Any]]) -> str:
        allow_count = sum(1 for r in policy_results if r["effect"] == PolicyEffect.ALLOW.value)
        return PolicyEffect.ALLOW.value if allow_count > len(policy_results) / 2 else PolicyEffect.DENY.value

    def __str__(self) -> str:
        return f"PolicyEngine(policies={len(self.policies)}, sets={len(self.policy_sets)})"

    def __repr__(self) -> str:
        return f"PolicyEngine(policies={len(self.policies)}, policy_sets={len(self.policy_sets)}, evaluations={self.statistics['total_evaluations']})"
