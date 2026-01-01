"""
Channel-based Data Isolation for HieraChain Framework.

This module implements secure data channels that provide complete isolation between 
organizations in enterprise blockchain applications. Each channel operates as a 
completely isolated data space with its own governance policies and access controls.
"""

import time
import logging
import pyarrow as pa
import pyarrow.compute as pc
from typing import Any, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

from hierachain.core.block import Block
from hierachain.core import schemas

if TYPE_CHECKING:
    from hierachain.hierarchical.private_data import PrivateCollection

logger = logging.getLogger(__name__)


class ChannelStatus(Enum):
    """Channel status enumeration"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    MAINTENANCE = "maintenance"


@dataclass
class Organization:
    """Organization participating in a channel"""
    org_id: str
    name: str
    msp_id: str
    endpoints: list[str]
    certificates: dict[str, Any]
    roles: set[str]
    
    def has_role(self, role: str) -> bool:
        """Check if organization has a specific role"""
        return role in self.roles


class ChannelPolicy:
    """Channel access and endorsement policies"""
    
    def __init__(self, policy_config: dict[str, Any]):
        """
        Initialize channel policy.
        
        Args:
            policy_config: Policy configuration dictionary
        """
        self.read_policy = policy_config.get("read", "MEMBER")
        self.write_policy = policy_config.get("write", "ADMIN")
        self.endorsement_policy = policy_config.get("endorsement", "MAJORITY")
        self.admin_policy = policy_config.get("admin", "UNANIMOUS")
        self.lifecycle_endorsement = policy_config.get("lifecycle_endorsement", "MAJORITY")
        
        # Custom policy expressions
        self.custom_policies = policy_config.get("custom_policies", {})
        
    def evaluate_read_access(self, organization: Organization) -> bool:
        """Evaluate if organization has read access"""
        return self._evaluate_policy(self.read_policy, organization)
    
    def evaluate_write_access(self, organization: Organization) -> bool:
        """Evaluate if organization has write access"""
        return self._evaluate_policy(self.write_policy, organization)
    
    def evaluate_endorsement(self, endorsements: list[str], total_orgs: int) -> bool:
        """Evaluate if endorsements meet the policy requirements"""
        if self.endorsement_policy == "MAJORITY":
            return len(endorsements) > total_orgs // 2
        elif self.endorsement_policy == "UNANIMOUS":
            return len(endorsements) == total_orgs
        elif self.endorsement_policy == "ANY":
            return len(endorsements) > 0
        else:
            # Custom endorsement logic could be implemented here
            return len(endorsements) >= 1
    
    def _evaluate_policy(self, policy: str, organization: Organization) -> bool:
        """Evaluate a policy expression against an organization"""
        if policy == "MEMBER":
            return True  # Any member organization
        elif policy == "ADMIN":
            return organization.has_role("admin")
        elif policy == "OPERATOR":
            return organization.has_role("operator") or organization.has_role("admin")
        elif policy in self.custom_policies:
            # Evaluate custom policy (simplified implementation)
            custom_policy = self.custom_policies[policy]
            required_roles = custom_policy.get("required_roles", [])
            return any(organization.has_role(role) for role in required_roles)
        else:
            return False


class ChannelLedger:
    """Channel-specific ledger for storing channel events"""
    
    def __init__(self):
        self.blocks: list[Block] = []
        self.current_block_events: list[dict[str, Any]] = []
        self.height = 0
        self.last_block_hash = "0"
        
    def add_event(self, event: dict[str, Any]) -> None:
        """Add event to current block"""
        event["timestamp"] = event.get("timestamp", time.time())
        event["channel_event"] = True
        self.current_block_events.append(event)
    
    def finalize_block(self) -> Block | None:
        """Finalize current block and add to ledger"""
        if not self.current_block_events:
            return None

        # Prepare arrays for Arrow Table
        schema_names = schemas.get_event_schema().names
        arrays = {name: [] for name in schema_names}

        for event in self.current_block_events:
            for name in schema_names:
                val = event.get(name)
                # Handle details field which might be dict
                if name == "details":
                    if isinstance(val, dict):
                         # Convert values to strings for Map<String, String> schema
                        val = {str(k): str(v) for k, v in val.items()}
                    elif val is None:
                        val = {}
                arrays[name].append(val)

        table = pa.Table.from_pydict(arrays, schema=schemas.get_event_schema())

        # Create Block
        block = Block(
            index=self.height,
            events=table,
            timestamp=time.time(),
            previous_hash=self.last_block_hash
        )
        block.calculate_hash() # Ensure hash is computed

        self.blocks.append(block)
        self.height += 1
        self.last_block_hash = block.hash
        self.current_block_events.clear()
        
        return block
    
    def get_events_by_filter(self, filter_func, filter_expr: Any | None = None) -> list[dict[str, Any]]:
        """
        Get events matching filter criteria.
        
        Args:
            filter_func: Fallback python filter function
            filter_expr: PyArrow compute expression for zero-copy filtering
        """
        events = []
        for block in self.blocks:
            # Use Arrow Compute Filter if expression is provided
            if filter_expr is not None:
                try:
                    arrow_table = block.events
                    filtered_table = arrow_table.filter(filter_expr)
                    filtered_events = Block._table_to_list_of_dicts(filtered_table)
                    events.extend([e for e in filtered_events if filter_func(e)])
                    continue
                except Exception as e:
                    logger.error(f"Failed to load channel: {e}")
                    pass
            
            # LEGACY / FALLBACK PATH
            block_events = []
            if hasattr(block, "to_event_list"):
                block_events = block.to_event_list()
            else:
                block_events = Block._table_to_list_of_dicts(block.events)
                
            events.extend([event for event in block_events if filter_func(event)])
        return events


class Channel:
    """
    Secure data channel providing complete isolation between organizations.
    
    Each channel operates as an isolated data space with its own governance policies,
    access controls, and private data collections for secure enterprise collaboration.
    """
    
    def __init__(self, channel_id: str, organizations: list[Organization], policy_config: dict[str, Any]):
        """
        Initialize a new channel.
        
        Args:
            channel_id: Unique channel identifier
            organizations: List of participating organizations
            policy_config: Channel access and endorsement policies
        """
        self.channel_id = channel_id
        self.organizations = {org.org_id: org for org in organizations}
        self.policy = ChannelPolicy(policy_config)
        self.private_collections: dict[str, PrivateCollection] = {}
        self.ordering_service = None
        self.ledger = ChannelLedger()
        self.status = ChannelStatus.ACTIVE
        
        # Channel metadata
        self.created_at = time.time()
        self.last_activity = time.time()
        self.configuration = {
            "block_size": policy_config.get("block_size", 500),
            "batch_timeout": policy_config.get("batch_timeout", 2.0),
            "max_message_size": policy_config.get("max_message_size", 1048576)  # 1MB
        }
        
        # Event tracking
        self.event_statistics = {
            "total_events": 0,
            "events_by_type": {},
            "events_by_org": {org_id: 0 for org_id in self.organizations.keys()}
        }
        
    def add_organization(self, organization: Organization, endorsements: list[str]) -> bool:
        """
        Add a new organization to the channel.
        
        Args:
            organization: Organization to add
            endorsements: List of endorsing organization IDs
            
        Returns:
            True if successfully added
        """
        # Check if endorsements meet policy requirements
        if not self.policy.evaluate_endorsement(endorsements, len(self.organizations)):
            return False
            
        # Verify endorsements are from current channel members
        valid_endorsements = [e for e in endorsements if e in self.organizations]
        if len(valid_endorsements) != len(endorsements):
            return False
            
        # Add organization
        self.organizations[organization.org_id] = organization
        self.event_statistics["events_by_org"][organization.org_id] = 0
        
        # Log channel modification event
        self._log_channel_event("organization_added", {
            "org_id": organization.org_id,
            "org_name": organization.name,
            "endorsed_by": valid_endorsements
        })
        
        return True
    
    def remove_organization(self, org_id: str, endorsements: list[str]) -> bool:
        """
        Remove an organization from the channel.
        
        Args:
            org_id: Organization ID to remove
            endorsements: List of endorsing organization IDs
            
        Returns:
            True if successfully removed
        """
        if org_id not in self.organizations:
            return False
            
        # Check endorsements (excluding the organization being removed)
        remaining_orgs = len(self.organizations) - 1
        if not self.policy.evaluate_endorsement(endorsements, remaining_orgs):
            return False
            
        # Remove organization
        org_info = self.organizations.pop(org_id)
        
        # Remove from private collections
        for collection in self.private_collections.values():
            collection.remove_organization(org_id)
        
        # Log channel modification event
        self._log_channel_event("organization_removed", {
            "org_id": org_id,
            "org_name": org_info.name,
            "endorsed_by": endorsements
        })
        
        return True
    
    def create_private_collection(self, name: str, member_org_ids: list[str], 
                                config: dict[str, Any]) -> bool:
        """
        Create a private data collection within the channel.
        
        Args:
            name: Collection name
            member_org_ids: Organization IDs that are members of this collection
            config: Collection configuration
            
        Returns:
            True if successfully created
        """
        # Validate all member organizations exist in channel
        members = {}
        for org_id in member_org_ids:
            if org_id not in self.organizations:
                return False
            members[org_id] = self.organizations[org_id]
        
        # Import PrivateCollection here to avoid circular imports
        from hierachain.hierarchical.private_data import PrivateCollection
        
        # Create private collection
        self.private_collections[name] = PrivateCollection(name, members, config)
        
        # Log private collection creation
        self._log_channel_event("private_collection_created", {
            "collection_name": name,
            "members": member_org_ids,
            "config": config
        })
        
        return True
    
    def submit_event(self, event: dict[str, Any], submitter_org_id: str) -> bool:
        """
        Submit an event to the channel.
        
        Args:
            event: Event to submit
            submitter_org_id: Organization ID of the submitter
            
        Returns:
            True if event was accepted
        """
        # Validate submitter organization
        if submitter_org_id not in self.organizations:
            return False
            
        submitter_org = self.organizations[submitter_org_id]
        
        # Check write access
        if not self.policy.evaluate_write_access(submitter_org):
            return False
        
        # Add channel and organization metadata
        enriched_event = {
            **event,
            "channel_id": self.channel_id,
            "submitter_org": submitter_org_id,
            "timestamp": time.time()
        }
        
        # Add to ledger
        self.ledger.add_event(enriched_event)
        
        # Update statistics
        self.event_statistics["total_events"] += 1
        self.event_statistics["events_by_org"][submitter_org_id] += 1
        
        event_type = event.get("event", "unknown")
        self.event_statistics["events_by_type"][event_type] = (
            self.event_statistics["events_by_type"].get(event_type, 0) + 1
        )
        
        self.last_activity = time.time()
        
        return True
    
    def query_events(self, query_params: dict[str, Any], requester_org_id: str) -> list[dict[str, Any]] | None:
        """
        Query events from the channel.
        
        Args:
            query_params: Query parameters (filters, limits, etc.)
            requester_org_id: Organization ID making the request
            
        Returns:
            List of matching events if authorized, None otherwise
        """
        # Validate requester organization
        if requester_org_id not in self.organizations:
            return None
            
        requester_org = self.organizations[requester_org_id]
        
        # Check read access
        if not self.policy.evaluate_read_access(requester_org):
            return None
        
        # Build Arrow Compute Expression for high-performance filtering
        filter_expr = None
        
        try:
            filters = []
            if "event_type" in query_params:
                filters.append(pc.field("event") == query_params["event_type"])
            
            if "entity_id" in query_params:
                filters.append(pc.field("entity_id") == query_params["entity_id"])
            
            if "start_time" in query_params:
                filters.append(pc.field("timestamp") >= query_params["start_time"])
                
            if "end_time" in query_params:
                filters.append(pc.field("timestamp") <= query_params["end_time"])

            if filters:
                filter_expr = filters[0]
                for f in filters[1:]:
                    filter_expr = filter_expr & f
                    
        except Exception:
            filter_expr = None

        # Python Filter (Fallback for complex logic like Map lookups if Arrow fails)
        def event_filter(event):
            for key, value in query_params.items():
                if key == "event_type":
                    if event.get("event") != value: return False
                elif key == "entity_id":
                    if event.get("entity_id") != value: return False
                elif key == "start_time":
                    if event.get("timestamp", 0) < value: return False
                elif key == "end_time":
                    if event.get("timestamp", 0) > value: return False
                elif key == "limit":
                    continue

                elif key.startswith("details."):
                    detail_key = key.split(".", 1)[1]
                    details = event.get("details", {})
                    
                    actual_val = details.get(detail_key)
                    
                    if isinstance(value, dict):
                        # Operator definitions
                        if "gt" in value and not (float(actual_val) > value["gt"] if actual_val is not None else False): return False
                        if "lt" in value and not (float(actual_val) < value["lt"] if actual_val is not None else False): return False
                        if "gte" in value and not (float(actual_val) >= value["gte"] if actual_val is not None else False): return False
                        if "lte" in value and not (float(actual_val) <= value["lte"] if actual_val is not None else False): return False
                    else:
                        # Exact match
                        if actual_val != str(value): return False
            
            return True
        
        # Get matching events
        events = self.ledger.get_events_by_filter(event_filter, filter_expr=filter_expr)
        
        # Apply limit if specified
        limit = query_params.get("limit", len(events))
        return events[:limit]
    
    def finalize_block(self) -> Any | None:
        """Finalize current block in the channel ledger"""
        return self.ledger.finalize_block()
    
    def get_channel_info(self) -> dict[str, Any]:
        """Get comprehensive channel information"""
        return {
            "channel_id": self.channel_id,
            "status": self.status.value,
            "organizations": list(self.organizations.keys()),
            "private_collections": list(self.private_collections.keys()),
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "ledger_height": self.ledger.height,
            "configuration": self.configuration,
            "statistics": self.event_statistics
        }
    
    def get_organization_info(self, org_id: str) -> dict[str, Any] | None:
        """Get information about a specific organization"""
        if org_id not in self.organizations:
            return None
            
        org = self.organizations[org_id]
        return {
            "org_id": org.org_id,
            "name": org.name,
            "msp_id": org.msp_id,
            "roles": list(org.roles),
            "events_submitted": self.event_statistics["events_by_org"].get(org_id, 0)
        }
    
    def update_channel_policy(self, new_policy_config: dict[str, Any], 
                            endorsements: list[str]) -> bool:
        """
        Update channel governance policy.
        
        Args:
            new_policy_config: New policy configuration
            endorsements: List of endorsing organization IDs
            
        Returns:
            True if successfully updated
        """
        # Check if endorsements meet current admin policy requirements
        if not self.policy.evaluate_endorsement(endorsements, len(self.organizations)):
            return False
        
        # Update policy
        old_policy_config = {
            "read": self.policy.read_policy,
            "write": self.policy.write_policy,
            "endorsement": self.policy.endorsement_policy,
            "admin": self.policy.admin_policy
        }
        
        self.policy = ChannelPolicy(new_policy_config)
        
        # Log policy change
        self._log_channel_event("policy_updated", {
            "old_policy": old_policy_config,
            "new_policy": new_policy_config,
            "endorsed_by": endorsements
        })
        
        return True
    
    def suspend_channel(self, reason: str, endorsements: list[str]) -> bool:
        """Suspend channel operations"""
        if not self.policy.evaluate_endorsement(endorsements, len(self.organizations)):
            return False
            
        self.status = ChannelStatus.SUSPENDED
        
        self._log_channel_event("channel_suspended", {
            "reason": reason,
            "endorsed_by": endorsements
        })
        
        return True
    
    def resume_channel(self, endorsements: list[str]) -> bool:
        """Resume channel operations"""
        if not self.policy.evaluate_endorsement(endorsements, len(self.organizations)):
            return False
            
        self.status = ChannelStatus.ACTIVE
        
        self._log_channel_event("channel_resumed", {
            "endorsed_by": endorsements
        })
        
        return True
    
    def _log_channel_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Log a channel management event"""
        channel_event = {
            "event": "channel_management",
            "event_type": event_type,
            "channel_id": self.channel_id,
            "timestamp": time.time(),
            "details": details
        }
        
        self.ledger.add_event(channel_event)
    
    def __str__(self) -> str:
        """String representation of channel"""
        return f"Channel(id={self.channel_id}, orgs={len(self.organizations)}, status={self.status.value})"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return (f"Channel(channel_id='{self.channel_id}', "
                f"organizations={len(self.organizations)}, "
                f"private_collections={len(self.private_collections)}, "
                f"status='{self.status.value}')")