"""
Unit tests for ZeroMQ transport layer.
"""

import asyncio
import sys
import pytest
from hierachain.network.zmq_transport import ZmqNode

# Fix for Windows asyncio compatibility with ZMQ
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def setup_nodes():
    """Set up two ZMQ nodes for testing."""
    # Use different ports to avoid conflicts
    port1 = 5601
    port2 = 5602

    node1 = ZmqNode("node1", port1)
    node2 = ZmqNode("node2", port2)

    # Register peers with each other
    node1.register_peer("node2", f"tcp://localhost:{port2}")
    node2.register_peer("node1", f"tcp://localhost:{port1}")

    await node1.start()
    await node2.start()

    # Allow time for sockets to bind/connect
    await asyncio.sleep(0.3)
    
    return node1, node2, port1, port2


async def teardown_nodes(node1, node2):
    """Tear down the ZMQ nodes."""
    await node1.stop()
    await node2.stop()
    await asyncio.sleep(0.2)


def test_keypair_generation():
    """Test that a key pair can be generated."""
    from hierachain.security.security_utils import KeyPair
    
    kp = KeyPair()
    assert kp.private_key is not None
    assert kp.public_key is not None
    assert len(kp.public_key) == 64  # Hex length of 32 bytes


def test_signing_verification():
    """Test signing and verifying a message."""
    from hierachain.security.security_utils import KeyPair, verify_signature
    
    kp = KeyPair()
    message = b"hello world"
    signature = kp.sign(message)

    assert len(signature) == 128  # Hex length of 64 bytes

    # Verify with helper
    assert verify_signature(kp.public_key, message, signature)

    # Verify failure with wrong message
    assert not verify_signature(kp.public_key, b"other message", signature)


def test_import_export():
    """Test exporting and importing a private key."""
    from hierachain.security.security_utils import KeyPair
    
    kp = KeyPair()
    priv_hex = kp.private_key

    kp2 = KeyPair.from_private_key(priv_hex)
    assert kp.public_key == kp2.public_key

    sig = kp.sign(b"test")
    sig2 = kp2.sign(b"test")
    assert sig == sig2


@pytest.mark.asyncio
async def test_direct_message():
    """Test sending a direct message from node1 to node2."""
    node1, node2, _, _ = await setup_nodes()
    
    try:
        received_messages = []

        def handler(msg, sender):
            received_messages.append((sender, msg))

        node2.set_handler(handler)

        msg = {"type": "ping", "data": "hello"}
        result = await node1.send_direct("node2", msg)

        assert result

        # Wait for message delivery
        await asyncio.sleep(0.5)

        assert len(received_messages) == 1
        sender, received_msg = received_messages[0]
        assert sender == "node1"
        assert received_msg == msg
    finally:
        await teardown_nodes(node1, node2)