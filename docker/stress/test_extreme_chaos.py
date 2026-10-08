"""
Extreme Chaos & Tsunami Load Test Suite for HieraChain.

Designed to be executed in an isolated Docker / container environment:
1. P2P Transport Malformed Packet Flood: Floods node with corrupted/spoofed raw messages.
2. Rapid Lockdown/Unlock Storm: Broadcasts thousands of high-frequency cluster lockdown events.
"""

import time

from hierachain.cluster.lockdown_types import LockdownMessage, LockdownMessageType


# ============================================================================
# 1. Rapid Lockdown/Unlock Storm Test
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
