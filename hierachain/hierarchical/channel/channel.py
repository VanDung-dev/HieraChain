"""
Channel — secure data channel providing complete isolation between organizations.
"""

import logging
import time
from typing import TYPE_CHECKING, Any, cast

from hierachain.hierarchical.channel.types import ChannelStatus, Organization
from hierachain.hierarchical.channel.policy import ChannelPolicy
from hierachain.hierarchical.channel.ledger import ChannelLedger
from hierachain.hierarchical.channel.query import (
    _build_query_expression,
    _create_query_filter,
)

if TYPE_CHECKING:
    from hierachain.hierarchical.private_data import PrivateCollection

logger = logging.getLogger(__name__)


class Channel:
    def __init__(
        self,
        channel_id: str,
        organizations: list[Organization],
        policy_config: dict[str, Any],
    ):
        self.channel_id = channel_id
        self.organizations = {org.org_id: org for org in organizations}
        self.policy = ChannelPolicy(policy_config)
        self.private_collections: dict[str, PrivateCollection] = {}
        self.ordering_service = None
        self.ledger = ChannelLedger()
        self.status = ChannelStatus.ACTIVE

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

    def add_organization(
        self, organization: Organization, endorsements: list[str]
    ) -> bool:
        if not self.policy.evaluate_endorsement(endorsements, len(self.organizations)):
            return False

        valid_endorsements = [e for e in endorsements if e in self.organizations]
        if len(valid_endorsements) != len(endorsements):
            return False

        self.organizations[organization.org_id] = organization
        cast(dict[str, int], self.event_statistics["events_by_org"])[organization.org_id] = 0

        self._log_channel_event(
            "organization_added",
            {
                "org_id": organization.org_id,
                "org_name": organization.name,
                "endorsed_by": valid_endorsements,
            },
        )

        return True

    def remove_organization(self, org_id: str, endorsements: list[str]) -> bool:
        if org_id not in self.organizations:
            return False

        remaining_orgs = len(self.organizations) - 1
        if not self.policy.evaluate_endorsement(endorsements, remaining_orgs):
            return False

        org_info = self.organizations.pop(org_id)

        for collection in self.private_collections.values():
            collection.remove_organization(org_id)

        self._log_channel_event(
            "organization_removed",
            {"org_id": org_id, "org_name": org_info.name, "endorsed_by": endorsements},
        )

        return True

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

    def submit_event(self, event: dict[str, Any], submitter_org_id: str) -> bool:
        if submitter_org_id not in self.organizations:
            return False

        submitter_org = self.organizations[submitter_org_id]

        if not self.policy.evaluate_write_access(submitter_org):
            return False

        enriched_event = {
            **event,
            "channel_id": self.channel_id,
            "submitter_org": submitter_org_id,
            "timestamp": time.time(),
        }

        self.ledger.add_event(enriched_event)

        self.event_statistics["total_events"] += 1
        cast(dict[str, int], self.event_statistics["events_by_org"])[submitter_org_id] += 1

        event_type = event.get("event", "unknown")
        cast(dict[str, int], self.event_statistics["events_by_type"])[event_type] = (
            cast(dict[str, int], self.event_statistics["events_by_type"]).get(event_type, 0) + 1
        )
        self.last_activity = time.time()
        return True

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

    def finalize_block(self) -> Any | None:
        return self.ledger.finalize_block()

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

    def update_channel_policy(
        self, new_policy_config: dict[str, Any], endorsements: list[str]
    ) -> bool:
        if not self.policy.evaluate_endorsement(endorsements, len(self.organizations)):
            return False

        old_policy_config = {
            "read": self.policy.read_policy,
            "write": self.policy.write_policy,
            "endorsement": self.policy.endorsement_policy,
            "admin": self.policy.admin_policy,
        }

        self.policy = ChannelPolicy(new_policy_config)

        self._log_channel_event(
            "policy_updated",
            {
                "old_policy": old_policy_config,
                "new_policy": new_policy_config,
                "endorsed_by": endorsements,
            },
        )

        return True

    def suspend_channel(self, reason: str, endorsements: list[str]) -> bool:
        if not self.policy.evaluate_endorsement(endorsements, len(self.organizations)):
            return False

        self.status = ChannelStatus.SUSPENDED

        self._log_channel_event(
            "channel_suspended", {"reason": reason, "endorsed_by": endorsements}
        )

        return True

    def resume_channel(self, endorsements: list[str]) -> bool:
        if not self.policy.evaluate_endorsement(endorsements, len(self.organizations)):
            return False

        self.status = ChannelStatus.ACTIVE

        self._log_channel_event("channel_resumed", {"endorsed_by": endorsements})

        return True

    def _log_channel_event(self, event_type: str, details: dict[str, Any]) -> None:
        channel_event = {
            "event": "channel_management",
            "event_type": event_type,
            "channel_id": self.channel_id,
            "timestamp": time.time(),
            "details": details,
        }
        self.ledger.add_event(channel_event)

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
