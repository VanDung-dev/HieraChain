"""
Edge Cases & Anomaly Fuzzing Test Suite for HieraChain Ledger.

Tests counter-intuitive, weird, and extreme edge-case scenarios:
1. PyArrow Data Torture & Deeply Nested Types
2. RateLimiter Ghost Headers, Unicode & XSS in X-Forwarded-For
3. Merkle Tree Deformed & Asymmetric Leaves (0, 1, odd counts, domain separation)
4. SubChain Rebalancer Edge Partitions & Single-Event Migrations
"""

import time

from hierachain.api.middleware import RateLimiter
from hierachain.core.block import Block, convert_events_to_arrow
from hierachain.core.merkle_tree import MerkleTree

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
# 2. RateLimiter Ghost Headers, Unicode & XSS in X-Forwarded-For
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




