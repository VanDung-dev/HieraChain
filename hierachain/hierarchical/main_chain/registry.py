"""
Registry, statistics, and integrity report helpers for Main Chain.
"""

from typing import Any, TYPE_CHECKING

from hierachain.hierarchical.main_chain.proofs import _get_proofs_by_sub_chain_from_main_chain

if TYPE_CHECKING:
    from hierachain.hierarchical.main_chain.base import MainChain


def _get_sub_chain_summary_from_main_chain(
    chain: "MainChain", sub_chain_name: str
) -> dict[str, Any]:
    """Get summary information about a Sub-Chain from the Main Chain."""
    if sub_chain_name not in chain.registered_sub_chains:
        return {}

    proofs = _get_proofs_by_sub_chain_from_main_chain(chain, sub_chain_name)

    return {
        "sub_chain_name": sub_chain_name,
        "registered": True,
        "total_proofs": len(proofs),
        "metadata": chain.sub_chain_metadata.get(sub_chain_name, {}),
        "latest_proof": proofs[-1] if proofs else None,
        "registration_time": chain.sub_chain_metadata.get(sub_chain_name, {}).get(
            "registered_at"
        ),
    }


def _get_main_chain_stats_for_chain(chain: "MainChain") -> dict[str, Any]:
    """Get comprehensive statistics about the Main Chain."""
    base_stats = chain.get_chain_stats()
    proof_events = chain.get_events_by_type("proof_submission")

    return {
        **base_stats,
        "role": "main_chain",
        "registered_sub_chains": len(chain.registered_sub_chains),
        "sub_chains": list(chain.registered_sub_chains),
        "total_proofs": len(proof_events),
        "consensus_type": chain.consensus.name,
        "authorities": chain.consensus.get_validator_count(),
    }


def _get_hierarchical_integrity_report_for_chain(chain: "MainChain") -> dict[str, Any]:
    """Generate an integrity report for the entire hierarchical system."""
    sub_chains: dict[str, Any] = {}
    for sub_chain_name in chain.registered_sub_chains:
        sub_chains[sub_chain_name] = _get_sub_chain_summary_from_main_chain(
            chain, sub_chain_name,
        )

    return {
        "main_chain": {
            "name": chain.name,
            "blocks": len(chain.chain),
            "valid": chain.is_chain_valid(),
            "latest_hash": chain.get_latest_block().hash,
        },
        "sub_chains": sub_chains,
        "total_proofs": chain.proof_count,
        "registered_sub_chains": len(chain.registered_sub_chains),
        "system_integrity": "healthy"
        if chain.is_chain_valid()
        else "compromised",
    }
