"""
Error Classifier for HieraChain Ledger.

Classifies errors by type, category, and priority using the risk
priority matrix and predefined error patterns.
"""

from __future__ import annotations

import os
import time
import json
import logging
import hashlib
from typing import Any
from datetime import datetime

from hierachain.error_mitigation.classifier_types import (
    PriorityLevel,
    ErrorCategory,
    ImpactLevel,
    LikelihoodLevel,
    ErrorInfo,
)
from hierachain.error_mitigation.risk_matrix import RiskPriorityMatrix

logger = logging.getLogger(__name__)


class ErrorClassifier:
    def __init__(self, config: dict[str, Any], lockdown_callback: Any | None = None) -> None:
        self.config = config
        self.risk_matrix = RiskPriorityMatrix()
        self.error_patterns = _load_error_patterns()
        self.classification_history: list[ErrorInfo] = []
        self.mitigation_strategies = _load_mitigation_strategies()
        self.lockdown_callback = lockdown_callback
        self.lockdown_trigger_categories = {ErrorCategory.SECURITY, ErrorCategory.PERFORMANCE}
        logger.info("Initialized ErrorClassifier")

    def classify_error(self, error_data: dict[str, Any]) -> ErrorInfo:
        error_type = error_data.get("error_type", "unknown")
        error_message = error_data.get("message", "")
        category = self._determine_category(error_type, error_message)
        impact = _assess_impact(error_data, category)
        likelihood = _assess_likelihood(error_data, category)
        priority = self.risk_matrix.calculate_priority(impact, likelihood)
        mitigation_strategy = self._determine_mitigation_strategy(category, priority)
        error_id = _generate_error_id(error_data)
        error_info = ErrorInfo(
            error_id=error_id,
            error_type=error_type,
            category=category,
            priority=priority,
            impact=impact,
            likelihood=likelihood,
            description=error_message,
            mitigation_strategy=mitigation_strategy,
            timestamp=time.time(),
            metadata=_sanitize_metadata(error_data.get("metadata", {})),
        )
        _log_classification(error_info)
        self.classification_history.append(error_info)
        if (
            priority == PriorityLevel.CRITICAL
            and category in self.lockdown_trigger_categories
            and self.lockdown_callback is not None
        ):
            logger.warning("CRITICAL %s error detected. Triggering lockdown: %s", category.value, error_id)
            try:
                self.lockdown_callback(error_info)
            except Exception as e:
                logger.error("Lockdown callback failed: %s", e)
        logger.info("Error classified: %s -> %s (%s)", error_id, category.value, priority.name)
        return error_info

    def get_priority_errors(self, priority: PriorityLevel) -> list[ErrorInfo]:
        return [error for error in self.classification_history if error.priority == priority]

    def get_category_errors(self, category: ErrorCategory) -> list[ErrorInfo]:
        return [error for error in self.classification_history if error.category == category]

    def get_classification_summary(self) -> dict[str, Any]:
        total_errors = len(self.classification_history)
        if total_errors == 0:
            return {"total_errors": 0, "categories": {}, "priorities": {}}
        category_counts = {c.value: len(self.get_category_errors(c)) for c in ErrorCategory}
        priority_counts = {p.name: len(self.get_priority_errors(p)) for p in PriorityLevel}
        return {"total_errors": total_errors, "categories": category_counts, "priorities": priority_counts, "timestamp": time.time()}

    def _determine_category(self, error_type: str, error_message: str) -> ErrorCategory:
        error_text = f"{error_type} {error_message}".lower()
        for pattern, cat_name in self.error_patterns.items():
            if pattern.lower() in error_text:
                return ErrorCategory(cat_name)
        category_keywords = {
            ErrorCategory.CONSENSUS: ["consensus", "bft", "leader", "view"],
            ErrorCategory.SECURITY: ["security", "encryption", "key", "certificate"],
            ErrorCategory.PERFORMANCE: ["performance", "resource", "cpu", "memory"],
            ErrorCategory.STORAGE: ["storage", "backup", "database", "persistence"],
            ErrorCategory.NETWORK: ["network", "timeout", "connection"],
            ErrorCategory.API: ["api", "endpoint", "request", "response"],
        }
        for cat_enum, keywords in category_keywords.items():
            if any(kw in error_text for kw in keywords):
                return cat_enum
        return ErrorCategory.OPERATIONAL

    def _determine_mitigation_strategy(self, category: ErrorCategory, priority: PriorityLevel) -> str:
        strategy_key = f"{category.value}_{priority.name.lower()}"
        return self.mitigation_strategies.get(strategy_key, "monitor_and_log")


def get_priority_score(priority: PriorityLevel) -> int:
    return priority.value


def _sanitize_metadata(data: Any) -> Any:
    if hasattr(data, "to_pylist"):
        return data.to_pylist()
    if isinstance(data, dict):
        return {k: _sanitize_metadata(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize_metadata(v) for v in data]
    return data


def _assess_impact(error_data: dict[str, Any], category: ErrorCategory) -> ImpactLevel:
    error_type = error_data.get("error_type", "").lower()
    handlers = {
        ErrorCategory.CONSENSUS: _assess_consensus_impact,
        ErrorCategory.SECURITY: _assess_security_impact,
        ErrorCategory.PERFORMANCE: _assess_performance_impact,
        ErrorCategory.STORAGE: _assess_storage_impact,
        ErrorCategory.NETWORK: _assess_network_impact,
    }
    handler = handlers.get(category)
    return handler(error_type) if handler else ImpactLevel.MINOR


def _assess_consensus_impact(error_type: str) -> ImpactLevel:
    if "insufficient nodes" in error_type or "bft" in error_type:
        return ImpactLevel.CATASTROPHIC
    if "leader failure" in error_type or "view change" in error_type:
        return ImpactLevel.MAJOR
    return ImpactLevel.MODERATE


def _assess_security_impact(error_type: str) -> ImpactLevel:
    if "encryption" in error_type or "key" in error_type:
        return ImpactLevel.MAJOR
    if "certificate" in error_type or "authentication" in error_type:
        return ImpactLevel.MODERATE
    return ImpactLevel.MINOR


def _assess_performance_impact(error_type: str) -> ImpactLevel:
    if "resource" in error_type and "critical" in error_type:
        return ImpactLevel.MAJOR
    if "threshold" in error_type:
        return ImpactLevel.MODERATE
    return ImpactLevel.MINOR


def _assess_storage_impact(error_type: str) -> ImpactLevel:
    is_critical = ("backup" in error_type and "failed" in error_type) or ("corruption" in error_type)
    return ImpactLevel.MAJOR if is_critical else ImpactLevel.MODERATE


def _assess_network_impact(error_type: str) -> ImpactLevel:
    if "partition" in error_type or "connectivity" in error_type:
        return ImpactLevel.MAJOR
    if "timeout" in error_type:
        return ImpactLevel.MODERATE
    return ImpactLevel.MINOR


def _assess_likelihood(error_data: dict[str, Any], category: ErrorCategory) -> LikelihoodLevel:
    category_likelihoods = {
        ErrorCategory.CONSENSUS: LikelihoodLevel.MEDIUM,
        ErrorCategory.SECURITY: LikelihoodLevel.LOW,
        ErrorCategory.PERFORMANCE: LikelihoodLevel.HIGH,
        ErrorCategory.STORAGE: LikelihoodLevel.MEDIUM,
        ErrorCategory.NETWORK: LikelihoodLevel.HIGH,
        ErrorCategory.API: LikelihoodLevel.LOW,
    }
    return category_likelihoods.get(category, LikelihoodLevel.MEDIUM)


def _generate_error_id(error_data: dict[str, Any]) -> str:
    type_code = error_data.get("error_type", "")
    msg_code = error_data.get("message", "")
    content = f"{type_code}{msg_code}{time.time()}"
    hash_value = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"ERR-{hash_value.upper()}"


def _log_classification(error_info: ErrorInfo) -> None:
    logger.info(
        "CLASSIFIED: ID=%s, Type=%s, Category=%s, Priority=%s, Impact=%s, Likelihood=%s",
        error_info.error_id, error_info.error_type, error_info.category.value,
        error_info.priority.name, error_info.impact.name, error_info.likelihood.name,
    )
    log_entry = {
        "event": "error_classified",
        "error_id": error_info.error_id,
        "category": error_info.category.value,
        "priority": error_info.priority.name,
        "impact": error_info.impact.name,
        "likelihood": error_info.likelihood.name,
        "mitigation_strategy": error_info.mitigation_strategy,
        "timestamp": error_info.timestamp,
    }
    try:
        os.makedirs("log/error_mitigation", exist_ok=True)
        with open("log/error_mitigation/error_classifications.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()}: {json.dumps(log_entry)}\n")
    except (IOError, OSError) as e:
        logger.error("Failed to log error classification: %s", e)


def _load_error_patterns() -> dict[str, str]:
    return {
        "insufficient nodes": "consensus",
        "bft consensus": "consensus",
        "leader failure": "consensus",
        "view change": "consensus",
        "message ordering": "consensus",
        "signature verification": "security",
        "encryption": "security",
        "key rotation": "security",
        "certificate": "security",
        "cpu threshold": "performance",
        "memory threshold": "performance",
        "resource usage": "performance",
        "backup failed": "storage",
        "data corruption": "storage",
        "world state": "storage",
        "network partition": "network",
        "timeout": "network",
        "connectivity": "network",
        "api endpoint": "api",
        "request validation": "api",
        "response error": "api",
        "multi org sync": "operational",
        "entity tracing": "operational",
        "block creation": "operational",
    }


def _load_mitigation_strategies() -> dict[str, str]:
    return {
        "consensus_critical": "immediate_scaling_and_recovery",
        "consensus_high": "auto_scale_nodes",
        "consensus_medium": "monitor_and_view_change",
        "consensus_low": "log_and_monitor",
        "security_critical": "immediate_lockdown_and_investigation",
        "security_high": "rotate_keys_and_audit",
        "security_medium": "schedule_security_review",
        "security_low": "monitor_and_log",
        "performance_critical": "immediate_resource_scaling",
        "performance_high": "auto_scale_resources",
        "performance_medium": "optimize_and_monitor",
        "performance_low": "monitor_and_log",
        "storage_critical": "immediate_backup_recovery",
        "storage_high": "verify_and_restore_backup",
        "storage_medium": "integrity_check_and_repair",
        "storage_low": "monitor_and_log",
        "network_critical": "activate_redundant_paths",
        "network_high": "network_recovery_procedures",
        "network_medium": "adjust_timeouts_and_monitor",
        "network_low": "monitor_and_log",
        "api_critical": "api_circuit_breaker",
        "api_high": "api_validation_enhancement",
        "api_medium": "api_monitoring_increase",
        "api_low": "monitor_and_log",
        "operational_critical": "immediate_manual_intervention",
        "operational_high": "automated_recovery_procedures",
        "operational_medium": "schedule_maintenance",
        "operational_low": "monitor_and_log",
    }


def classify_error_quick(error_type: str, message: str, config: dict[str, Any] | None = None) -> ErrorInfo:
    classifier_config = config or {}
    classifier = ErrorClassifier(classifier_config)
    error_data = {"error_type": error_type, "message": message, "timestamp": time.time()}
    return classifier.classify_error(error_data)


def get_priority_threshold(priority: PriorityLevel) -> dict[str, Any]:
    thresholds = {
        PriorityLevel.CRITICAL: {"response_time_minutes": 5, "escalation_time_minutes": 15, "auto_recovery": True, "alert_level": "immediate"},
        PriorityLevel.HIGH: {"response_time_minutes": 30, "escalation_time_minutes": 120, "auto_recovery": True, "alert_level": "urgent"},
        PriorityLevel.MEDIUM: {"response_time_minutes": 240, "escalation_time_minutes": 1440, "auto_recovery": False, "alert_level": "standard"},
        PriorityLevel.LOW: {"response_time_minutes": 1440, "escalation_time_minutes": 10080, "auto_recovery": False, "alert_level": "low"},
    }
    return thresholds.get(priority, thresholds[PriorityLevel.LOW])
