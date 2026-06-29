"""
Cross-Chain Validator for HieraChain Ledger.

This module provides validation capabilities across the HieraChain
system to ensure data consistency and integrity between Main Chain
and Sub-Chains while maintaining Ledger guidelines.
"""

import time
from typing import Any, Callable, cast

from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.domains.utils.entity_tracer import EntityTracer
from hierachain.domains.utils.compliance_checker import ComplianceChecker
from hierachain.security.secure_logging import get_security_logger

logger = get_security_logger()


def _check_operation_consistency(
    event_type: str,
    details: dict[str, Any],
    current_operation: str | None,
    chain_name: str,
    event: dict[str, Any],
    inconsistencies: list[dict[str, Any]]
) -> str | None:
    """Check and update operation status for consistency."""
    if event_type == "operation_start":
        if current_operation is not None:
            inconsistencies.append({
                "type": "concurrent_operations",
                "chain_name": chain_name,
                "event": event,
                "issue": f"Operation started while {current_operation} is still active"
            })
        return details.get("operation_type")

    if event_type == "operation_complete":
        if current_operation is None:
            inconsistencies.append({
                "type": "operation_complete_without_start",
                "chain_name": chain_name,
                "event": event,
                "issue": "Operation completed without corresponding start event"
            })
        return None

    return current_operation


def _check_status_consistency(
    event_type: str,
    details: dict[str, Any],
    entity_status: str | None,
    chain_name: str,
    event: dict[str, Any],
    inconsistencies: list[dict[str, Any]]
) -> str | None:
    """Check and update entity status for consistency."""
    if event_type != "status_update":
        return entity_status

    old_status = details.get("old_status")
    new_status = details.get("new_status")

    if (
        old_status is not None and
        entity_status is not None and
        entity_status != old_status
    ):
        inconsistencies.append({
            "type": "status_inconsistency",
            "chain_name": chain_name,
            "event": event,
            "issue": f"Expected old_status to be {entity_status}, but got {old_status}"
        })

    return new_status


def _check_logical_consistency(
    entity_trace: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Check for logical inconsistencies across chains."""
    inconsistencies: list[dict[str, Any]] = []

    all_events = []
    for chain_name, events in entity_trace.items():
        for event in events:
            event_with_chain = event.copy()
            event_with_chain["_chain_name"] = chain_name
            all_events.append(event_with_chain)

    all_events.sort(key=lambda x: x.get("timestamp", 0))

    entity_status = None
    current_operation = None

    for event in all_events:
        event_type = str(event.get("event", ""))
        details = event.get("details", {})
        chain_name = str(event.get("_chain_name", "Unknown"))

        current_operation = _check_operation_consistency(
            event_type,
            details,
            current_operation,
            chain_name,
            event,
            inconsistencies,
        )
        entity_status = _check_status_consistency(
            event_type,
            details,
            entity_status,
            chain_name,
            event,
            inconsistencies,
        )

    return inconsistencies


def _add_chain_integrity_recommendations(
    validation_results: dict[str, Any],
    recommendations: list[str]
) -> None:
    """Add recommendations related to chain integrity."""
    if not validation_results["main_chain_valid"]:
        recommendations.append(
            "Main Chain integrity is compromised - immediate investigation required"
        )

    invalid_sub_chains = [
        name for name,
        valid in validation_results["sub_chains_valid"].items()
        if not valid
    ]
    if invalid_sub_chains:
        names = ", ".join(invalid_sub_chains)
        recommendations.append(f"Sub-Chains with integrity issues: {names}")


def _add_proof_consistency_recommendations(
    validation_results: dict[str, Any],
    recommendations: list[str]
) -> None:
    """Add recommendations for proof consistency."""
    proof = validation_results["proof_consistency"]
    if not proof["overall_consistent"]:
        if proof["missing_blocks"] > 0:
            recommendations.append(
                "Missing blocks detected - check Sub-Chain synchronization"
            )
        if proof["inconsistent_proofs"] > 0:
            recommendations.append(
                "Proof inconsistencies detected - verify proof submission process"
            )


def _add_ledger_compliance_recommendations(
    validation_results: dict[str, Any],
    recommendations: list[str]
) -> None:
    """Add recommendations related to Ledger compliance."""
    ledger_compliance = validation_results["Ledger_compliance"]
    if not ledger_compliance["overall_compliant"]:
        violation_types = set(v["type"] for v in ledger_compliance["violations"])
        if "cryptocurrency_terms" in violation_types:
            recommendations.append(
                "Remove cryptocurrency terminology from events and data"
            )
        if "entity_id_misuse" in violation_types:
            recommendations.append(
                "Ensure entity_id is used as metadata field, not as identifier"
            )
        if "invalid_block_structure" in violation_types:
            recommendations.append(
                "Fix block structures to contain multiple events, not single events"
            )


def _generate_system_recommendations(validation_results: dict[str, Any]) -> list[str]:
    """Generate recommendations from validation results."""
    recommendations: list[str] = []
    _add_chain_integrity_recommendations(validation_results, recommendations)
    _add_proof_consistency_recommendations(validation_results, recommendations)
    _add_ledger_compliance_recommendations(validation_results, recommendations)
    return recommendations


def _process_string_value(v: str) -> str | None:
    """Process string value with length check."""
    if len(v) >= 1000:
        logger.debug(
            "Skipping validation for long string (length=%d). "
            "Consider validating with pattern matching for hashes.",
            len(v)
        )
        return None
    return v.lower()


def _process_bytes_value(v: bytes) -> str | None:
    """Process bytes value with length check."""
    if len(v) >= 1000:
        logger.debug(
            "Skipping validation for long bytes (length=%d). "
            "Consider validating with pattern matching for hashes.",
            len(v)
        )
        return None
    return v.decode('utf-8', errors='ignore').lower()


def _build_default_validation_rules() -> dict[str, Callable]:
    """Return the set of default validation rules."""

    def proof_hash_consistency(
        main_chain_event: dict[str, Any], sub_chain_block: dict[str, Any]
    ) -> bool:
        """Proof hash must match Sub-Chain block hash."""
        proof_hash = main_chain_event.get("details", {}).get("proof_hash")
        block_hash = sub_chain_block.get("hash")
        return proof_hash == block_hash

    def proof_timestamp_consistency(
        main_chain_event: dict[str, Any], sub_chain_block: dict[str, Any]
    ) -> bool:
        """Proof timestamp must be >= block timestamp AND within 24 hours of block."""
        proof_ts = main_chain_event.get("timestamp", 0)
        block_ts = sub_chain_block.get("timestamp", 0)

        return proof_ts >= block_ts and (proof_ts - block_ts) < 86400

    def entity_id_metadata_usage(event: dict[str, Any],) -> bool:
        """entity_id must be used as metadata."""
        return "entity_id" in event and isinstance(event["entity_id"], str)

    def no_cryptocurrency_terms(data: dict[str, Any],) -> bool:
        """Data must not contain crypto terminology."""
        from hierachain.core.utils import validate_no_cryptocurrency_terms
        return validate_no_cryptocurrency_terms(data)

    return {
        "proof_hash_consistency": proof_hash_consistency,
        "proof_timestamp_consistency": proof_timestamp_consistency,
        "entity_id_metadata_usage": entity_id_metadata_usage,
        "no_cryptocurrency_terms": no_cryptocurrency_terms,
    }


def _record_missing(
    results: dict[str, Any],
    issue_type: str,
    sub_chain_name: str,
    proof_hash: str,
    proof_event: dict[str, Any],
) -> None:
    """Record a missing block / sub-chain."""
    results["missing_blocks"] += 1
    results["inconsistencies"].append({
        "type": issue_type,
        "sub_chain_name": sub_chain_name,
        "proof_hash": proof_hash,
        "timestamp": proof_event.get("timestamp"),
    })


class ProofValidator:
    """Validates proof consistency between Main Chain and Sub-Chains."""

    def __init__(
        self,
        hierarchy_manager: HierarchyManager,
        validation_rules: dict[str, Callable],
    ):
        self._hm = hierarchy_manager
        self._rules = validation_rules

    def validate(self) -> dict[str, Any]:
        """
        Validate consistency between Main Chain proofs
        and Sub-Chain blocks.
        """
        results: dict[str, Any] = {
            "timestamp": time.time(),
            "total_proofs_checked": 0,
            "consistent_proofs": 0,
            "inconsistent_proofs": 0,
            "missing_blocks": 0,
            "inconsistencies": [],
            "overall_consistent": True,
        }

        proof_events = self._hm.main_chain.get_events_by_type("proof_submission")
        results["total_proofs_checked"] = len(proof_events)

        for proof_event in proof_events:
            self._validate_single_proof(proof_event, results)

        results["overall_consistent"] = (
            results["inconsistent_proofs"] == 0 and results["missing_blocks"] == 0
        )
        return results

    # -- internals -------------------------------------------------

    def _validate_single_proof(
        self, proof_event: dict[str, Any], results: dict[str, Any],
    ) -> None:
        """Validate one proof event."""
        details = proof_event.get("details", {})
        sub_chain_name = details.get("sub_chain_name")
        proof_hash = details.get("proof_hash")

        if not sub_chain_name or not proof_hash:
            return

        sub_chain = self._hm.get_sub_chain(sub_chain_name)
        if not sub_chain:
            _record_missing(
                results,
                "missing_sub_chain",
                sub_chain_name,
                proof_hash,
                proof_event,
            )
            return

        block = self._find_block(sub_chain_name, proof_hash)
        if not block:
            _record_missing(
                results,
                "missing_block",
                sub_chain_name,
                proof_hash,
                proof_event,
            )
            return

        self._check_proof_rules(
            proof_event,
            cast(Any, block).to_dict(),
            sub_chain_name,
            proof_hash,
            results,
        )

    def _find_block(self, sub_chain_name: str, proof_hash: str) -> Any | None:
        """Find block in a Sub-Chain by hash."""
        sub_chain = self._hm.get_sub_chain(sub_chain_name)
        if not sub_chain:
            return None
        for block in sub_chain.chain:
            if block.hash == proof_hash:
                return block
        return None

    def _check_proof_rules(
        self,
        proof_event: dict[str, Any],
        block_dict: dict[str, Any],
        sub_chain_name: str,
        proof_hash: str,
        results: dict[str, Any],
    ) -> None:
        """Apply proof-hash and timestamp rules."""
        hash_rule = self._rules["proof_hash_consistency"]
        if not hash_rule(proof_event, block_dict):
            results["inconsistent_proofs"] += 1
            results["inconsistencies"].append({
                "type": "hash_mismatch",
                "sub_chain_name": sub_chain_name,
                "expected_hash": proof_hash,
                "actual_hash": block_dict.get("hash"),
                "timestamp": proof_event.get("timestamp"),
            })
            return

        ts_rule = self._rules["proof_timestamp_consistency"]
        if not ts_rule(proof_event, block_dict):
            results["inconsistent_proofs"] += 1
            results["inconsistencies"].append({
                "type": "timestamp_inconsistency",
                "sub_chain_name": sub_chain_name,
                "proof_timestamp": (proof_event.get("timestamp")),
                "block_timestamp": (block_dict.get("timestamp")),
                "proof_hash": proof_hash,
            })
            return

        results["consistent_proofs"] += 1


class CrossChainValidator:
    """
    Cross-chain validation utility for HieraChain Ledger.

    Delegates specialised work to:
        - ProofValidator - proof consistency
        - ComplianceChecker - Ledger guideline compliance

    Public API remains unchanged.
    """

    def __init__(self, hierarchy_manager: HierarchyManager):
        """
        Initialize the Cross-Chain Validator.

        Args:
            hierarchy_manager: HierarchyManager instance
        """
        self.hierarchy_manager = hierarchy_manager
        self.validation_rules: dict[str, Callable] = {}

        # Set up default validation rules
        self.validation_rules.update(_build_default_validation_rules())

        # Delegates
        self._proof_validator = ProofValidator(hierarchy_manager, self.validation_rules)
        self._compliance_checker = ComplianceChecker(
            hierarchy_manager, self.validation_rules
        )

    # -- proof validation (delegated) ------------------------------

    def validate_proof_consistency(self) -> dict[str, Any]:
        """
        Validate consistency between Main Chain proofs
        and Sub-Chain blocks.
        """
        return self._proof_validator.validate()

    # -- entity consistency ----------------------------------------

    def _validate_entity_event(
        self,
        event: dict[str, Any],
        chain_name: str,
        validation_results: dict[str, Any],
    ) -> bool:
        """Validate a single entity event."""
        entity_rule = self.validation_rules["entity_id_metadata_usage"]
        if not entity_rule(event):
            validation_results["inconsistencies"].append({
                "type": "entity_id_misuse",
                "chain_name": chain_name,
                "event": event,
                "issue": "entity_id not used as metadata field"
            })
            return False

        crypto_rule = self.validation_rules["no_cryptocurrency_terms"]
        if not crypto_rule(event):
            validation_results["inconsistencies"].append({
                "type": "cryptocurrency_terms",
                "chain_name": chain_name,
                "event": event,
                "issue": "contains forbidden cryptocurrency terminology",
            })
            return False

        from hierachain.core.utils import validate_event_structure
        if not validate_event_structure(event):
            validation_results["inconsistencies"].append({
                "type": "invalid_event_structure",
                "chain_name": chain_name,
                "event": event,
                "issue": "event structure doesn't follow Ledger guidelines",
            })
            return False

        return True

    def _process_entity_trace(
        self,
        entity_trace: dict[str, list[dict[str, Any]]],
        validation_results: dict[str, Any],
    ) -> None:
        """Process entity trace: validate events and
        check logical consistency."""
        total = 0
        consistent = 0
        inconsistent = 0

        for chain_name, events in entity_trace.items():
            total += len(events)
            for event in events:
                if self._validate_entity_event(event, chain_name, validation_results):
                    consistent += 1
                else:
                    inconsistent += 1

        logical = _check_logical_consistency(entity_trace)
        validation_results["inconsistencies"].extend(logical)
        inconsistent += len(logical)

        validation_results["total_events"] = total
        validation_results["consistent_events"] = consistent
        validation_results["inconsistent_events"] = inconsistent

    def validate_entity_consistency(self, entity_id: str) -> dict[str, Any]:
        """
        Validate consistency of an entity across chains.

        Args:
            entity_id: Entity identifier to validate

        Returns:
            Entity consistency validation results
        """
        results: dict[str, Any] = {
            "entity_id": entity_id,
            "timestamp": time.time(),
            "chains_checked": 0,
            "total_events": 0,
            "consistent_events": 0,
            "inconsistent_events": 0,
            "inconsistencies": [],
            "entity_found": False,
            "overall_consistent": True,
        }

        tracer = EntityTracer(self.hierarchy_manager)
        entity_trace = tracer.trace_entity_across_chains(entity_id)

        if not entity_trace:
            return results

        results["entity_found"] = True
        results["chains_checked"] = len(entity_trace)
        self._process_entity_trace(entity_trace, results)

        results["overall_consistent"] = (results["inconsistent_events"] == 0)
        return results

    # -- system integrity (orchestrator) ---------------------------

    def validate_system_integrity(self) -> dict[str, Any]:
        """
        Validate the integrity of the entire system.

        Returns:
            Comprehensive system integrity results
        """
        results: dict[str, Any] = dict(
            timestamp=time.time(),
            main_chain_valid=False,
            sub_chains_valid={},
            proof_consistency={},
            Ledger_compliance={},
            overall_integrity=False,
            recommendations=[],
        )

        results["main_chain_valid"] = (
            self.hierarchy_manager.main_chain.is_chain_valid()
            )

        for name, sub in (self.hierarchy_manager.sub_chains.items()):
            results["sub_chains_valid"][name] = (sub.is_chain_valid())

        results["proof_consistency"] = (self.validate_proof_consistency())
        results["Ledger_compliance"] = (self._compliance_checker.validate())
        results["recommendations"] = (_generate_system_recommendations(results))

        results["overall_integrity"] = (
            results["main_chain_valid"]
            and all(results["sub_chains_valid"].values())
            and results["proof_consistency"]["overall_consistent"]
            and results["Ledger_compliance"]["overall_compliant"]
        )

        return results

    # -- string representations ------------------------------------

    def __str__(self) -> str:
        """String representation."""
        main = self.hierarchy_manager.main_chain.name
        return f"CrossChainValidator(hierarchy_manager={main})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        main = self.hierarchy_manager.main_chain.name
        subs = len(self.hierarchy_manager.sub_chains)
        rules = len(self.validation_rules)
        return (
            f"CrossChainValidator("
            f"main_chain={main}, "
            f"sub_chains={subs}, "
            f"validation_rules={rules})"
        )
