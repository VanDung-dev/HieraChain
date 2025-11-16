"""
Policy Evaluation Engine for Hierarchical Blockchain Framework.

This module implements a comprehensive policy evaluation engine that works with the 
MSP system for complex organizational policies and access control decisions. It 
provides flexible policy definition, evaluation, and enforcement capabilities for 
enterprise blockchain applications.
"""

import time
import json
import re
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum


class PolicyType(Enum):
    """Policy type enumeration"""
    ACCESS_CONTROL = "access_control"
    ENDORSEMENT = "endorsement"
    LIFECYCLE = "lifecycle"
    DATA_ACCESS = "data_access"
    CHANNEL_MANAGEMENT = "channel_management"
    CONTRACT_EXECUTION = "contract_execution"


class PolicyEffect(Enum):
    """Policy effect enumeration"""
    ALLOW = "allow"
    DENY = "deny"


class ComparisonOperator(Enum):
    """Comparison operators for policy conditions"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_OR_EQUAL = "less_or_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"
    MATCHES = "matches"
    NOT_MATCHES = "not_matches"


class LogicalOperator(Enum):
    """Logical operators for policy conditions"""
    AND = "and"
    OR = "or"
    NOT = "not"


@dataclass
class PolicyCondition:
    """Individual policy condition"""
    attribute: str
    operator: ComparisonOperator
    value: Union[str, int, float, List[Any]]
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate condition against context.
        
        Args:
            context: Evaluation context containing attributes
            
        Returns:
            True if condition is satisfied
        """
        attribute_value = self._get_attribute_value(context, self.attribute)
        
        if attribute_value is None:
            return False
        
        try:
            if self.operator == ComparisonOperator.EQUALS:
                return attribute_value == self.value
            elif self.operator == ComparisonOperator.NOT_EQUALS:
                return attribute_value != self.value
            elif self.operator == ComparisonOperator.GREATER_THAN:
                return attribute_value > self.value
            elif self.operator == ComparisonOperator.LESS_THAN:
                return attribute_value < self.value
            elif self.operator == ComparisonOperator.GREATER_OR_EQUAL:
                return attribute_value >= self.value
            elif self.operator == ComparisonOperator.LESS_OR_EQUAL:
                return attribute_value <= self.value
            elif self.operator == ComparisonOperator.CONTAINS:
                return self.value in attribute_value
            elif self.operator == ComparisonOperator.NOT_CONTAINS:
                return self.value not in attribute_value
            elif self.operator == ComparisonOperator.IN:
                return attribute_value in self.value
            elif self.operator == ComparisonOperator.NOT_IN:
                return attribute_value not in self.value
            elif self.operator == ComparisonOperator.MATCHES:
                return bool(re.match(str(self.value), str(attribute_value)))
            elif self.operator == ComparisonOperator.NOT_MATCHES:
                return not bool(re.match(str(self.value), str(attribute_value)))
            else:
                return False
                
        except (TypeError, ValueError, AttributeError):
            return False
    
    @staticmethod
    def _get_attribute_value(context: Dict[str, Any], attribute_path: str) -> Any:
        """Get attribute value from context using dot notation"""
        current = context
        
        for part in attribute_path.split('.'):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
                
        return current
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "attribute": self.attribute,
            "operator": self.operator.value,
            "value": self.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PolicyCondition':
        """Create from dictionary"""
        return cls(
            attribute=data["attribute"],
            operator=ComparisonOperator(data["operator"]),
            value=data["value"]
        )


@dataclass
class PolicyRule:
    """Policy rule with conditions and effect"""
    rule_id: str
    conditions: List[PolicyCondition]
    logical_operator: LogicalOperator
    effect: PolicyEffect
    priority: int = 0
    description: str = ""
    
    def evaluate(self, context: Dict[str, Any]) -> Optional[PolicyEffect]:
        """
        Evaluate rule against context.
        
        Args:
            context: Evaluation context
            
        Returns:
            Policy effect if rule applies, None otherwise
        """
        if not self.conditions:
            return self.effect
        
        # Evaluate all conditions
        condition_results = [condition.evaluate(context) for condition in self.conditions]
        
        # Apply logical operator
        if self.logical_operator == LogicalOperator.AND:
            rule_applies = all(condition_results)
        elif self.logical_operator == LogicalOperator.OR:
            rule_applies = any(condition_results)
        elif self.logical_operator == LogicalOperator.NOT:
            # For NOT, we expect exactly one condition
            rule_applies = not condition_results[0] if len(condition_results) == 1 else False
        else:
            rule_applies = False
        
        return self.effect if rule_applies else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "rule_id": self.rule_id,
            "conditions": [condition.to_dict() for condition in self.conditions],
            "logical_operator": self.logical_operator.value,
            "effect": self.effect.value,
            "priority": self.priority,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PolicyRule':
        """Create from dictionary"""
        return cls(
            rule_id=data["rule_id"],
            conditions=[PolicyCondition.from_dict(cond) for cond in data["conditions"]],
            logical_operator=LogicalOperator(data["logical_operator"]),
            effect=PolicyEffect(data["effect"]),
            priority=data.get("priority", 0),
            description=data.get("description", "")
        )


class Policy:
    """
    Enterprise policy with multiple rules and evaluation logic.
    
    Supports complex policy definitions with multiple rules, priorities,
    and conflict resolution strategies.
    """
    
    def __init__(self, policy_id: str, policy_type: PolicyType, 
                 rules: Optional[List[PolicyRule]] = None,
                 default_effect: PolicyEffect = PolicyEffect.DENY,
                 description: str = ""):
        """
        Initialize policy.
        
        Args:
            policy_id: Unique policy identifier
            policy_type: Type of policy
            rules: List of policy rules
            default_effect: Default effect if no rules apply
            description: Policy description
        """
        self.policy_id = policy_id
        self.policy_type = policy_type
        self.rules = rules or []
        self.default_effect = default_effect
        self.description = description
        self.created_at = time.time()
        self.last_modified = time.time()
        self.version = 1
        
        # Policy metadata
        self.metadata = {
            "organization": None,
            "scope": "global",
            "tags": [],
            "enabled": True
        }
        
        # Sort rules by priority (higher priority first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def add_rule(self, rule: PolicyRule) -> None:
        """Add rule to policy"""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        self.last_modified = time.time()
        self.version += 1
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove rule from policy"""
        for i, rule in enumerate(self.rules):
            if rule.rule_id == rule_id:
                del self.rules[i]
                self.last_modified = time.time()
                self.version += 1
                return True
        return False
    
    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate policy against context.
        
        Args:
            context: Evaluation context
            
        Returns:
            Policy evaluation result
        """
        evaluation_result = {
            "policy_id": self.policy_id,
            "effect": self.default_effect.value,
            "applicable_rules": [],
            "decision_path": [],
            "evaluated_at": time.time(),
            "context_hash": self._hash_context(context)
        }
        
        if not self.metadata.get("enabled", True):
            evaluation_result["effect"] = PolicyEffect.DENY.value
            evaluation_result["decision_path"].append("Policy is disabled")
            return evaluation_result
        
        # Evaluate rules in priority order
        for rule in self.rules:
            rule_effect = rule.evaluate(context)
            
            if rule_effect is not None:
                evaluation_result["applicable_rules"].append({
                    "rule_id": rule.rule_id,
                    "effect": rule_effect.value,
                    "priority": rule.priority,
                    "description": rule.description
                })
                
                # First applicable rule wins (highest priority)
                if rule_effect != self.default_effect:
                    evaluation_result["effect"] = rule_effect.value if isinstance(rule_effect, PolicyEffect) else str(rule_effect)
                    evaluation_result["decision_path"].append(
                        f"Rule {rule.rule_id} applied with effect {rule_effect.value if isinstance(rule_effect, PolicyEffect) else str(rule_effect)}"
                    )
                    break
                else:
                    evaluation_result["decision_path"].append(
                        f"Rule {rule.rule_id} confirmed default effect"
                    )
        
        # If no rules applied, use default effect
        if not evaluation_result["applicable_rules"]:
            evaluation_result["decision_path"].append(
                f"No rules applied, using default effect {self.default_effect.value}"
            )
        
        return evaluation_result
    
    @staticmethod
    def _hash_context(context: Dict[str, Any]) -> str:
        """Generate hash of context for caching"""
        import hashlib
        context_str = json.dumps(context, sort_keys=True, separators=(',', ':'))
        return hashlib.md5(context_str.encode()).hexdigest()[:8]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "policy_id": self.policy_id,
            "policy_type": self.policy_type.value,
            "rules": [rule.to_dict() for rule in self.rules],
            "default_effect": self.default_effect.value,
            "description": self.description,
            "created_at": self.created_at,
            "last_modified": self.last_modified,
            "version": self.version,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Policy':
        """Create from dictionary"""
        policy = cls(
            policy_id=data["policy_id"],
            policy_type=PolicyType(data["policy_type"]),
            rules=[PolicyRule.from_dict(rule) for rule in data["rules"]],
            default_effect=PolicyEffect(data["default_effect"]),
            description=data.get("description", "")
        )
        
        policy.created_at = data.get("created_at", time.time())
        policy.last_modified = data.get("last_modified", time.time())
        policy.version = data.get("version", 1)
        policy.metadata = data.get("metadata", {})
        
        return policy


class PolicyEngine:
    """
    Comprehensive policy evaluation engine for enterprise blockchain applications.
    
    Provides flexible policy definition, evaluation, and enforcement capabilities
    with support for complex organizational hierarchies and access control patterns.
    """
    
    def __init__(self):
        self.policies: Dict[str, Policy] = {}
        self.policy_sets: Dict[str, List[str]] = {}  # Named sets of policies
        self.evaluation_cache: Dict[str, Dict[str, Any]] = {}
        self.audit_log: List[Dict[str, Any]] = []
        
        # Configuration
        self.cache_enabled = True
        self.cache_ttl = 300  # 5 minutes
        self.max_cache_entries = 1000
        self.audit_enabled = True
        
        # Statistics
        self.statistics = {
            "total_evaluations": 0,
            "cached_evaluations": 0,
            "policy_count": 0,
            "allow_decisions": 0,
            "deny_decisions": 0
        }
    
    def register_policy(self, policy: Policy) -> None:
        """Register policy with the engine"""
        self.policies[policy.policy_id] = policy
        self.statistics["policy_count"] = len(self.policies)
        
        # Clear cache when policies change
        if self.cache_enabled:
            self.evaluation_cache.clear()
        
        self._log_audit_event("policy_registered", {
            "policy_id": policy.policy_id,
            "policy_type": policy.policy_type.value
        })
    
    def unregister_policy(self, policy_id: str) -> bool:
        """Unregister policy from engine"""
        if policy_id in self.policies:
            policy = self.policies.pop(policy_id)
            self.statistics["policy_count"] = len(self.policies)
            
            # Clear cache
            if self.cache_enabled:
                self.evaluation_cache.clear()
            
            self._log_audit_event("policy_unregistered", {
                "policy_id": policy_id,
                "policy_type": policy.policy_type.value
            })
            return True
        return False
    
    def create_policy_set(self, set_name: str, policy_ids: List[str]) -> bool:
        """Create named set of policies"""
        # Validate all policies exist
        for policy_id in policy_ids:
            if policy_id not in self.policies:
                return False
        
        self.policy_sets[set_name] = policy_ids.copy()
        
        self._log_audit_event("policy_set_created", {
            "set_name": set_name,
            "policy_count": len(policy_ids)
        })
        
        return True
    
    def evaluate_policy(self, policy_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate single policy against context.
        
        Args:
            policy_id: Policy to evaluate
            context: Evaluation context
            
        Returns:
            Policy evaluation result
        """
        # Check cache first
        cache_key = f"{policy_id}:{self._hash_context(context)}"
        if self.cache_enabled and cache_key in self.evaluation_cache:
            cached_result = self.evaluation_cache[cache_key]
            if time.time() - cached_result["cached_at"] < self.cache_ttl:
                self.statistics["cached_evaluations"] += 1
                return cached_result["result"]
        
        # Get policy
        policy = self.policies.get(policy_id)
        if not policy:
            result = {
                "policy_id": policy_id,
                "effect": PolicyEffect.DENY.value,
                "error": f"Policy {policy_id} not found",
                "evaluated_at": time.time()
            }
        else:
            result = policy.evaluate(context)
        
        # Update statistics
        self.statistics["total_evaluations"] += 1
        if result["effect"] == PolicyEffect.ALLOW.value:
            self.statistics["allow_decisions"] += 1
        else:
            self.statistics["deny_decisions"] += 1
        
        # Cache result
        if self.cache_enabled:
            self._cache_result(cache_key, result)
        
        # Audit log
        if self.audit_enabled:
            self._log_audit_event("policy_evaluated", {
                "policy_id": policy_id,
                "effect": result["effect"],
                "context_summary": self._summarize_context(context)
            })
        
        return result
    
    def evaluate_policy_set(self, set_name: str, context: Dict[str, Any],
                          combination_logic: str = "all_allow") -> Dict[str, Any]:
        """
        Evaluate set of policies against context.
        
        Args:
            set_name: Name of policy set
            context: Evaluation context
            combination_logic: How to combine results ("all_allow", "any_allow", "majority_allow")
            
        Returns:
            Combined evaluation result
        """
        if set_name not in self.policy_sets:
            return {
                "set_name": set_name,
                "effect": PolicyEffect.DENY.value,
                "error": f"Policy set {set_name} not found",
                "evaluated_at": time.time()
            }
        
        policy_ids = self.policy_sets[set_name]
        policy_results = []
        
        # Evaluate each policy
        for policy_id in policy_ids:
            result = self.evaluate_policy(policy_id, context)
            policy_results.append(result)
        
        # Combine results based on logic
        combined_result = {
            "set_name": set_name,
            "combination_logic": combination_logic,
            "policy_results": policy_results,
            "evaluated_at": time.time()
        }
        
        if combination_logic == "all_allow":
            # All policies must allow
            combined_result["effect"] = PolicyEffect.ALLOW.value if all(
                result["effect"] == PolicyEffect.ALLOW.value for result in policy_results
            ) else PolicyEffect.DENY.value
        elif combination_logic == "any_allow":
            # At least one policy must allow
            combined_result["effect"] = PolicyEffect.ALLOW.value if any(
                result["effect"] == PolicyEffect.ALLOW.value for result in policy_results
            ) else PolicyEffect.DENY.value
        elif combination_logic == "majority_allow":
            # Majority of policies must allow
            allow_count = sum(1 for result in policy_results if result["effect"] == PolicyEffect.ALLOW.value)
            combined_result["effect"] = PolicyEffect.ALLOW.value if allow_count > len(policy_results) / 2 else PolicyEffect.DENY.value
        else:
            combined_result["effect"] = PolicyEffect.DENY.value
            combined_result["error"] = f"Unknown combination logic: {combination_logic}"
        
        return combined_result
    
    def get_applicable_policies(self, _context: Dict[str, Any],
                              policy_type: Optional[PolicyType] = None) -> List[str]:
        """Get list of policies that might apply to context"""
        applicable_policies = []
        
        for policy_id, policy in self.policies.items():
            if policy_type and policy.policy_type != policy_type:
                continue
            
            # Quick check if policy might be applicable
            # This is a simplified check - in practice, you might want more sophisticated logic
            if policy.metadata.get("enabled", True):
                applicable_policies.append(policy_id)
        
        return applicable_policies
    
    def get_policy_info(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive policy information"""
        policy = self.policies.get(policy_id)
        if not policy:
            return None
            
        return policy.to_dict()
    
    def get_engine_statistics(self) -> Dict[str, Any]:
        """Get engine statistics"""
        cache_stats = {
            "enabled": self.cache_enabled,
            "entries": len(self.evaluation_cache),
            "hit_rate": (
                self.statistics["cached_evaluations"] / max(self.statistics["total_evaluations"], 1)
            ) * 100
        }
        
        return {
            "statistics": self.statistics,
            "cache_stats": cache_stats,
            "policy_count": len(self.policies),
            "policy_set_count": len(self.policy_sets),
            "audit_log_size": len(self.audit_log)
        }
    
    def clear_cache(self) -> None:
        """Clear evaluation cache"""
        self.evaluation_cache.clear()
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit log entries"""
        return self.audit_log[-limit:] if limit > 0 else self.audit_log
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Cache evaluation result"""
        # Implement LRU eviction if cache is full
        if len(self.evaluation_cache) >= self.max_cache_entries:
            oldest_key = min(self.evaluation_cache.keys(), 
                           key=lambda k: self.evaluation_cache[k]["cached_at"])
            del self.evaluation_cache[oldest_key]
        
        self.evaluation_cache[cache_key] = {
            "result": result,
            "cached_at": time.time()
        }
    
    @staticmethod
    def _hash_context(context: Dict[str, Any]) -> str:
        """Generate hash of context"""
        import hashlib
        context_str = json.dumps(context, sort_keys=True, separators=(',', ':'))
        return hashlib.md5(context_str.encode()).hexdigest()[:8]
    
    @staticmethod
    def _summarize_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """Create summary of context for audit logging"""
        return {
            "entity_id": context.get("entity_id"),
            "role": context.get("role"),
            "action": context.get("action"),
            "resource": context.get("resource"),
            "organization": context.get("organization")
        }
    
    def _log_audit_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Log audit event"""
        if not self.audit_enabled:
            return
        
        audit_entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "details": details
        }
        
        self.audit_log.append(audit_entry)
        
        # Limit audit log size
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-5000:]  # Keep last 5000 entries
    
    def __str__(self) -> str:
        """String representation"""
        return f"PolicyEngine(policies={len(self.policies)}, sets={len(self.policy_sets)})"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return (f"PolicyEngine(policies={len(self.policies)}, "
                f"policy_sets={len(self.policy_sets)}, "
                f"evaluations={self.statistics['total_evaluations']})")