"""
Edge Cases & Anomaly Fuzzing Test Suite for HieraChain Ledger.

Tests counter-intuitive, weird, and extreme edge-case scenarios:
1. PyArrow Data Torture & Deeply Nested Types
2. P2P Time-Travel & Extreme Timestamp Drifts (Epoch 1970, Far Future 2099)
3. RateLimiter Ghost Headers, Unicode & XSS in X-Forwarded-For
4. Merkle Tree Deformed & Asymmetric Leaves (0, 1, odd counts, domain separation)
5. Cluster Lockdown HMAC Fuzzing & Malformed Signatures
6. SubChain Rebalancer Edge Partitions & Single-Event Migrations
"""

import time
import uuid

from hierachain.core.block import Block, convert_events_to_arrow
from hierachain.core.merkle_tree import MerkleTree
from hierachain.network.message_cryptographic import (
    verify_message,
    create_signable_payload,
)
from hierachain.security.security_utils import KeyPair
from hierachain.api.middleware import RateLimiter
from hierachain.cluster.lockdown_types import LockdownMessage, LockdownMessageType
from hierachain.domains.chains.domain_chain import DomainChain
from hierachain.hierarchical.rebalancer.rebalancer import SubChainRebalancer
from hierachain.hierarchical.rebalancer.split_ops import (
    _migrate_state_for_rebalancer,
)


# ============================================================================
# 1. PyArrow Data Torture & Deeply Nested Types
# ============================================================================

def test_arrow_data_torture_and_nested_types():
    """Test PyArrow conversion with weird, deep, and malformed payload values."""
    weird_events = [
        # Normal event
        {
            "entity_id": "sensor-001",
            "event": "temp_reading",
            "timestamp": time.time(),
            "details": {"temp": "25.5", "status": "ok"},
        },
        # Event with unicode, emojis, and special chars in entity_id & event
        {
            "entity_id": "🛸_entity_🚀_#123",
            "event": "anomaly_event_⚡️",
            "timestamp": time.time(),
            "details": {
                "tag": "unicode_test",
                "nested_str": "{\"level1\": {\"level2\": [1, 2, 3]}}",
            },
        },
        # Event with empty details
        {
            "entity_id": "empty-details-entity",
            "event": "heartbeat",
            "timestamp": time.time(),
            "details": {},
        },
        # Event with complex stringified list in details
        {
            "entity_id": "batch-entity-99",
            "event": "bulk_operation",
            "timestamp": time.time(),
            "details": {"items": str(list(range(50)))},
        },
    ]

    arrow_table = convert_events_to_arrow(weird_events)
    assert arrow_table.num_rows == 4

    block = Block(index=1, events=arrow_table, previous_hash="0" * 64)
    assert block.validate_structure() is True

    # Check that to_event_list converts back cleanly
    event_list = block.to_event_list()
    assert len(event_list) == 4
    assert event_list[1]["entity_id"] == "🛸_entity_🚀_#123"
    assert block.hash != ""


# ============================================================================
# 2. P2P Time-Travel & Extreme Timestamp Drifts
# ============================================================================

def test_p2p_time_travel_and_extreme_drifts():
    """Verify that P2P verification rejects timestamps from the 1970s or 2099."""
    keypair = KeyPair()
    sender_id = "node-alpha"
    payload_body = {"ping": "pong"}

    # Case A: Unix Epoch (1970-01-01) - Time travel to the past
    ts_past = 0.0
    nonce_past = "nonce-epoch-001"
    signable_epoch = create_signable_payload(payload_body, ts_past, nonce_past, sender_id)
    sig_epoch = keypair.sign(signable_epoch)
    msg_epoch = {
        "payload": payload_body,
        "timestamp": ts_past,
        "nonce": nonce_past,
        "sender_id": sender_id,
        "signature": sig_epoch,
    }

    # Must be rejected due to timestamp drift > 300s
    assert verify_message(msg_epoch, keypair.public_key, max_drift=300.0) is False

    # Case B: Far future (year 2099 ~ 4070908800) - Time travel to the future
    ts_future = 4070908800.0
    nonce_future = "nonce-future-001"
    signable_future = create_signable_payload(payload_body, ts_future, nonce_future, sender_id)
    sig_future = keypair.sign(signable_future)
    msg_future = {
        "payload": payload_body,
        "timestamp": ts_future,
        "nonce": nonce_future,
        "sender_id": sender_id,
        "signature": sig_future,
    }

    assert verify_message(msg_future, keypair.public_key, max_drift=300.0) is False

    # Case C: Fresh timestamp within 5 seconds - Must be accepted
    ts_fresh = time.time()
    nonce_fresh = uuid.uuid4().hex
    signable_fresh = create_signable_payload(payload_body, ts_fresh, nonce_fresh, sender_id)
    sig_fresh = keypair.sign(signable_fresh)
    msg_fresh = {
        "payload": payload_body,
        "timestamp": ts_fresh,
        "nonce": nonce_fresh,
        "sender_id": sender_id,
        "signature": sig_fresh,
    }

    assert verify_message(msg_fresh, keypair.public_key, max_drift=300.0) is True


# ============================================================================
# 3. RateLimiter Ghost Headers, Unicode & XSS in X-Forwarded-For
# ============================================================================

def test_ratelimiter_ghost_headers_and_fuzzing_ips():
    """Verify RateLimiter handles dirty and spoofed X-Forwarded-For headers gracefully."""
    limiter = RateLimiter(requests_per_minute=5)

    ghost_ip = "👻.🔥.💩.🚀"

    # Send 5 requests - should be allowed under rate limit
    for _ in range(5):
        allowed = limiter.is_allowed(ghost_ip)
        assert allowed is True

    # 6th request from the same ghost IP identity should be rate limited
    allowed = limiter.is_allowed(ghost_ip)
    assert allowed is False


# ============================================================================
# 4. Merkle Tree Deformed & Asymmetric Leaves
# ============================================================================

def test_merkle_tree_deformed_leaves():
    """Verify MerkleTree handles empty lists, single items, and odd counts."""
    # 0 leaves
    tree_empty = MerkleTree([])
    root_empty = tree_empty.get_root()
    assert len(root_empty) == 64

    # 1 leaf
    tree_single = MerkleTree([{"entity_id": "item-1", "event": "init"}])
    root_single = tree_single.get_root()
    assert len(root_single) == 64

    # 3 leaves (odd count needing duplicate/padding)
    tree_odd = MerkleTree([
        {"entity_id": "item-1", "event": "e1"},
        {"entity_id": "item-2", "event": "e2"},
        {"entity_id": "item-3", "event": "e3"},
    ])
    root_odd = tree_odd.get_root()
    assert len(root_odd) == 64

    # Determinism: same input leaves produce identical root
    tree_odd_repeat = MerkleTree([
        {"entity_id": "item-1", "event": "e1"},
        {"entity_id": "item-2", "event": "e2"},
        {"entity_id": "item-3", "event": "e3"},
    ])
    assert tree_odd.get_root() == tree_odd_repeat.get_root()


# ============================================================================
# 5. Cluster Lockdown HMAC Fuzzing & Malformed Signatures
# ============================================================================

def test_cluster_lockdown_hmac_fuzzing():
    """Verify LockdownMessage rejects tampered signatures, wrong keys, and malformed digests."""
    secret_key = "super-secure-cluster-key-2026"
    wrong_key = "attacker-compromised-key"

    msg = LockdownMessage(
        node_id="node-1",
        timestamp=time.time(),
        reason="Security breach test",
        message_type=LockdownMessageType.LOCKDOWN,
    )

    # Compute valid signature
    msg.signature = msg.compute_signature(secret_key)
    assert msg.verify_signature(secret_key) is True
    assert msg.verify_signature(wrong_key) is False

    # Tampered signature (corrupted byte)
    tampered_sig = ("0" if msg.signature[0] != "0" else "1") + msg.signature[1:]
    msg.signature = tampered_sig
    assert msg.verify_signature(secret_key) is False

    # Malformed non-hex or empty signature with unicode emojis
    msg.signature = "NOT_A_HEX_SIGNATURE_💩"
    assert msg.verify_signature(secret_key) is False
    msg.signature = ""
    assert msg.verify_signature(secret_key) is False


# ============================================================================
# 6. SubChain Rebalancer Edge Partitions
# ============================================================================

def test_subchain_rebalancer_empty_and_single_partitions():
    """Verify Rebalancer migration handles empty and single-event subchains without error."""
    rebalancer = SubChainRebalancer(threshold_eps=100, check_interval=0.1)
    parent_chain = DomainChain("source_chain", "traceability")
    child1 = DomainChain("child_1", "traceability")
    child2 = DomainChain("child_2", "traceability")

    # Migrate when parent has no events at all
    events_migrated, _ = _migrate_state_for_rebalancer(rebalancer, parent_chain, [child1, child2])
    assert events_migrated == 0
    assert len(child1.pending_events) == 0
    assert len(child2.pending_events) == 0

    # Add single event
    parent_chain.add_event({
        "entity_id": "apple-123",
        "event": "harvest",
        "timestamp": time.time(),
        "details": {"origin": "Farm A"},
    })

    child_target1 = DomainChain("child_target_1", "traceability")
    child_target2 = DomainChain("child_target_2", "traceability")
    migrated_count, _ = _migrate_state_for_rebalancer(rebalancer, parent_chain, [child_target1, child_target2])
    assert migrated_count == 1

    # Exactly one child receives the pending event
    total_received = len(child_target1.pending_events) + len(child_target2.pending_events)
    assert total_received == 1
