"""Regression coverage for BFT request binding, quorum voting, and application."""

from __future__ import annotations

import time
from collections import deque
from copy import deepcopy
from typing import Any

import pytest

from hierachain.consensus import BFTConsensus, BFTMessage, MessageType, sign_message
from hierachain.consensus.bft.types import ConsensusState
from hierachain.security import KeyPair


def _build_network() -> dict[str, BFTConsensus]:
    node_ids = ["node_1", "node_2", "node_3", "node_4"]
    keypairs = {node_id: KeyPair() for node_id in node_ids}
    public_keys = {node_id: keypair.public_key for node_id, keypair in keypairs.items()}
    return {
        node_id: BFTConsensus(
            node_id=node_id,
            all_nodes=node_ids,
            f=1,
            keypair=keypairs[node_id],
            node_public_keys=public_keys,
        )
        for node_id in node_ids
    }


def _shutdown_network(network: dict[str, BFTConsensus]) -> None:
    for node in network.values():
        node.shutdown()


def test_later_quorum_waits_for_earlier_failed_application() -> None:
    network = _build_network()

    class FailFirstWrite:
        def __init__(self) -> None:
            self.calls = 0
            self.events: list[dict[str, Any]] = []

        def add_event(self, event: dict[str, Any]) -> None:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("Earlier event storage is unavailable")
            self.events.append(deepcopy(event))

    chain = FailFirstWrite()
    replica = network["node_2"]
    replica.chain = chain
    try:
        for seq in (1, 2):
            assert network["node_1"].request({
                "client_id": "client", "entity_id": f"entity-{seq}", "event_type": "created",
            })
            assert replica.handle_message(network["node_1"].pre_prepare_messages[seq].to_dict())
            digest = network["node_1"].pre_prepare_messages[seq].data["digest"]
            assert replica.handle_message(_signed_vote(network, "node_3", MessageType.PREPARE, seq, digest))
        commits: dict[int, dict[str, Any]] = {}
        for seq in (1, 2):
            digest = network["node_1"].pre_prepare_messages[seq].data["digest"]
            assert replica.handle_message(_signed_vote(network, "node_1", MessageType.COMMIT, seq, digest)) is False
            commits[seq] = _signed_vote(network, "node_3", MessageType.COMMIT, seq, digest)
            assert replica.handle_message(commits[seq]) is False
        assert replica.committed_sequence == -1
        assert chain.events == []
        assert replica.handle_message(commits[1]) is True
        assert replica.committed_sequence == 2
        assert [event["entity_id"] for event in chain.events] == ["entity-1", "entity-2"]
        assert replica.handle_message(commits[2]) is True
        assert [event["entity_id"] for event in chain.events] == ["entity-1", "entity-2"]
        assert replica.committed_sequence == 2
    finally:
        _shutdown_network(network)


def test_future_quorum_waits_for_missing_pre_prepare() -> None:
    network = _build_network()

    class RecordingChain:
        def __init__(self) -> None:
            self.events: list[dict[str, Any]] = []

        def add_event(self, event: dict[str, Any]) -> None:
            self.events.append(deepcopy(event))

    replica = network["node_2"]
    chain = RecordingChain()
    replica.chain = chain
    try:
        for seq in (1, 2):
            assert network["node_1"].request({"entity_id": f"entity-{seq}", "event_type": "created"})
        for seq in (2, 1):
            message = network["node_1"].pre_prepare_messages[seq].to_dict()
            assert replica.handle_message(message)
            digest = message["data"]["digest"]
            assert replica.handle_message(_signed_vote(network, "node_3", MessageType.PREPARE, seq, digest))
            assert replica.handle_message(_signed_vote(network, "node_1", MessageType.COMMIT, seq, digest)) is False
            final_vote = _signed_vote(network, "node_3", MessageType.COMMIT, seq, digest)
            if seq == 2:
                assert replica.handle_message(final_vote) is False
                assert replica.committed_sequence == -1
                assert chain.events == []
            else:
                assert replica.handle_message(final_vote) is True
                assert replica.committed_sequence == 2
                assert [event["entity_id"] for event in chain.events] == ["entity-1", "entity-2"]
    finally:
        _shutdown_network(network)


def _signed_vote(
    network: dict[str, BFTConsensus],
    sender_id: str,
    message_type: MessageType,
    sequence_number: int,
    digest: str,
) -> dict[str, Any]:
    message = BFTMessage(
        message_type=message_type,
        view=0,
        sequence_number=sequence_number,
        sender_id=sender_id,
        timestamp=time.time(),
        signature="",
        data={"digest": digest},
    )
    message.signature = sign_message(
        network[sender_id].key_provider,
        message.get_signable_payload(),
    )
    return message.to_dict()


def _prepare_commit_quorum(
    network: dict[str, BFTConsensus], replica: BFTConsensus
) -> dict[str, Any]:
    assert network["node_1"].request(
        {
            "client_id": "client-1",
            "entity_id": "entity-1",
            "event_type": "record_updated",
            "details": {"status": "approved"},
        }
    )
    pre_prepare = network["node_1"].pre_prepare_messages[1].to_dict()
    assert replica.handle_message(pre_prepare)
    digest = pre_prepare["data"]["digest"]
    assert replica.handle_message(
        _signed_vote(network, "node_3", MessageType.PREPARE, 1, digest)
    )
    assert replica.handle_message(
        _signed_vote(network, "node_1", MessageType.COMMIT, 1, digest)
    ) is False
    return _signed_vote(network, "node_3", MessageType.COMMIT, 1, digest)


def test_signed_pre_prepare_rejects_mutated_request_body() -> None:
    network = _build_network()
    try:
        operation = {
            "entity_id": "entity-original",
            "event_type": "record_updated",
            "details": {"status": "approved"},
        }
        assert network["node_1"].request(
            {"client_id": "client-1", **operation}
        )

        signed_pre_prepare = network["node_1"].pre_prepare_messages[1].to_dict()
        retained_digest = signed_pre_prepare["data"]["digest"]
        retained_signature = signed_pre_prepare["signature"]
        signed_pre_prepare["data"]["request"]["operation"]["entity_id"] = (
            "entity-substituted"
        )

        assert signed_pre_prepare["data"]["digest"] == retained_digest
        assert signed_pre_prepare["signature"] == retained_signature
        assert network["node_2"].handle_message(signed_pre_prepare) is False
        assert 1 not in network["node_2"].pre_prepare_messages
    finally:
        _shutdown_network(network)


@pytest.mark.parametrize("operation_count", [1, 2])
def test_three_live_nodes_commit_with_one_unavailable_peer_and_local_votes(operation_count: int) -> None:
    network = _build_network()
    queue: deque[tuple[str, str, dict[str, Any]]] = deque()

    class RecordingChain:
        def __init__(self) -> None:
            self.events: list[dict[str, Any]] = []

        def add_event(self, event: dict[str, Any]) -> str:
            self.events.append(deepcopy(event))
            return "event-accepted"

    chains = {node_id: RecordingChain() for node_id in network}
    for node_id, node in network.items():
        node.chain = chains[node_id]

        def send(
            target_id: str,
            message: dict[str, Any],
            source_id: str = node_id,
        ) -> None:
            if source_id == "node_4" or target_id == "node_4":
                return
            queue.append((source_id, target_id, deepcopy(message)))

        node.set_network_send_function(send)

    try:
        for sequence in range(1, operation_count + 1):
            assert network["node_1"].request({
                "client_id": "client-1", "entity_id": f"entity-{sequence}",
                "event_type": "record_updated", "details": {"status": "approved"},
            })

        handled = 0
        while queue and handled < 1000:
            _source_id, target_id, message = queue.popleft()
            network[target_id].handle_message(message)
            handled += 1

        assert not queue
        for node_id in ("node_1", "node_2", "node_3"):
            node = network[node_id]
            assert node.committed_sequence == operation_count
            assert node.state is ConsensusState.COMMITTED
            assert [event["entity_id"] for event in chains[node_id].events] == [
                f"entity-{sequence}" for sequence in range(1, operation_count + 1)
            ]
            for sequence in range(1, operation_count + 1):
                assert chains[node_id].events[sequence - 1]["details"] == {"status": "approved"}
                assert sum(vote.sender_id == node_id for vote in node.prepare_messages[sequence]) == 1
                assert sum(vote.sender_id == node_id for vote in node.commit_messages[sequence]) == 1
                assert len({vote.sender_id for vote in node.prepare_messages[sequence]}) == 3
                assert len({vote.sender_id for vote in node.commit_messages[sequence]}) == 3
    finally:
        _shutdown_network(network)


def test_failed_event_write_keeps_commit_quorum_for_stable_retry() -> None:
    network = _build_network()

    class FailOnceChain:
        def __init__(self) -> None:
            self.attempts: list[dict[str, Any]] = []

        def add_event(self, event: dict[str, Any]) -> str:
            self.attempts.append(deepcopy(event))
            if len(self.attempts) == 1:
                raise RuntimeError("temporary event storage failure")
            return "event-accepted"

    chain = FailOnceChain()
    replica = network["node_2"]
    replica.chain = chain

    try:
        node_3_commit = _prepare_commit_quorum(network, replica)
        assert replica.handle_message(node_3_commit) is False
        assert replica.committed_sequence == -1
        assert 1 in replica.pending_apply_events
        assert 1 in replica.pre_prepare_messages
        assert len(replica.commit_messages[1]) == 3

        assert replica.handle_message(node_3_commit) is True
        assert replica.committed_sequence == 1
        assert 1 not in replica.pending_apply_events
        assert len(chain.attempts) == 2
        assert chain.attempts[0] == chain.attempts[1]

        assert replica.handle_message(node_3_commit) is True
        assert len(chain.attempts) == 2
        assert 1 in replica.pre_prepare_messages
        assert 1 in replica.commit_messages
    finally:
        _shutdown_network(network)


def test_false_event_write_result_remains_retryable() -> None:
    network = _build_network()

    class RejectOnceChain:
        def __init__(self) -> None:
            self.attempts: list[dict[str, Any]] = []

        def add_event(self, event: dict[str, Any]) -> str | bool:
            self.attempts.append(deepcopy(event))
            if len(self.attempts) == 1:
                return False
            return "event-accepted"

    chain = RejectOnceChain()
    replica = network["node_2"]
    replica.chain = chain

    try:
        node_3_commit = _prepare_commit_quorum(network, replica)

        assert replica.handle_message(node_3_commit) is False
        assert replica.committed_sequence == -1
        assert 1 in replica.pending_apply_events
        assert replica.handle_message(node_3_commit) is True
        assert replica.committed_sequence == 1
        assert len(chain.attempts) == 2
        assert chain.attempts[0] == chain.attempts[1]
    finally:
        _shutdown_network(network)
