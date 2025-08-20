"""
Multi-Organization Architecture for Hierarchical Blockchain Framework

This module implements the multi-organization architecture with MSP integration,
inspired by Hyperledger Fabric but simplified for enterprise applications.
Provides support for multiple organizations, affiliation hierarchies, and
channel management across organizational boundaries.
"""

import time
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class OrganizationError(Exception):
    """Exception raised for organization-related errors"""
    pass


class NetworkError(Exception):
    """Exception raised for network-related errors"""
    pass


class ConsensusError(Exception):
    """Exception raised for consensus-related errors"""
    pass


@dataclass
class HierarchicalMSP:
    """Hierarchical Membership Service Provider"""
    org_id: str
    ca_cert: str
    tls_ca_cert: str
    admin_certs: List[str] = field(default_factory=list)
    
    def validate_identity(self, identity: Dict[str, Any]) -> bool:
        """Validate identity credentials"""
        # Simplified validation for enterprise use
        required_fields = ["user_id", "org_id", "role"]
        
        for field in required_fields:
            if field not in identity:
                return False
        
        # Verify organization matches
        if identity["org_id"] != self.org_id:
            return False
        
        # In a real implementation, this would verify certificates
        return True


@dataclass
class OrganizationPolicy:
    """Organization policy configuration"""
    org_id: str
    admin_threshold: int
    voting_policy: str = "majority"  # majority, unanimous, admin_only
    
    def evaluate_proposal(self, votes: Dict[str, bool], voter_roles: Dict[str, str]) -> bool:
        """Evaluate a proposal based on organization policy"""
        admin_votes = {user_id: vote for user_id, vote in votes.items() 
                      if voter_roles.get(user_id) == "admin"}
        
        if self.voting_policy == "admin_only":
            if len(admin_votes) < self.admin_threshold:
                return False
            return all(admin_votes.values())
        
        elif self.voting_policy == "unanimous":
            return all(votes.values())
        
        else:  # majority
            positive_votes = sum(1 for vote in votes.values() if vote)
            return positive_votes > len(votes) / 2


class Organization:
    """Enterprise organization with MSP integration"""
    
    def __init__(self, org_id: str, msp_config: Dict[str, Any]):
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
        self.members: Dict[str, Dict[str, Any]] = {}
        self.channels: Dict[str, Any] = {}
        self.affiliations: Dict[str, Any] = {}
        self.lock = threading.Lock()
    
    def register_member(self, member_id: str, identity: Dict[str, Any], role: str) -> str:
        """Register a member with organization"""
        with self.lock:
            if not self.msp.validate_identity(identity):
                raise OrganizationError("Invalid identity credentials")
            
            self.members[member_id] = {
                "identity": identity,
                "role": role,
                "affiliation": None,
                "registered_at": time.time()
            }
            return member_id
    
    def create_affiliation(self, affiliation_path: str) -> str:
        """Create organizational affiliation hierarchy"""
        with self.lock:
            parts = affiliation_path.split('.')
            current = self.affiliations
            
            for part in parts:
                if part not in current:
                    current[part] = {
                        "members": [],
                        "sub_affiliations": {},
                        "created_at": time.time()
                    }
                current = current[part]["sub_affiliations"]
            
            return affiliation_path
    
    def assign_affiliation(self, member_id: str, affiliation_path: str):
        """Assign member to an affiliation"""
        with self.lock:
            if member_id not in self.members:
                raise OrganizationError("Member not found")
            
            # Validate affiliation path exists
            parts = affiliation_path.split('.')
            current = self.affiliations
            for part in parts:
                if part not in current:
                    raise OrganizationError(f"Affiliation {affiliation_path} does not exist")
                current = current[part]["sub_affiliations"]
            
            # Remove from old affiliation if any
            old_affiliation = self.members[member_id]["affiliation"]
            if old_affiliation:
                self._remove_from_affiliation(member_id, old_affiliation)
            
            # Add to new affiliation
            self.members[member_id]["affiliation"] = affiliation_path
            current = self.affiliations
            for part in parts:
                current[part]["members"].append(member_id)
                current = current[part]["sub_affiliations"]
    
    def _remove_from_affiliation(self, member_id: str, affiliation_path: str):
        """Remove member from affiliation"""
        parts = affiliation_path.split('.')
        current = self.affiliations
        
        for part in parts:
            if part in current and member_id in current[part]["members"]:
                current[part]["members"].remove(member_id)
            if part in current:
                current = current[part]["sub_affiliations"]
    
    def get_admins(self) -> List[str]:
        """Get list of admin members"""
        return [member_id for member_id, info in self.members.items() 
                if info["role"] == "admin"]
    
    def get_org_policy(self) -> OrganizationPolicy:
        """Get organization policy configuration"""
        admin_count = len(self.get_admins())
        return OrganizationPolicy(
            org_id=self.org_id,
            admin_threshold=max(1, admin_count // 2 + 1)
        )
    
    def get_members_by_role(self, role: str) -> List[str]:
        """Get members by role"""
        return [member_id for member_id, info in self.members.items() 
                if info["role"] == role]
    
    def get_affiliation_members(self, affiliation_path: str) -> List[str]:
        """Get members in an affiliation"""
        parts = affiliation_path.split('.')
        current = self.affiliations
        
        for part in parts:
            if part not in current:
                return []
            current = current[part]["sub_affiliations"]
        
        # Get members from the parent level
        parts = affiliation_path.split('.')
        current = self.affiliations
        for part in parts[:-1]:
            current = current[part]["sub_affiliations"]
        
        return current.get(parts[-1], {}).get("members", [])


class ApplicationChannel:
    """Application channel for multi-organization collaboration"""
    
    def __init__(self, channel_id: str, organizations: List[Organization], 
                 config: Dict[str, Any], system_channel=None):
        """
        Initialize application channel
        
        Args:
            channel_id: Unique channel identifier
            organizations: List of participating organizations
            config: Channel configuration
            system_channel: Reference to system channel
        """
        self.channel_id = channel_id
        self.organizations = {org.org_id: org for org in organizations}
        self.config = config
        self.system_channel = system_channel
        self.created_at = time.time()
        self.blocks: List[Any] = []
        self.lock = threading.Lock()
    
    def add_organization(self, organization: Organization) -> bool:
        """Add organization to channel"""
        with self.lock:
            if organization.org_id in self.organizations:
                return False
            
            self.organizations[organization.org_id] = organization
            return True
    
    def remove_organization(self, org_id: str) -> bool:
        """Remove organization from channel"""
        with self.lock:
            if org_id not in self.organizations:
                return False
            
            del self.organizations[org_id]
            return True
    
    def validate_member_access(self, member_id: str, org_id: str) -> bool:
        """Validate if member has access to this channel"""
        if org_id not in self.organizations:
            return False
        
        org = self.organizations[org_id]
        return member_id in org.members
    
    def get_channel_policy(self) -> Dict[str, Any]:
        """Get channel policy configuration"""
        return {
            "channel_id": self.channel_id,
            "participating_orgs": list(self.organizations.keys()),
            "consensus_policy": self.config.get("consensus_policy", "majority"),
            "endorsement_policy": self.config.get("endorsement_policy", "any_org")
        }


class MultiOrgNetwork:
    """Multi-organization network manager"""
    
    def __init__(self):
        self.organizations: Dict[str, Organization] = {}
        self.system_channel: Optional[ApplicationChannel] = None
        self.application_channels: Dict[str, ApplicationChannel] = {}
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
            
            # Remove from all channels
            for channel in self.application_channels.values():
                channel.remove_organization(org_id)
            
            del self.organizations[org_id]
            return True
    
    def create_system_channel(self, config: Dict[str, Any]) -> ApplicationChannel:
        """Create system channel for network management"""
        with self.lock:
            if self.system_channel:
                raise NetworkError("System channel already exists")
            
            # System channel includes all organizations
            all_orgs = list(self.organizations.values())
            self.system_channel = ApplicationChannel(
                channel_id="system-channel",
                organizations=all_orgs,
                config=config
            )
            return self.system_channel
    
    def create_application_channel(self, channel_id: str, participating_orgs: List[str], 
                                 config: Dict[str, Any]) -> ApplicationChannel:
        """
        Create application channel with participating organizations
        
        Args:
            channel_id: Unique channel identifier
            participating_orgs: List of organization IDs
            config: Channel configuration
        """
        with self.lock:
            # Validate organizations exist
            for org_id in participating_orgs:
                if org_id not in self.organizations:
                    raise NetworkError(f"Organization {org_id} not found")
            
            if channel_id in self.application_channels:
                raise NetworkError(f"Channel {channel_id} already exists")
            
            # Create channel
            orgs = [self.organizations[org_id] for org_id in participating_orgs]
            channel = ApplicationChannel(
                channel_id=channel_id,
                organizations=orgs,
                config=config,
                system_channel=self.system_channel
            )
            
            self.application_channels[channel_id] = channel
            return channel
    
    def get_channel(self, channel_id: str) -> Optional[ApplicationChannel]:
        """Get channel by ID"""
        if channel_id == "system-channel":
            return self.system_channel
        return self.application_channels.get(channel_id)
    
    def get_organization(self, org_id: str) -> Optional[Organization]:
        """Get organization by ID"""
        return self.organizations.get(org_id)
    
    def get_network_status(self) -> Dict[str, Any]:
        """Get network status information"""
        return {
            "organizations": len(self.organizations),
            "application_channels": len(self.application_channels),
            "system_channel_exists": self.system_channel is not None,
            "total_members": sum(len(org.members) for org in self.organizations.values())
        }
    
    def validate_cross_org_operation(self, operation: Dict[str, Any], 
                                     channel_id: str) -> bool:
        """Validate cross-organizational operation"""
        channel = self.get_channel(channel_id)
        if not channel:
            return False
        
        # Validate all required organizations are part of the channel
        required_orgs = operation.get("required_orgs", [])
        for org_id in required_orgs:
            if org_id not in channel.organizations:
                return False
        
        # Validate endorsement policy
        endorsement_policy = channel.config.get("endorsement_policy", "any_org")
        if endorsement_policy == "all_orgs":
            return len(required_orgs) == len(channel.organizations)
        elif endorsement_policy == "majority_orgs":
            return len(required_orgs) > len(channel.organizations) / 2
        
        # Default: any_org
        return len(required_orgs) > 0


# Factory functions for easy setup
def create_organization(org_id: str, name: str, admin_users: List[str] = None) -> Organization:
    """Factory function to create an organization with default MSP config"""
    msp_config = {
        "ca_cert": f"-----BEGIN CERTIFICATE-----\n{org_id}_ca_cert\n-----END CERTIFICATE-----",
        "tls_ca_cert": f"-----BEGIN CERTIFICATE-----\n{org_id}_tls_ca_cert\n-----END CERTIFICATE-----",
        "admin_certs": [f"{admin}_admin_cert" for admin in (admin_users or [f"{org_id}_admin"])]
    }
    
    org = Organization(org_id, msp_config)
    
    # Register admin users
    for admin in (admin_users or [f"{org_id}_admin"]):
        identity = {
            "user_id": admin,
            "org_id": org_id,
            "role": "admin"
        }
        org.register_member(admin, identity, "admin")
    
    return org


def create_multi_org_network(organizations: List[Dict[str, Any]]) -> MultiOrgNetwork:
    """Factory function to create a multi-organization network"""
    network = MultiOrgNetwork()
    
    # Create and add organizations
    for org_config in organizations:
        org = create_organization(
            org_config["org_id"],
            org_config["name"],
            org_config.get("admin_users")
        )
        network.add_organization(org)
    
    # Create system channel
    system_config = {
        "consensus_policy": "majority",
        "admin_policy": "majority"
    }
    network.create_system_channel(system_config)
    
    return network