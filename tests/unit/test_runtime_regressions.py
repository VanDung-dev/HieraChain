"""P2 regressions for journal and network paths."""

import asyncio
import time
from pathlib import Path

import pytest
import zmq

from hierachain.error_mitigation.journal import TransactionJournal
from hierachain.network.zmq_transport import (
    MAX_MESSAGE_BYTES,
    MAX_REPLAY_ENTRIES,
    ZmqNode,
    _handle_received_message,
)
from hierachain.serialization import dumps_json


def test_journal_rejects_ancestor_and_dangling_symlinks(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "data" / "alias").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="Security"):
        TransactionJournal("data/alias/journal")
    assert not (outside / "journal").exists()
    (tmp_path / "data" / "journal").mkdir()
    (tmp_path / "data" / "journal" / "current.arrow").symlink_to(outside / "missing")
    with pytest.raises(ValueError, match="Security"):
        TransactionJournal()


@pytest.mark.asyncio
async def test_network_replay_cache_isolated_and_rejects_unverified_input() -> None:

    node = ZmqNode("receiver", 0)
    received = []
    node.set_handler(lambda message, sender: received.append(sender))
    node.set_message_validator(lambda message, sender: message.get("verified") is True)
    now = time.time()
    try:
        for index in range(MAX_REPLAY_ENTRIES + 1):
            payload = dumps_json({"timestamp": now, "nonce": str(index), "verified": False}).encode("utf-8")
            await _handle_received_message(node, [b"untrusted", payload])
        assert node.peer_replay_buffers == {}
        node.peer_replay_buffers["busy"] = {(now, str(i)) for i in range(MAX_REPLAY_ENTRIES)}
        await _handle_received_message(node, [
            b"busy", dumps_json({"timestamp": now, "nonce": "overflow", "verified": True}).encode("utf-8"),
        ])
        await _handle_received_message(node, [
            b"healthy", dumps_json({"timestamp": now, "nonce": "accepted", "verified": True}).encode("utf-8"),
        ])
        assert received == ["healthy"]
        await _handle_received_message(node, [b"healthy", b"x" * (MAX_MESSAGE_BYTES + 1)])
        await _handle_received_message(node, [b"healthy", b"", b"{}"])
        assert received == ["healthy"]
    finally:
        await node.stop()


@pytest.mark.asyncio
async def test_receiving_socket_sets_message_size_bound() -> None:
    node = ZmqNode("size-bound", 0)
    await node.start()
    try:
        assert node.router.getsockopt(zmq.MAXMSGSIZE) == MAX_MESSAGE_BYTES
    finally:
        await node.stop()
        await asyncio.sleep(0)
