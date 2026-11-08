"""
Multi-Organization Architecture for HieraChain Ledger

This module implements the multi-organization architecture designed for
enterprise applications.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from hierachain.hierarchical.types import (
    ConsensusError,
    NetworkError,
    OrganizationError,
)

# Backward-compat re-exports
OrganizationError = OrganizationError
NetworkError = NetworkError
ConsensusError = ConsensusError


@dataclass
class HierarchicalMSP:
    """Hierarchical Membership Service Provider"""
    org_id: str
    ca_cert: str
    tls_ca_cert: str
    admin_certs: list[str] = field(default_factory=list)

    def validate_identity(self, identity: dict[str, Any]) -> bool:
        """Validate identity credentials"""
        required_fields = ["user_id", "org_id", "role"]

        for req_field in required_fields:
            if req_field not in identity:
                return False

        if identity["org_id"] != self.org_id:
            return False

        return True


class Organization:
    """Enterprise organization with MSP integration"""

    def __init__(self, org_id: str, msp_config: dict[str, Any]) -> None:
        """
        Initialize organization with MSP configuration

        Args:
            org_id: Unique organization identifier
            msp_config: MSP configuration for the organization
        """
        self.org_id = org_id
        self.msp = HierarchicalMSP(
            org_id=org_id,
            ca_cert=msp_config["ca_cert"],
            tls_ca_cert=msp_config["tls_ca_cert"],
            admin_certs=msp_config.get("admin_certs", [])
        )
        self.members: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    def register_member(
        self, member_id: str, identity: dict[str, Any], role: str
    ) -> str:
        """Register a member with organization"""
        with self.lock:
            if not self.msp.validate_identity(identity):
                raise OrganizationError("Invalid identity credentials")

            self.members[member_id] = {
                "identity": identity,
                "role": role,
                "registered_at": time.time()
            }
            return member_id


class MultiOrgNetwork:
    """Multi-organization network manager"""

    def __init__(self):
        self.organizations: dict[str, Organization] = {}
        self.lock = threading.Lock()

    def add_organization(self, organization: Organization):
        """Add organization to the network"""
        with self.lock:
            self.organizations[organization.org_id] = organization

    def remove_organization(self, org_id: str) -> bool:
        """Remove organization from network"""
        with self.lock:
            if org_id not in self.organizations:
                return False

            del self.organizations[org_id]
            return True

    def get_organization(self, org_id: str) -> Organization | None:
        """Get organization by ID"""
        return self.organizations.get(org_id)


def create_organization(
    org_id: str, _name: str, admin_users: list[str] | None = None
) -> Organization:
    """Factory function to create an organization with default MSP config"""
    msp_config = {
        "ca_cert":
        f"-----BEGIN CERTIFICATE-----\n{org_id}_ca_cert\n-----END CERTIFICATE-----",
        "tls_ca_cert":
        f"-----BEGIN CERTIFICATE-----\n{org_id}_tls_ca_cert\n-----END CERTIFICATE-----",
        "admin_certs":
        [f"{admin}_admin_cert" for admin in (admin_users or [f"{org_id}_admin"])]
    }

    org = Organization(org_id, msp_config)

    for admin in (admin_users or [f"{org_id}_admin"]):
        identity = {
            "user_id": admin,
            "org_id": org_id,
            "role": "admin"
        }
        org.register_member(admin, identity, "admin")

    return org
