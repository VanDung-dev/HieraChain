"""
Policy types for HieraChain Ledger.

Defines enums, dataclasses, and helper functions for policy definitions.
"""

import re
from typing import Any
from dataclasses import dataclass
from enum import Enum


class PolicyType(Enum):
    ACCESS_CONTROL = "access_control"
    ENDORSEMENT = "endorsement"
    LIFECYCLE = "lifecycle"
    DATA_ACCESS = "data_access"
    CHANNEL_MANAGEMENT = "channel_management"
    CONTRACT_EXECUTION = "contract_execution"


class PolicyEffect(Enum):
    ALLOW = "allow"
    DENY = "deny"


class ComparisonOperator(Enum):
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
    AND = "and"
    OR = "or"
    NOT = "not"


def _get_dict_value(current: dict, part: str) -> Any:
    return current[part] if part in current else None


def _get_sequence_value(current: list | tuple, part: str) -> Any:
    if not part.isdigit():
        return None
    try:
        return current[int(part)]
    except (IndexError, ValueError):
        return None


def _get_arrow_value(current: Any, part: str) -> Any:
    try:
        return current[part]
    except (KeyError, IndexError, TypeError):
        return None


def _convert_arrow_scalar(value: Any) -> Any:
    if hasattr(value, "as_py"):
        return value.as_py()
    return value


def _resolve_value(current: Any, part: str) -> Any:
    if isinstance(current, dict):
        return _get_dict_value(current, part)
    if isinstance(current, (list, tuple)):
        return _get_sequence_value(current, part)
    if hasattr(current, "__getitem__"):
        return _get_arrow_value(current, part)
    return None


def _get_attribute_value(context: dict[str, Any], attribute_path: str) -> Any:
    current = context
    for part in attribute_path.split('.'):
        if current is None:
            return None
        current = _resolve_value(current, part)
    return _convert_arrow_scalar(current)


@dataclass
class PolicyCondition:
    attribute: str
    operator: ComparisonOperator
    value: str | int | float | list[Any]

    def evaluate(self, context: dict[str, Any]) -> bool:
        attribute_value = _get_attribute_value(context, self.attribute)
        if attribute_value is None:
            return False
        try:
            match self.operator:
                case ComparisonOperator.EQUALS:
                    return self._evaluate_equals(attribute_value)
                case ComparisonOperator.NOT_EQUALS:
                    return self._evaluate_not_equals(attribute_value)
                case ComparisonOperator.GREATER_THAN:
                    return self._evaluate_greater_than(attribute_value)
                case ComparisonOperator.LESS_THAN:
                    return self._evaluate_less_than(attribute_value)
                case ComparisonOperator.GREATER_OR_EQUAL:
                    return self._evaluate_greater_or_equal(attribute_value)
                case ComparisonOperator.LESS_OR_EQUAL:
                    return self._evaluate_less_or_equal(attribute_value)
                case ComparisonOperator.CONTAINS:
                    return self._evaluate_contains(attribute_value)
                case ComparisonOperator.NOT_CONTAINS:
                    return self._evaluate_not_contains(attribute_value)
                case ComparisonOperator.IN:
                    return self._evaluate_in(attribute_value)
                case ComparisonOperator.NOT_IN:
                    return self._evaluate_not_in(attribute_value)
                case ComparisonOperator.MATCHES:
                    return self._evaluate_matches(attribute_value)
                case ComparisonOperator.NOT_MATCHES:
                    return self._evaluate_not_matches(attribute_value)
        except (TypeError, ValueError, AttributeError):
            return False

    def _evaluate_equals(self, attribute_value: Any) -> bool:
        return attribute_value == self.value

    def _evaluate_not_equals(self, attribute_value: Any) -> bool:
        return attribute_value != self.value

    def _evaluate_greater_than(self, attribute_value: Any) -> bool:
        return attribute_value > self.value

    def _evaluate_less_than(self, attribute_value: Any) -> bool:
        return attribute_value < self.value

    def _evaluate_greater_or_equal(self, attribute_value: Any) -> bool:
        return attribute_value >= self.value

    def _evaluate_less_or_equal(self, attribute_value: Any) -> bool:
        return attribute_value <= self.value

    def _evaluate_contains(self, attribute_value: Any) -> bool:
        if isinstance(attribute_value, (str, list, dict, set)):
            return self.value in attribute_value
        return False

    def _evaluate_not_contains(self, attribute_value: Any) -> bool:
        if isinstance(attribute_value, (str, list, dict, set)):
            return self.value not in attribute_value
        return True

    def _evaluate_in(self, attribute_value: Any) -> bool:
        if isinstance(self.value, (str, list)):
            return attribute_value in self.value
        return False

    def _evaluate_not_in(self, attribute_value: Any) -> bool:
        if isinstance(self.value, (str, list)):
            return attribute_value not in self.value
        return True

    def _evaluate_matches(self, attribute_value: Any) -> bool:
        pattern = str(self.value)
        pattern = self._add_anchors(pattern)
        return bool(re.match(pattern, str(attribute_value)))

    def _evaluate_not_matches(self, attribute_value: Any) -> bool:
        pattern = str(self.value)
        pattern = self._add_anchors(pattern)
        return not bool(re.match(pattern, str(attribute_value)))

    @staticmethod
    def _add_anchors(pattern: str) -> str:
        if not pattern.startswith('^'):
            pattern = '^' + pattern
        if not pattern.endswith('$'):
            pattern = pattern + '$'
        return pattern

    def to_dict(self) -> dict[str, Any]:
        return {
            "attribute": self.attribute,
            "operator": self.operator.value,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'PolicyCondition':
        return cls(
            attribute=data["attribute"],
            operator=ComparisonOperator(data["operator"]),
            value=data["value"],
        )


@dataclass
class PolicyRule:
    rule_id: str
    conditions: list[PolicyCondition]
    logical_operator: LogicalOperator
    effect: PolicyEffect
    priority: int = 0
    description: str = ""

    def evaluate(self, context: dict[str, Any]) -> PolicyEffect | None:
        if not self.conditions:
            return self.effect
        condition_results = [condition.evaluate(context) for condition in self.conditions]
        if self.logical_operator == LogicalOperator.AND:
            rule_applies = all(condition_results)
        elif self.logical_operator == LogicalOperator.OR:
            rule_applies = any(condition_results)
        elif self.logical_operator == LogicalOperator.NOT:
            rule_applies = not condition_results[0] if len(condition_results) == 1 else False
        else:
            rule_applies = False
        return self.effect if rule_applies else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "conditions": [condition.to_dict() for condition in self.conditions],
            "logical_operator": self.logical_operator.value,
            "effect": self.effect.value,
            "priority": self.priority,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'PolicyRule':
        return cls(
            rule_id=data["rule_id"],
            conditions=[PolicyCondition.from_dict(cond) for cond in data["conditions"]],
            logical_operator=LogicalOperator(data["logical_operator"]),
            effect=PolicyEffect(data["effect"]),
            priority=data.get("priority", 0),
            description=data.get("description", ""),
        )
