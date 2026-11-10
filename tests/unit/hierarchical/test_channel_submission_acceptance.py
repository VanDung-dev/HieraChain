"""Focused regressions for channel ledger acceptance and registry rollback."""

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from hierachain.hierarchical.channel import Channel, Organization
from hierachain.hierarchical.channel.types import ChannelStatus
from hierachain.hierarchical.private_data import PrivateCollection
from hierachain.security.identity_loader import NodeIdentity
from hierachain.security.security_utils import KeyPair


def _identity_and_keys() -> tuple[NodeIdentity, dict[str, bytes]]:
    keypair = KeyPair.generate()
    identity = NodeIdentity({
        "node_id": "node-a",
        "msp_id": "OrgA-MSP",
        "signing_key": keypair.private_key,
        "signing_public_key": keypair.public_key,
        "transport_secret_key": "",
        "transport_public_key": "",
    })
    public_key = Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(keypair.public_key)
    ).public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return identity, {identity.node_id: public_key}


def _organization(org_id: str, user_id: str) -> Organization:
    member = {
        "identity": {"user_id": user_id, "org_id": org_id, "role": "admin"},
        "role": "admin",
    }
    return Organization(
        org_id=org_id,
        name=org_id,
        msp_id=f"{org_id}-MSP",
        endpoints=[],
        certificates={},
        roles={"admin"},
        member_registry={user_id: member},
    )


def test_submit_event_fails_when_ledger_rejects_and_keeps_statistics_unchanged() -> None:
    channel = Channel("orders", [_organization("org-a", "admin-a")], {"write": "ADMIN"})

    accepted = channel.submit_event(
        {"event": "created"}, "org-a", submitter_user_id="admin-a"
    )

    assert not accepted
    assert channel.ledger.current_block_events == []
    assert channel.event_statistics["total_events"] == 0
    assert channel.event_statistics["events_by_org"]["org-a"] == 0


def test_registry_mutation_rolls_back_when_persistence_fails() -> None:
    channel = Channel(
        "orders",
        [_organization("org-a", "admin-a"), _organization("org-b", "admin-b")],
        {"endorsement": "MAJORITY"},
    )
    old_policy = channel.policy
    channel._persist_registry = lambda: False

    assert not channel.suspend_channel("maintenance", ["org-a", "org-b"])
    assert channel.status is ChannelStatus.ACTIVE
    assert not channel.update_channel_policy({"write": "MEMBER"}, ["org-a", "org-b"])
    assert channel.policy is old_policy


def test_submit_event_auto_finalizes_block_when_block_size_reached() -> None:
    identity, keys = _identity_and_keys()
    channel = Channel(
        "orders",
        [_organization("org-a", "admin-a")],
        {"write": "ADMIN", "block_size": 2},
        node_identity=identity,
        trusted_public_keys=keys,
    )

    assert channel.submit_event(
        {"entity_id": "e1", "event": "created"}, "org-a", submitter_user_id="admin-a"
    )
    assert channel.ledger.current_block_events

    assert channel.submit_event(
        {"entity_id": "e2", "event": "created"}, "org-a", submitter_user_id="admin-a"
    )
    assert channel.ledger.height == 1
    assert channel.ledger.current_block_events == []
    assert len(channel.ledger.blocks) == 1


def test_private_collection_snapshot_round_trips_entries() -> None:
    org = _organization("org-a", "admin-a")
    collection = PrivateCollection(
        "records",
        {"org-a": org},
        {"endorsement_policy": "ANY", "block_to_purge": 0},
    )
    assert collection.add_data(
        "record-1", {"value": 42}, {"endorsements": ["org-a"]}, "org-a"
    )

    restored = PrivateCollection.restore("records", {"org-a": org}, collection.snapshot())

    assert restored.get_data("record-1", "org-a") == {"value": 42}
    assert restored.get_data_hash("record-1", "org-a") == collection.get_data_hash(
        "record-1", "org-a"
    )


def test_channel_restores_private_collections_from_registry_state() -> None:
    channel = Channel(
        "orders",
        [_organization("org-a", "admin-a")],
        {"write": "ADMIN"},
    )
    assert channel.create_private_collection(
        "records", ["org-a"], {"endorsement_policy": "ANY", "block_to_purge": 0}
    )
    collection = channel.private_collections["records"]
    assert collection.add_data(
        "record-1", {"value": 42}, {"endorsements": ["org-a"]}, "org-a"
    )

    restored = Channel(
        "orders",
        [_organization("org-a", "admin-a")],
        {"write": "ADMIN"},
    )
    restored.restore_private_collections(
        {"records": collection.snapshot()}
    )

    assert restored.private_collections["records"].get_data("record-1", "org-a") == {
        "value": 42
    }


def test_private_collection_rejects_outsider_even_with_valid_quorum() -> None:
    collection = PrivateCollection(
        "records",
        {org_id: object() for org_id in ("org-a", "org-b", "org-c")},
        {"endorsement_policy": "MAJORITY"},
    )

    assert collection._verify_endorsements(["org-a", "org-b"])
    assert not collection._verify_endorsements(["org-a", "org-a"])
    assert not collection._verify_endorsements(["org-a", "org-b", "outsider"])
