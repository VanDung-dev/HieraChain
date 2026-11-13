"""Organization, channel and access-control behavior for :class:`HierarchyManager`."""

from copy import deepcopy
from typing import Any

from hierachain.hierarchical.channel import Channel
from hierachain.hierarchical.hierarchy_manager.contracts import HierarchyHost
from hierachain.hierarchical.hierarchy_manager.organization import (
    _build_channel_orgs,
    _build_collection_orgs,
    _init_organization_msp,
    _is_organization_admin,
)
from hierachain.hierarchical.multi_org import MultiOrgNetwork
from hierachain.hierarchical.private_data import PrivateCollection


class OrganizationOperationsMixin(HierarchyHost):
    """Registry-backed organization, channel and chain-access operations."""

    def create_organization(
        self, org_id: str, name: str, admin_users: list[str] | None = None
    ) -> Any:
        def change() -> Any:
            if org_id in self.organizations:
                raise ValueError(f"Organization {org_id} already exists")

            org = _init_organization_msp(org_id, name, admin_users)
            self.organizations[org_id] = org
            if self.network is None:
                self.network = MultiOrgNetwork()
            self.network.add_organization(org)
            return org
        return self._mutate_registry(change, "Failed to persist organization registry")

    def get_organization(self, org_id: str) -> Any:
        with self._registry_lock:
            if not self._registry_mutating:
                self._restore_hierarchy_registry()
            return self.organizations.get(org_id)

    def register_organization_member(
        self, org_id: str, member_id: str, identity: dict[str, Any], role: str,
        *, actor_user_id: str | None = None,
    ) -> str:
        def change() -> str:
            organization = self.get_organization(org_id)
            if organization is None:
                raise ValueError(f"Organization {org_id} not found")
            if actor_user_id is not None and not _is_organization_admin(organization, actor_user_id):
                raise PermissionError("Only a registered organization administrator can add members")
            if member_id in organization.members:
                raise ValueError(f"Member {member_id} already exists")
            if (
                identity.get("user_id") != member_id
                or identity.get("org_id") != org_id
                or identity.get("role") != role
            ):
                raise ValueError("Member identity does not match registry fields")
            organization.register_member(member_id, identity, role)
            return member_id
        return self._mutate_registry(change, "Failed to persist organization member")

    def create_channel(
        self,
        channel_id: str,
        org_ids: list[str],
        policy_config: dict[str, Any] | None = None,
    ) -> Channel:
        def change() -> Channel:
            if channel_id in self.channels:
                raise ValueError(f"Channel {channel_id} already exists")

            organizations = _build_channel_orgs(org_ids, self.organizations)
            policy = policy_config or {
                "read": "MEMBER",
                "write": "ADMIN",
                "endorsement": "MAJORITY",
            }

            channel = Channel(
                channel_id, organizations, policy,
                node_identity=self.main_chain.node_identity,
                trusted_public_keys=self.main_chain.trusted_public_keys,
            )
            self.channels[channel_id] = channel
            channel._persist_registry = self._persist_hierarchy_registry
            channel._registry_lock = self._registry_lock
            channel._refresh_registry = self._restore_hierarchy_registry
            channel.ledger._lock = self._registry_lock
            return channel
        return self._mutate_registry(change, "Failed to persist channel registry")

    def get_channel(self, channel_id: str) -> Channel | None:
        with self._registry_lock:
            if not self._registry_mutating:
                self._restore_hierarchy_registry()
            channel = self.channels.get(channel_id)
            if channel is not None:
                channel._refresh_ledger()
            return channel

    def create_private_collection(
        self,
        name: str,
        org_ids: list[str],
        config: dict[str, Any] | None = None
    ) -> PrivateCollection:
        if name in self.private_collections:
            raise ValueError(f"Private collection {name} already exists")

        organizations = _build_collection_orgs(org_ids, self)
        col_config = config or {
            "block_to_purge": 1000,
            "endorsement_policy": "MAJORITY",
            "min_endorsements": 2,
        }

        private_collection = PrivateCollection(name, organizations, col_config)
        self.private_collections[name] = private_collection
        return private_collection

    def get_private_collection(self, name: str) -> PrivateCollection | None:
        return self.private_collections.get(name)

    def create_private_data_collection(
        self,
        name: str,
        org_ids: list[str],
        config: dict[str, Any] | None = None,
    ) -> PrivateCollection:
        return self.create_private_collection(name, org_ids, config)

    def assign_organization_to_chain(
        self, org_id: str, chain_name: str, *, permissions: list[str] | None = None,
    ) -> bool:
        grants = ["read", "write"] if permissions is None else permissions
        if (
            not isinstance(grants, list) or not grants
            or any(not isinstance(item, str) or item not in {"read", "write", "proofs"} for item in grants)
        ):
            raise ValueError("Chain permissions must contain read, write, or proofs")

        def change() -> bool:
            if org_id not in self.organizations or self.get_sub_chain(chain_name) is None:
                return False
            self.chain_access.setdefault(chain_name, {})[org_id] = sorted(set(grants))
            return True

        return self._mutate_registry(change, "Failed to persist chain access")

    def revoke_organization_from_chain(self, org_id: str, chain_name: str) -> bool:
        def change() -> bool:
            grants = self.chain_access.get(chain_name)
            if grants is None or org_id not in grants:
                return False
            del grants[org_id]
            return True

        return self._mutate_registry(change, "Failed to persist chain access revocation")

    def get_chain_access(self, chain_name: str) -> dict[str, list[str]] | None:
        with self._registry_lock:
            if not self._registry_mutating:
                self._restore_hierarchy_registry()
            grants = self.chain_access.get(chain_name)
            return deepcopy(grants) if grants is not None else None

    def can_access_chain(self, chain_name: str, user_id: str | None, permission: str) -> bool:
        with self._registry_lock:
            if not self._registry_mutating:
                self._restore_hierarchy_registry()
            grants = self.chain_access.get(chain_name)
            if grants is None:
                return True
            if not isinstance(user_id, str) or not user_id:
                return False
            for org_id, permissions in grants.items():
                if permission not in permissions:
                    continue
                organization = self.organizations.get(org_id)
                member = organization.members.get(user_id) if organization is not None else None
                identity = member.get("identity") if isinstance(member, dict) else None
                if (
                    isinstance(member, dict) and isinstance(identity, dict) and identity.get("user_id") == user_id
                    and identity.get("org_id") == org_id
                    and isinstance(member.get("role"), str) and bool(member["role"])
                    and identity.get("role") == member["role"]
                ):
                    return True
            return False
