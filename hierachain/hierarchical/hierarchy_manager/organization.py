"""
Organization and channel helpers for HierarchyManager.
"""

from typing import Any

from hierachain.hierarchical.channel import Organization as ChannelOrganization
from hierachain.hierarchical.multi_org import create_organization


def _is_organization_admin(organization: Any, user_id: str) -> bool:
    """Resolve an administrator from the current, internally consistent member registry."""
    member = organization.members.get(user_id)
    identity = member.get("identity") if isinstance(member, dict) else None
    return (
        isinstance(member, dict)
        and member.get("role") == "admin"
        and isinstance(identity, dict)
        and identity.get("user_id") == user_id
        and identity.get("org_id") == organization.org_id
        and identity.get("role") == "admin"
    )


def _trace_entity_history(
    sub_chains: dict[str, Any], entity_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Trace an entity across all sub-chains."""
    trace_result = {}
    for name, chain in sub_chains.items():
        try:
            history = chain.get_entity_history(entity_id)
            if history:
                trace_result[name] = history
        except AttributeError:
            pass
    return trace_result


def _init_organization_msp(
    org_id: str, name: str, admin_users: list[str] | None
) -> Any:
    """Initialize organization and its network integration."""
    org = create_organization(org_id, name, admin_users or [])
    return org


def _build_channel_orgs(
    org_ids: list[str], registered: dict[str, Any],
) -> list[ChannelOrganization]:
    """Build channel organization objects from IDs."""
    organizations = []
    for org_id in org_ids:
        org = registered.get(org_id)
        if not org:
            raise ValueError(f"Organization {org_id} not found")
        member_registry = getattr(org, "members", None)
        if not isinstance(member_registry, dict):
            raise ValueError(f"Organization {org_id} has no valid member registry")

        organizations.append(
            ChannelOrganization(
                org_id=org_id,
                name=org_id,
                msp_id=f"{org_id}-MSP",
                endpoints=[],
                certificates={},
                roles={"member"},
                member_registry=member_registry,
            )
        )
    return organizations


def _build_collection_orgs(org_ids: list[str], manager: Any) -> dict[str, Any]:
    """Build collection organization mapping."""
    organizations = {}
    for org_id in org_ids:
        org = manager.get_organization(org_id)
        if not org:
            raise ValueError(f"Organization {org_id} not found")

        organizations[org_id] = ChannelOrganization(
            org_id=org_id,
            name=org_id,
            msp_id=f"{org_id}-MSP",
            endpoints=[],
            certificates={},
            roles={"admin", "member"},
        )
    return organizations
