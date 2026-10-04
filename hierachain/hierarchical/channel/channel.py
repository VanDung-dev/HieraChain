"""
Channel — secure data channel providing complete isolation between organizations.
"""

from __future__ import annotations

import logging
import threading
import time
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, cast

from hierachain.hierarchical.channel.ledger import ChannelLedger
from hierachain.hierarchical.channel.policy import ChannelPolicy
from hierachain.hierarchical.channel.query import (
    _build_query_expression,
    _create_query_filter,
)
from hierachain.hierarchical.channel.types import ChannelStatus, Organization

if TYPE_CHECKING:
    from hierachain.hierarchical.private_data import PrivateCollection
    from hierachain.security.identity_loader import NodeIdentity

logger = logging.getLogger(__name__)


def _registry_operation(method: Callable[..., Any]) -> Callable[..., Any]:
    """Read current access state and serialize local registry operations."""
    @wraps(method)
    def wrapped(self: "Channel", *args: Any, **kwargs: Any) -> Any:
        with self._registry_lock:
            if self._refresh_registry is not None:
                self._refresh_registry()
            return method(self, *args, **kwargs)
    return wrapped


class Channel:
    def __init__(
        self,
        channel_id: str,
        organizations: list[Organization],
        policy_config: dict[str, Any],
        *,
        node_identity: NodeIdentity | None = None,
        trusted_public_keys: dict[str, bytes] | None = None,
    ):
        self.channel_id = channel_id
        self.organizations = {org.org_id: org for org in organizations}
        self.policy = ChannelPolicy(policy_config)
        self.private_collections: dict[str, PrivateCollection] = {}
        self.ordering_service = None
        self.ledger = ChannelLedger(node_identity, trusted_public_keys, channel_id)
        self.status = ChannelStatus.ACTIVE
        self._persist_registry: Callable[[], bool] | None = None
        self._refresh_registry: Callable[[], None] | None = None
        self._registry_lock = threading.RLock()

        self.created_at = time.time()
        self.last_activity = time.time()
        self.configuration = {
            "block_size": policy_config.get("block_size", 500),
            "batch_timeout": policy_config.get("batch_timeout", 2.0),
            "max_message_size": policy_config.get("max_message_size", 1048576),
        }

        self.event_statistics: dict[str, Any] = {
            "total_events": 0,
            "events_by_type": {},
            "events_by_org": {org_id: 0 for org_id in self.organizations.keys()},
        }

    @_registry_operation
    def add_organization(
        self, organization: Organization, endorsements: list[str]
    ) -> bool:
        valid_endorsements = [e for e in endorsements if e in self.organizations]
        if len(valid_endorsements) != len(endorsements):
            return False
        if not self.policy.evaluate_endorsement(
            endorsements,
            len(self.organizations),
            eligible_org_ids=set(self.organizations),
        ):
            return False

        self.organizations[organization.org_id] = organization
        cast(dict[str, int], self.event_statistics["events_by_org"])[organization.org_id] = 0

        def rollback() -> None:
            self.organizations.pop(organization.org_id, None)
            cast(dict[str, int], self.event_statistics["events_by_org"]).pop(
                organization.org_id, None
            )

        if not self._persist_or_rollback(rollback):
            return False

        self._log_channel_event(
            "organization_added",
            {
                "org_id": organization.org_id,
                "org_name": organization.name,
                "endorsed_by": valid_endorsements,
            },
        )

        return True

    @_registry_operation
    def remove_organization(self, org_id: str, endorsements: list[str]) -> bool:
        if org_id not in self.organizations:
            return False

        remaining_orgs = len(self.organizations) - 1
        if any(
            endorsement not in self.organizations or endorsement == org_id
            for endorsement in endorsements
        ):
            return False
        eligible_org_ids = set(self.organizations) - {org_id}
        if not self.policy.evaluate_endorsement(
            endorsements, remaining_orgs, eligible_org_ids=eligible_org_ids
        ):
            return False

        org_info = self.organizations.pop(org_id)
        events_by_org = cast(dict[str, int], self.event_statistics["events_by_org"])
        event_count = events_by_org.pop(org_id, None)

        def rollback() -> None:
            self.organizations[org_id] = org_info
            if event_count is not None:
                events_by_org[org_id] = event_count

        if not self._persist_or_rollback(rollback):
            return False

        for collection in self.private_collections.values():
            collection.remove_organization(org_id)

        self._log_channel_event(
            "organization_removed",
            {"org_id": org_id, "org_name": org_info.name, "endorsed_by": endorsements},
        )

        return True

    @_registry_operation
    def create_private_collection(
        self, name: str, member_org_ids: list[str], config: dict[str, Any]
    ) -> bool:
        members = {}
        for org_id in member_org_ids:
            if org_id not in self.organizations:
                return False
            members[org_id] = self.organizations[org_id]

        from hierachain.hierarchical.private_data import PrivateCollection

        self.private_collections[name] = PrivateCollection(name, members, config)

        self._log_channel_event(
            "private_collection_created",
            {"collection_name": name, "members": member_org_ids, "config": config},
        )

        return True

    @_registry_operation
    def submit_event(
        self,
        event: dict[str, Any],
        submitter_org_id: str,
        *,
        submitter_user_id: str | None = None,
    ) -> bool:
        """Submit as a registered member identified by the verified auth layer.

        Callers must pass ``submitter_user_id`` from authenticated context. The ID
        alone does not grant a role: this method resolves it in the live member
        registry captured from HierarchyManager and checks its registered org/role.
        """
        if self.status != ChannelStatus.ACTIVE or submitter_org_id not in self.organizations:
            return False

        submitter_org = self.organizations[submitter_org_id]
        if not submitter_user_id:
            return False

        member = submitter_org.member_registry.get(submitter_user_id)
        if not isinstance(member, dict):
            return False
        identity = member.get("identity")
        member_role = member.get("role")
        if (
            not isinstance(identity, dict)
            or identity.get("user_id") != submitter_user_id
            or identity.get("org_id") != submitter_org_id
            or identity.get("role") != member_role
            or not isinstance(member_role, str)
            or not member_role
        ):
            return False

        if not self.policy.evaluate_write_access(submitter_org, member_role):
            return False

        enriched_event = {
            **event,
            "channel_id": self.channel_id,
            "submitter_org": submitter_org_id,
            "timestamp": time.time(),
        }

        if not self.ledger.add_event(enriched_event):
            return False

        self.event_statistics["total_events"] += 1
        cast(dict[str, int], self.event_statistics["events_by_org"])[submitter_org_id] += 1

        event_type = event.get("event", "unknown")
        cast(dict[str, int], self.event_statistics["events_by_type"])[event_type] = (
            cast(dict[str, int], self.event_statistics["events_by_type"]).get(event_type, 0) + 1
        )
        self.last_activity = time.time()
        return True

    @_registry_operation
    def query_events(
        self, query_params: dict[str, Any], requester_org_id: str
    ) -> list[dict[str, Any]] | None:
        if requester_org_id not in self.organizations:
            return None
        if not self.policy.evaluate_read_access(self.organizations[requester_org_id]):
            return None

        filter_expr = _build_query_expression(query_params)
        event_filter = _create_query_filter(query_params)

        events = self.ledger.get_events_by_filter(event_filter, filter_expr=filter_expr)

        limit = query_params.get("limit", len(events))
        return events[:limit]

    @_registry_operation
    def finalize_block(self) -> Any | None:
        return self.ledger.finalize_block()

    def restore_statistics(self) -> None:
        """Rebuild submission counters from the durable accepted event history."""
        events = [event for block in self.ledger.blocks for event in block.to_event_list()]
        events.extend(self.ledger.current_block_events)
        statistics: dict[str, Any] = {
            "total_events": 0,
            "events_by_type": {},
            "events_by_org": {org_id: 0 for org_id in self.organizations},
        }
        for event in events:
            org_id = event.get("submitter_org")
            if not org_id:
                continue
            statistics["total_events"] += 1
            event_type = event.get("event", "unknown")
            by_type = statistics["events_by_type"]
            by_type[event_type] = by_type.get(event_type, 0) + 1
            if org_id in statistics["events_by_org"]:
                statistics["events_by_org"][org_id] += 1
        self.event_statistics = statistics

    @_registry_operation
    def get_channel_info(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "status": self.status.value,
            "organizations": list(self.organizations.keys()),
            "private_collections": list(self.private_collections.keys()),
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "ledger_height": self.ledger.height,
            "configuration": self.configuration,
            "statistics": self.event_statistics,
        }

    @_registry_operation
    def get_organization_info(self, org_id: str) -> dict[str, Any] | None:
        if org_id not in self.organizations:
            return None

        org = self.organizations[org_id]
        return {
            "org_id": org.org_id,
            "name": org.name,
            "msp_id": org.msp_id,
            "roles": list(org.roles),
            "events_submitted": cast(dict[str, int], self.event_statistics["events_by_org"]).get(org_id, 0),
        }

    @_registry_operation
    def update_channel_policy(
        self, new_policy_config: dict[str, Any], endorsements: list[str]
    ) -> bool:
        if not self.policy.evaluate_endorsement(
            endorsements,
            len(self.organizations),
            eligible_org_ids=set(self.organizations),
        ):
            return False

        old_policy_config = {
            "read": self.policy.read_policy,
            "write": self.policy.write_policy,
            "endorsement": self.policy.endorsement_policy,
            "admin": self.policy.admin_policy,
            "lifecycle_endorsement": self.policy.lifecycle_endorsement,
            "custom_policies": self.policy.custom_policies,
        }

        old_policy = self.policy
        self.policy = ChannelPolicy(new_policy_config)

        def rollback() -> None:
            self.policy = old_policy

        if not self._persist_or_rollback(rollback):
            return False

        self._log_channel_event(
            "policy_updated",
            {
                "old_policy": old_policy_config,
                "new_policy": new_policy_config,
                "endorsed_by": endorsements,
            },
        )

        return True

    @_registry_operation
    def suspend_channel(self, reason: str, endorsements: list[str]) -> bool:
        if not self.policy.evaluate_endorsement(
            endorsements,
            len(self.organizations),
            eligible_org_ids=set(self.organizations),
        ):
            return False

        old_status = self.status
        self.status = ChannelStatus.SUSPENDED

        def rollback() -> None:
            self.status = old_status

        if not self._persist_or_rollback(rollback):
            return False

        self._log_channel_event(
            "channel_suspended", {"reason": reason, "endorsed_by": endorsements}
        )

        return True

    @_registry_operation
    def resume_channel(self, endorsements: list[str]) -> bool:
        if not self.policy.evaluate_endorsement(
            endorsements,
            len(self.organizations),
            eligible_org_ids=set(self.organizations),
        ):
            return False

        old_status = self.status
        self.status = ChannelStatus.ACTIVE

        def rollback() -> None:
            self.status = old_status

        if not self._persist_or_rollback(rollback):
            return False

        self._log_channel_event("channel_resumed", {"endorsed_by": endorsements})

        return True

    def _log_channel_event(self, event_type: str, details: dict[str, Any]) -> bool:
        channel_event = {
            "event": "channel_management",
            "entity_id": self.channel_id,
            "event_type": event_type,
            "channel_id": self.channel_id,
            "timestamp": time.time(),
            "details": details,
        }
        return self.ledger.add_event(channel_event)

    def _persist_or_rollback(self, rollback: Callable[[], None]) -> bool:
        """Persist a registry mutation, restoring in-memory state if it fails."""
        if self._persist_registry is None:
            return True
        try:
            persisted = self._persist_registry()
        except Exception:
            rollback()
            raise
        if not persisted:
            rollback()
            return False
        return True

    def __str__(self) -> str:
        return (
            f"Channel(id={self.channel_id}, "
            f"orgs={len(self.organizations)}, "
            f"status={self.status.value})"
        )

    def __repr__(self) -> str:
        return (
            f"Channel(channel_id='{self.channel_id}', "
            f"organizations={len(self.organizations)}, "
            f"private_collections={len(self.private_collections)}, "
            f"status='{self.status.value}')"
        )
