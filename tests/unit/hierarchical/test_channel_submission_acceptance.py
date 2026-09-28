"""Focused regressions for channel ledger acceptance and registry rollback."""

from hierachain.hierarchical.channel import Channel, Organization
from hierachain.hierarchical.channel.types import ChannelStatus
from hierachain.hierarchical.private_data import PrivateCollection


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


def test_private_collection_rejects_outsider_even_with_valid_quorum() -> None:
    collection = PrivateCollection(
        "records",
        {org_id: object() for org_id in ("org-a", "org-b", "org-c")},
        {"endorsement_policy": "MAJORITY"},
    )

    assert collection._verify_endorsements(["org-a", "org-b"])
    assert not collection._verify_endorsements(["org-a", "org-a"])
    assert not collection._verify_endorsements(["org-a", "org-b", "outsider"])
