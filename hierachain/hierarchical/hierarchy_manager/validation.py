"""
Validation and reporting functions for HierarchyManager.
"""

import logging
import time
from typing import Any

from hierachain.security.verify.block_verifier import get_block_verifier

logger = logging.getLogger(__name__)


def _extract_chain_health(_name: str, chain: Any) -> tuple[dict[str, Any], bool]:
    """Extract health metrics and validation status for a single sub-chain."""
    is_valid = chain.is_chain_valid()
    chain_blocks = len(chain.chain)
    chain_events = 0
    chain_entities = 0
    chain_operations = 0

    if hasattr(chain, "get_domain_statistics"):
        try:
            stats = chain.get_domain_statistics()
            chain_blocks = stats.get("total_blocks", chain_blocks)
            chain_events = stats.get("total_events", 0)
            chain_entities = stats.get("registered_entities", 0)
            chain_operations = stats.get("completed_operations", 0)
        except (AttributeError, KeyError, ValueError, RuntimeError):
            pass

    details = {
        "domain_type": chain.domain_type,
        "blocks": chain_blocks,
        "events": chain_events,
        "entities": chain_entities,
        "operations": chain_operations,
        "valid": is_valid,
    }
    return details, is_valid


def _verify_chain_blocks(verifier: Any, _name: str, chain: Any) -> dict[str, Any]:
    """Verify chain blocks using the provided verifier."""
    result = verifier.verify_chain(chain.chain, chain.trusted_public_keys)
    return {"valid": result.is_valid, "message": result.message}


def _validate_all_sub_chains(
    sub_chains: dict[str, Any], verifier: Any
) -> tuple[dict, dict, bool]:
    """Perform validation for all sub-chains."""
    sub_validation = {}
    block_verification = {}
    consistent = True

    for name, chain in sub_chains.items():
        is_valid = chain.is_chain_valid()
        sub_validation[name] = is_valid
        sub_res = _verify_chain_blocks(verifier, name, chain)
        block_verification[name] = sub_res

        if not is_valid or not sub_res["valid"]:
            consistent = False
            logger.warning("Sub-chain %s verification failed", name)

    return sub_validation, block_verification, consistent


def _compute_system_integrity_report(manager: Any) -> dict[str, Any]:
    """Compute system integrity report."""
    total_sub_chain_events = 0
    total_sub_chain_blocks = 0
    sub_chain_details: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    overall_status = "HEALTHY"

    if not manager.main_chain.is_chain_valid():
        overall_status = "DEGRADED"
        issues.append("Main Chain validation failed")

    for name, chain in manager.sub_chains.items():
        details, is_valid = _extract_chain_health(name, chain)
        if not is_valid:
            overall_status = "DEGRADED"
            issues.append(f"Sub-chain {name} validation failed")

        total_sub_chain_blocks += details["blocks"]
        total_sub_chain_events += details["events"]
        sub_chain_details[name] = details

    return {
        "timestamp": time.time(),
        "overall_status": overall_status,
        "integrity_status": overall_status,
        "system_overview": {
            "total_sub_chains": len(manager.sub_chains),
            "total_sub_chain_blocks": total_sub_chain_blocks,
            "total_sub_chain_events": total_sub_chain_events,
            "system_uptime": time.time() - manager.system_started_at,
        },
        "main_chain": {
            "valid": manager.main_chain.is_chain_valid(),
            "height": len(manager.main_chain.chain),
        },
        "sub_chains": {
            name: {"valid": details["valid"], "height": details["blocks"]}
            for name, details in sub_chain_details.items()
        },
        "sub_chain_details": sub_chain_details,
        "issues": issues,
    }


def _compute_proof_consistency(
    main_chain: Any, sub_chains: dict[str, Any]
) -> dict[str, Any]:
    """Compute proof consistency between main chain and sub-chains."""
    consistency_report: dict[str, Any] = {}
    for name, chain in sub_chains.items():
        latest_block = chain.get_latest_block()
        latest_proof = main_chain.latest_proofs.get(name)
        chain_height = len(chain.chain)
        block_index = latest_block.index if latest_block else None

        def submission_is_due() -> bool:
            should_submit = getattr(chain, "should_submit_proof", None)
            if not callable(should_submit):
                return True
            try:
                return bool(should_submit())
            except Exception:
                logger.exception("Could not determine proof schedule for %s", name)
                return True

        if not latest_proof:
            pending = latest_block is not None and not submission_is_due()
            consistency_report[name] = {
                "consistent": False,
                "pending": pending,
                "reason": (
                    "No proof submitted yet; the current tip is within the "
                    "configured submission interval"
                    if pending
                    else "No proof submitted for the current Sub-Chain tip"
                ),
                "chain_height": chain_height,
                "last_block_index": block_index,
            }
            continue

        proof_hash = latest_proof.get("proof_hash")
        matches_tip = (
            latest_block is not None
            and isinstance(proof_hash, str)
            and proof_hash == latest_block.hash
        )
        anchored_index = latest_proof.get("latest_block_index")
        tip_advanced = (
            isinstance(anchored_index, int)
            and not isinstance(anchored_index, bool)
            and isinstance(block_index, int)
            and block_index > anchored_index
        )
        pending = not matches_tip and tip_advanced and not submission_is_due()
        consistency_report[name] = {
            "consistent": matches_tip,
            "pending": pending,
            "reason": (
                None
                if matches_tip
                else (
                    "The Sub-Chain tip advanced and its next proof is not yet due"
                    if pending
                    else "The latest MainChain proof does not match the current "
                    "Sub-Chain tip"
                )
            ),
            "latest_proof_hash": proof_hash,
            "latest_block_hash": latest_block.hash if latest_block else None,
            "latest_proof_block_index": anchored_index,
            "chain_height": chain_height,
            "last_block_index": block_index,
        }

    return consistency_report


def _validate_cross_chain_consistency(manager: Any) -> dict[str, Any]:
    """Validate cross-chain consistency."""
    verifier = get_block_verifier()
    results: dict[str, Any] = {
        "timestamp": time.time(),
        "main_chain_valid": manager.main_chain.is_chain_valid(),
        "overall_consistent": True,
    }

    main_res = _verify_chain_blocks(verifier, "main_chain", manager.main_chain)
    results["block_verification"] = {"main_chain": main_res}
    if not main_res["valid"]:
        results["overall_consistent"] = False

    sub_val, block_ver, sub_consistent = _validate_all_sub_chains(
        manager.sub_chains, verifier
    )
    results["sub_chain_validation"] = sub_val
    results["block_verification"].update(block_ver)
    if not sub_consistent:
        results["overall_consistent"] = False

    results["proof_consistency"] = _compute_proof_consistency(
        manager.main_chain, manager.sub_chains
    )
    # Pending describes why an anchor is not yet available; it does not make
    # the child tip match the latest durable MainChain proof. Keep the useful
    # scheduling detail while reporting the cross-chain state as unverified.
    if any(
        not proof["consistent"]
        for proof in results["proof_consistency"].values()
    ):
        results["overall_consistent"] = False
    return results
