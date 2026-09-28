"""
ChannelPolicy — access control and endorsement policies for channels.
"""

from typing import Any

from hierachain.hierarchical.channel.types import Organization


class ChannelPolicy:
    def __init__(self, policy_config: dict[str, Any]):
        self.read_policy = policy_config.get("read", "MEMBER")
        self.write_policy = policy_config.get("write", "ADMIN")
        self.endorsement_policy = policy_config.get("endorsement", "MAJORITY")
        self.admin_policy = policy_config.get("admin", "UNANIMOUS")
        self.lifecycle_endorsement = policy_config.get(
            "lifecycle_endorsement", "MAJORITY"
        )

        self.custom_policies = policy_config.get("custom_policies", {})

    def evaluate_read_access(self, organization: Organization) -> bool:
        return self._evaluate_policy(self.read_policy, organization)

    def evaluate_write_access(
        self, organization: Organization, member_role: str | None = None
    ) -> bool:
        if member_role is None:
            return False
        return self._evaluate_policy(self.write_policy, organization, member_role)

    def evaluate_endorsement(
        self,
        endorsements: list[str],
        total_orgs: int,
        eligible_org_ids: set[str] | None = None,
    ) -> bool:
        endorsement_ids = set(endorsements)
        if eligible_org_ids is not None and not endorsement_ids.issubset(
            eligible_org_ids
        ):
            return False

        endorsement_count = len(endorsement_ids)
        if self.endorsement_policy == "MAJORITY":
            return endorsement_count > total_orgs // 2
        elif self.endorsement_policy == "UNANIMOUS":
            return endorsement_count == total_orgs
        elif self.endorsement_policy == "ANY":
            return endorsement_count > 0
        else:
            return endorsement_count >= 1

    def _evaluate_policy(
        self,
        policy: str,
        organization: Organization,
        member_role: str | None = None,
    ) -> bool:
        if policy == "MEMBER":
            return True
        elif policy == "ADMIN":
            return (
                member_role == "admin"
                if member_role is not None
                else organization.has_role("admin")
            )
        elif policy == "OPERATOR":
            if member_role is not None:
                return member_role in {"operator", "admin"}
            return organization.has_role("operator") or organization.has_role("admin")
        elif policy in self.custom_policies:
            custom_policy = self.custom_policies[policy]
            required_roles = custom_policy.get("required_roles", [])
            if member_role is not None:
                return member_role in required_roles
            return any(organization.has_role(role) for role in required_roles)
        else:
            return False
