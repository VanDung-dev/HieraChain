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

    def evaluate_write_access(self, organization: Organization) -> bool:
        return self._evaluate_policy(self.write_policy, organization)

    def evaluate_endorsement(self, endorsements: list[str], total_orgs: int) -> bool:
        if self.endorsement_policy == "MAJORITY":
            return len(endorsements) > total_orgs // 2
        elif self.endorsement_policy == "UNANIMOUS":
            return len(endorsements) == total_orgs
        elif self.endorsement_policy == "ANY":
            return len(endorsements) > 0
        else:
            return len(endorsements) >= 1

    def _evaluate_policy(self, policy: str, organization: Organization) -> bool:
        if policy == "MEMBER":
            return True
        elif policy == "ADMIN":
            return organization.has_role("admin")
        elif policy == "OPERATOR":
            return organization.has_role("operator") or organization.has_role("admin")
        elif policy in self.custom_policies:
            custom_policy = self.custom_policies[policy]
            required_roles = custom_policy.get("required_roles", [])
            return any(organization.has_role(role) for role in required_roles)
        else:
            return False
