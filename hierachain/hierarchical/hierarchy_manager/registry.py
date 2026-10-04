"""
Snapshot, migrate and refresh the shared organization/channel registry.

Helpers use the coordinator's existing registry lock and storage adapter.
Channel ledger writes remain separate; this module owns no duplicate state.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from hierachain.hierarchical.channel import Channel
from hierachain.hierarchical.channel.policy import ChannelPolicy
from hierachain.hierarchical.channel.types import ChannelStatus
from hierachain.hierarchical.hierarchy_manager.organization import _build_channel_orgs
from hierachain.hierarchical.multi_org import MultiOrgNetwork, Organization

if TYPE_CHECKING:
    from hierachain.hierarchical.hierarchy_manager.base import HierarchyManager

logger = logging.getLogger(__name__)

def _hierarchy_registry_snapshot(self: HierarchyManager) -> dict[str, Any]:
    for channel in self.channels.values():
        for org_id, channel_org in channel.organizations.items():
            organization = self.organizations.get(org_id)
            if (
                organization is None
                or channel_org.member_registry is not organization.members
            ):
                raise ValueError("Channel organization is not in the manager registry")
    return {
        "_channel_ledger_version": 1,
        "organizations": {
            org_id: {
                "msp": {
                    "ca_cert": org.msp.ca_cert,
                    "tls_ca_cert": org.msp.tls_ca_cert,
                    "admin_certs": org.msp.admin_certs,
                },
                "members": org.members,
            }
            for org_id, org in self.organizations.items()
        },
        "channels": {
            channel_id: {
                "organizations": list(channel.organizations),
                "policy": {
                    "read": channel.policy.read_policy,
                    "write": channel.policy.write_policy,
                    "endorsement": channel.policy.endorsement_policy,
                    "admin": channel.policy.admin_policy,
                    "lifecycle_endorsement": channel.policy.lifecycle_endorsement,
                    "custom_policies": channel.policy.custom_policies,
                },
                "status": channel.status.value,
            }
            for channel_id, channel in self.channels.items()
        },
    }


def _persist_hierarchy_registry(self: HierarchyManager) -> bool:
    with self._registry_lock:
        if self.storage is None:
            return True
        save = getattr(self.storage, "save_hierarchy_registry", None)
        if not callable(save):
            return False
        try:
            state = self._hierarchy_registry_snapshot()
            state["_revision"] = uuid.uuid4().hex
            revision = (self._registry_state or {}).get("_revision")
            previous = self._registry_state or {}
            legacy = previous.get("_channel_ledger_version") != 1
            seeds = {
                channel_id: channel.ledger.snapshot()
                for channel_id, channel in self.channels.items()
                if legacy or channel_id not in previous.get("channels", {})
            }
            if seeds and (
                not callable(getattr(self.storage, "append_channel_record", None))
                or not callable(getattr(self.storage, "load_channel_records", None))
            ):
                raise RuntimeError("Storage does not support durable channel ledgers")
            if save(state, expected_revision=revision, channel_ledgers=seeds) is not True:
                return False
            self._registry_state = deepcopy(state)
            for channel_id in seeds:
                channel = self.channels[channel_id]
                self._bind_channel_ledger(channel)
                # The seed was committed atomically with this metadata revision.
                channel.ledger._sequence = 1
            return True
        except Exception:
            logger.exception("Could not persist hierarchy registry")
            return False


def _restore_hierarchy_registry(self: HierarchyManager) -> None:
    load = getattr(self.storage, "load_hierarchy_registry", None)
    if not callable(load):
        return
    for _ in range(3):
        state = load()
        if state is None:
            if (self._registry_state or {}).get("_revision") is not None:
                raise RuntimeError("Persisted hierarchy registry is missing")
            return
        if state == self._registry_state and state.get("_channel_ledger_version") == 1:
            return
        self._apply_hierarchy_registry(state)
        if state.get("_channel_ledger_version") == 1:
            return
        # Snapshot validation precedes atomic migration of registry and ledgers.
        if self._persist_hierarchy_registry():
            return
    raise RuntimeError("Failed to migrate channel ledger snapshots")


def _apply_hierarchy_registry(self: HierarchyManager, state: dict[str, Any]) -> None:
    """Refresh access metadata; existing ledgers consume their own durable suffix."""
    if (
        not isinstance(state, dict)
        or not isinstance(state.get("organizations"), dict)
        or not isinstance(state.get("channels"), dict)
        or ("_revision" in state and not isinstance(state["_revision"], str))
        or state.get("_channel_ledger_version") not in (None, 1)
    ):
        raise RuntimeError("Invalid hierarchy registry snapshot")

    organizations: dict[str, Organization] = {}
    for org_id, saved in state["organizations"].items():
        if not isinstance(org_id, str) or not isinstance(saved, dict):
            raise RuntimeError("Invalid organization in hierarchy registry")
        msp = saved.get("msp")
        members = saved.get("members")
        if not isinstance(msp, dict) or not isinstance(members, dict):
            raise RuntimeError("Invalid organization in hierarchy registry")
        org = Organization(org_id, msp)
        for member_id, member in members.items():
            identity = member.get("identity") if isinstance(member, dict) else None
            if (
                not isinstance(member_id, str)
                or not isinstance(identity, dict)
                or identity.get("user_id") != member_id
                or identity.get("org_id") != org_id
                or identity.get("role") != member.get("role")
            ):
                raise RuntimeError("Invalid member in hierarchy registry")
        org.members = members
        organizations[org_id] = org

    from hierachain.hierarchical.channel.ledger import ChannelLedger

    legacy = state.get("_channel_ledger_version") != 1
    prepared: dict[str, tuple[list[Any], ChannelPolicy, ChannelStatus, ChannelLedger | None]] = {}
    for channel_id, saved in state["channels"].items():
        if not isinstance(channel_id, str) or not isinstance(saved, dict):
            raise RuntimeError("Invalid channel in hierarchy registry")
        org_ids = saved.get("organizations")
        policy = saved.get("policy")
        if not isinstance(org_ids, list) or not isinstance(policy, dict):
            raise RuntimeError("Invalid channel in hierarchy registry")
        channel_orgs = _build_channel_orgs(org_ids, organizations)
        ledger = None
        if legacy or channel_id not in self.channels:
            ledger = ChannelLedger(self.main_chain.node_identity, self.main_chain.trusted_public_keys, channel_id)
            if legacy:
                ledger.restore(saved.get("ledger", {"blocks": [], "pending_events": []}))
            elif self.storage is not None:
                ledger.bind_storage(self.storage, self._channel_registry_revision)
                ledger.refresh()
        prepared[channel_id] = (
            channel_orgs, ChannelPolicy(policy), ChannelStatus(saved.get("status")), ledger
        )

    # Validate the entire snapshot before updating objects held by callers.
    network = MultiOrgNetwork()
    for org_id, org in organizations.items():
        existing = self.organizations.get(org_id)
        if existing is not None:
            existing.msp = org.msp
            existing.members.clear()
            existing.members.update(org.members)
            organizations[org_id] = existing
            org = existing
        network.add_organization(org)
    channels: dict[str, Channel] = {}
    for channel_id, (channel_orgs, policy, channel_status, ledger) in prepared.items():
        for org in channel_orgs:
            org.member_registry = organizations[org.org_id].members
        channel = self.channels.get(channel_id)
        if channel is None:
            channel = Channel(
                channel_id, channel_orgs, state["channels"][channel_id]["policy"],
                node_identity=self.main_chain.node_identity,
                trusted_public_keys=self.main_chain.trusted_public_keys,
            )
        else:
            channel.organizations = {org.org_id: org for org in channel_orgs}
            channel.policy = policy
            counts = channel.event_statistics["events_by_org"]
            channel.event_statistics["events_by_org"] = {
                org.org_id: counts.get(org.org_id, 0) for org in channel_orgs
            }
        channel.status = channel_status
        if ledger is not None:
            channel.ledger = ledger
            channel.restore_statistics()
        channel._persist_registry = self._persist_hierarchy_registry
        channel._registry_lock = self._registry_lock
        channel._refresh_registry = self._restore_hierarchy_registry
        if not legacy:
            self._bind_channel_ledger(channel)
        channels[channel_id] = channel
    for channel_id, channel in self.channels.items():
        if channel_id not in channels:
            channel.organizations.clear()
            channel.status = ChannelStatus.CLOSED
    self.organizations = organizations
    self.network = network
    self.channels = channels
    self._registry_state = deepcopy(state)


def _mutate_registry(self: HierarchyManager, change: Callable[[], Any], failure_message: str) -> Any:
    with self._registry_lock:
        for _ in range(3):
            self._restore_hierarchy_registry()
            before = deepcopy(self._registry_state or self._hierarchy_registry_snapshot())
            self._registry_mutating = True
            try:
                result = change()
                if self._persist_hierarchy_registry():
                    return result
            except Exception:
                self._apply_hierarchy_registry(before)
                raise
            finally:
                self._registry_mutating = False
            self._apply_hierarchy_registry(before)
        raise RuntimeError(failure_message)

