"""
Unit tests for ZMQ transport layer replay protection mechanism.

Tests cover validation of message timestamps, nonce uniqueness and automatic
cleanup of expired entries from the replay buffer.
"""

import pytest
import time
import uuid
from hierachain.network.zmq_transport import ZmqNode

@pytest.fixture
def node():
    node = ZmqNode("test_node", 5000)
    return node

def test_valid_fresh_message(node):
    msg = {
        "timestamp": time.time(),
        "nonce": str(uuid.uuid4()),
        "content": "hello"
    }
    assert node._is_valid_replay(msg) == True
    assert len(node.replay_buffer) == 1

def test_missing_timestamp(node):
    msg = {
        "nonce": str(uuid.uuid4()),
        "content": "hello"
    }
    assert node._is_valid_replay(msg) == False

def test_missing_nonce(node):
    msg = {
        "timestamp": time.time(),
        "content": "hello"
    }
    assert node._is_valid_replay(msg) == False

def test_duplicate_nonce(node):
    nonce = str(uuid.uuid4())
    msg = {
        "timestamp": time.time(),
        "nonce": nonce,
        "content": "hello"
    }
    # First send is valid
    assert node._is_valid_replay(msg) == True

    # Second send with same nonce is invalid
    assert node._is_valid_replay(msg) == False

def test_old_message_rejection(node):
    old_time = time.time() - (node.replay_tolerance + 10)
    msg = {
        "timestamp": old_time,
        "nonce": str(uuid.uuid4()),
        "content": "old"
    }
    assert node._is_valid_replay(msg) == False

def test_future_message_rejection(node):
    # Assuming tolerance applies to future too (abs check)
    future_time = time.time() + (node.replay_tolerance + 10)
    msg = {
        "timestamp": future_time,
        "nonce": str(uuid.uuid4()),
        "content": "future"
    }
    assert node._is_valid_replay(msg) == False

def test_buffer_cleanup(node):
    # 1. Add an old valid message (just on the edge or manually insert)
    # We can't insert "old" message via valid_replay check because it will reject it.
    # So we manually insert into buffer to test cleanup logic if we trigger it with a new message.

    old_ts = time.time() - (node.replay_tolerance + 10)
    old_entry = (old_ts, "old_nonce")
    node.replay_buffer.add(old_entry)

    # 2. Process a new valid message
    new_msg = {
        "timestamp": time.time(),
        "nonce": "new_nonce"
    }
    assert node._is_valid_replay(new_msg) == True

    # 3. Verify old entry is gone
    assert old_entry not in node.replay_buffer
    assert (new_msg["timestamp"], "new_nonce") in node.replay_buffer
