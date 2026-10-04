"""
Replay and verify durable chain history for the hierarchy coordinator.

State and resource ownership remain with HierarchyManager. Bootstrap invokes
these helpers before serving requests and owns cleanup if recovery fails.
"""

from __future__ import annotations

import math
from contextlib import ExitStack
from copy import deepcopy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hierachain.hierarchical.hierarchy_manager.base import HierarchyManager

def _restore_main_chain(self: HierarchyManager) -> None:
    """Restore and verify the signed MainChain history before accepting proofs."""
    from hierachain.consensus.ordering.storage import (
        _block_from_dict,
        _verify_chain_links,
    )
    from hierachain.hierarchical.main_chain.proofs import _refresh_durable_proofs

    saved = self.storage.load_chain(self.main_chain.name)
    if not isinstance(saved, dict):
        raise RuntimeError("Could not load main chain from durable storage")
    rows = saved.get("chain", [])
    if not rows:
        return
    blocks = [_block_from_dict(row, self.main_chain.trusted_public_keys) for row in rows]
    if blocks[0].index != 0 or any(block.index != index for index, block in enumerate(blocks)):
        raise RuntimeError("Main chain block indices are incomplete")
    _verify_chain_links(blocks)
    main = self.main_chain
    main.chain = blocks
    main._rebuild_event_indexes()
    _refresh_durable_proofs(main)
    main.proof_sequence = main.proof_count

    # Registration state is an in-memory index over signed MainChain
    # events. Rebuild it before _restore_sub_chains reconnects children;
    # otherwise every restart appends another registration event and can
    # replace the original registration metadata.
    from hierachain.core.utils import get_block_events

    registrations: dict[str, tuple[dict[str, Any], float]] = {}
    for block in main.chain:
        for event in get_block_events(block):
            if event.get("event") != "sub_chain_registration":
                continue
            name = event.get("entity_id")
            details = event.get("details")
            metadata = details.get("metadata") if isinstance(details, dict) else None
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(details, dict)
                or details.get("sub_chain_name") != name
                or not isinstance(metadata, dict)
                or (
                    "sub_chain_name" in metadata
                    and metadata["sub_chain_name"] != name
                )
                or (
                    "domain_type" in metadata
                    and (
                        not isinstance(metadata["domain_type"], str)
                        or not metadata["domain_type"]
                    )
                )
            ):
                raise RuntimeError("Invalid signed sub-chain registration event")
            event_timestamp = event.get("timestamp")
            try:
                valid_timestamp = (
                    isinstance(event_timestamp, (int, float))
                    and not isinstance(event_timestamp, bool)
                    and math.isfinite(event_timestamp)
                )
            except OverflowError:
                valid_timestamp = False
            if not valid_timestamp:
                raise RuntimeError("Invalid sub-chain registration timestamp")
            previous = registrations.get(name)
            previous_domain = previous[0].get("domain_type") if previous else None
            current_domain = metadata.get("domain_type")
            if (
                previous_domain is not None
                and current_domain is not None
                and previous_domain != current_domain
            ):
                raise RuntimeError(
                    f"Conflicting signed domain types for sub-chain {name}"
                )
            restored_metadata = deepcopy(previous[0]) if previous else {}
            restored_metadata.update(deepcopy(metadata))
            registrations[name] = (restored_metadata, float(event_timestamp))

    for name, (metadata, registered_at) in registrations.items():
        consensus = main.consensus
        authorities = getattr(
            consensus, "authorities", getattr(consensus, "validators", set())
        )
        authority_metadata = getattr(
            consensus,
            "authority_metadata",
            getattr(consensus, "validator_metadata", None),
        )
        restored_authority = {
            "role": "sub_chain",
            "permissions": ["proof_submission"],
            "registered_at": registered_at,
            "metadata": deepcopy(metadata),
        }
        if name in authorities:
            if isinstance(authority_metadata, dict):
                authority_metadata.setdefault(name, restored_authority)
        else:
            add_authority = getattr(consensus, "add_authority", None)
            if not callable(add_authority) or add_authority(name, restored_authority) is not True:
                raise RuntimeError(
                    f"Could not restore sub-chain authority: {name}"
                )

    main.registered_sub_chains = set(registrations)
    main.sub_chain_metadata = {
        name: metadata for name, (metadata, _registered_at) in registrations.items()
    }


def _restore_sub_chains(self: HierarchyManager) -> None:
    """Recreate every persisted sub-chain before serving API requests."""
    if self.storage is None:
        return

    from hierachain.hierarchical.sub_chain import SubChain

    with ExitStack() as cleanup:
        for metadata in self.storage.list_chains():
            name = metadata["name"]
            domain_type = metadata.get("domain_type") or "generic"
            if self.transaction_manager.requires_2pc_participant(name):
                from hierachain.domains.chains.domain_chain import DomainChain

                chain = DomainChain(name, domain_type)
            else:
                chain = SubChain(
                    name=name,
                    domain_type=domain_type,
                    node_identity=self.node_identity,
                )
            cleanup.callback(chain.shutdown)
            self.add_sub_chain(name, chain, persist=False)
        cleanup.pop_all()

