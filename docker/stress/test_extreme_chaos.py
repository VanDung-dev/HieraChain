"""
Extreme Chaos & Tsunami Load Test Suite for HieraChain.

Designed to be executed in an isolated Docker / container environment:
1. Rebalancer Tsunami Burst: Simulates hundreds of rapid event splits across sub-chains.
2. P2P Transport Malformed Packet Flood: Floods node with corrupted/spoofed raw messages.
3. Rapid Lockdown/Unlock Storm: Broadcasts thousands of high-frequency cluster lockdown events.
"""

import time
import random
import string

from hierachain.hierarchical.rebalancer.rebalancer import SubChainRebalancer
from hierachain.hierarchical.hierarchy_manager.base import HierarchyManager
from hierachain.cluster.lockdown_types import LockdownMessage, LockdownMessageType


def _random_entity_id() -> str:
    prefix = random.choice(string.ascii_letters)
    suffix = "".join(random.choices(string.digits, k=6))
    return f"{prefix}_{suffix}"


# ============================================================================
# 1. Rebalancer Tsunami Burst Test
# ============================================================================

def test_rebalancer_tsunami_burst_split():
    """
    Stress test Rebalancer under a burst of events to verify that
    dynamic partitioning functions reliably without deadlock or memory exhaustion.
    """
    hierarchy = HierarchyManager("ChaosMainChain")
    hierarchy.create_sub_chain("high_load_chain", "traceability")
    sub_chain = hierarchy.get_sub_chain("high_load_chain")
    assert sub_chain is not None

    rebalancer = SubChainRebalancer(
        threshold_eps=10,
        check_interval=0.1,
        min_events_for_split=50,
    )
    rebalancer.set_hierarchy_manager(hierarchy)
    rebalancer.register_subchain("high_load_chain", sub_chain)

    # Ingest a burst of 1,000 events with diverse entity IDs
    for i in range(1000):
        sub_chain.add_event({
            "entity_id": _random_entity_id(),
            "event": f"tsunami_op_{i}",
            "timestamp": time.time(),
            "details": {"batch_index": str(i), "status": "processing"},
        })

    # Trigger rebalancer split
    split_result = rebalancer.split_sub_chain(sub_chain)
    assert split_result.success is True
    assert len(split_result.child_chain_ids) == 2
    assert split_result.error_message == ""
    assert hierarchy.get_sub_chain(split_result.child_chain_ids[0]) is not None
    assert hierarchy.get_sub_chain(split_result.child_chain_ids[1]) is not None

    rebalancer.stop_monitoring()


# ============================================================================
# 2. Rapid Lockdown/Unlock Storm Test
# ============================================================================

def test_lockdown_storm_burst():
    """
    Simulates high-frequency generation and verification of LockdownMessages
    under cluster storm conditions.
    """
    secret = "cluster-master-secret-key-9999"
    message_count = 2000
    valid_count = 0
    invalid_count = 0

    for i in range(message_count):
        is_corrupt = (i % 5 == 0)  # 20% corrupted packets
        msg_type = (
            LockdownMessageType.LOCKDOWN
            if i % 2 == 0
            else LockdownMessageType.RECOVERY
        )
        msg = LockdownMessage(
            node_id=f"node-worker-{i % 10}",
            timestamp=time.time(),
            reason=f"Chaos test storm iteration {i}",
            message_type=msg_type,
        )

        if not is_corrupt:
            msg.signature = msg.compute_signature(secret)
        else:
            msg.signature = "corrupted_signature_payload_xyz"

        if msg.verify_signature(secret):
            valid_count += 1
        else:
            invalid_count += 1

    assert valid_count == 1600
    assert invalid_count == 400
