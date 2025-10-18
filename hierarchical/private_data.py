"""
Private Data Collections for Hierarchical Blockchain Framework.

This module implements private data collections that allow organizations to share 
sensitive data within a channel while keeping it hidden from other channel participants.
This significantly enhances data privacy in enterprise collaborations.
"""

import time
import hashlib
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from cryptography.fernet import Fernet, InvalidToken


class CollectionStatus(Enum):
    """Private collection status enumeration"""
    ACTIVE = "active"
    DISABLED = "disabled"
    PURGING = "purging"


class EndorsementPolicy(Enum):
    """Endorsement policy types for private collections"""
    MAJORITY = "MAJORITY"
    UNANIMOUS = "UNANIMOUS"
    ANY = "ANY"
    SPECIFIC_COUNT = "SPECIFIC_COUNT"


@dataclass
class PrivateDataEntry:
    """Private data entry with metadata"""
    key: str
    encrypted_value: bytes
    metadata: Dict[str, Any]
    timestamp: float
    block_height: int
    endorsements: List[str]
    hash_value: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "key": self.key,
            "encrypted_value": self.encrypted_value.hex(),
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "block_height": self.block_height,
            "endorsements": self.endorsements,
            "hash_value": self.hash_value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PrivateDataEntry':
        """Create from dictionary"""
        return cls(
            key=data["key"],
            encrypted_value=bytes.fromhex(data["encrypted_value"]),
            metadata=data["metadata"],
            timestamp=data["timestamp"],
            block_height=data["block_height"],
            endorsements=data["endorsements"],
            hash_value=data["hash_value"]
        )


class PrivateCollection:
    """
    Private data collection for sensitive information sharing.
    
    Allows organizations within a channel to share sensitive data while keeping 
    it hidden from other channel participants. Supports encryption, endorsement 
    policies, and automatic data purging.
    """
    
    def __init__(self, name: str, organizations: Dict[str, Any], config: Dict[str, Any]):
        """
        Initialize private data collection.
        
        Args:
            name: Collection name
            organizations: Organizations participating in this collection  
            config: Collection configuration including block-to-purge and endorsements
        """
        self.name = name
        self.organizations = organizations  # Dict[org_id, Organization]
        self.config = config
        self.status = CollectionStatus.ACTIVE
        
        # Private data store
        self.data_store: Dict[str, PrivateDataEntry] = {}
        
        # Collection metadata
        self.created_at = time.time()
        self.last_activity = time.time()
        self.current_block_height = 0
        
        # Configuration settings
        self.metadata = {
            "block_to_purge": config.get("block_to_purge", 1000),
            "endorsement_policy": EndorsementPolicy(config.get("endorsement_policy", "MAJORITY")),
            "min_endorsements": config.get("min_endorsements", 2),
            "max_peer_count": config.get("max_peer_count", len(organizations)),
            "require_peer_count": config.get("require_peer_count", 1),
            "member_only_read": config.get("member_only_read", True),
            "member_only_write": config.get("member_only_write", True)
        }
        
        # Generate encryption key for this collection
        self.encryption_key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Statistics
        self.statistics = {
            "total_entries": 0,
            "entries_by_org": {org_id: 0 for org_id in organizations.keys()},
            "purged_entries": 0,
            "failed_endorsements": 0
        }
        
    def add_data(self, key: str, value: Any, event_metadata: Dict[str, Any], 
                submitter_org_id: str) -> bool:
        """
        Add private data with proper endorsement verification.
        
        Args:
            key: Data key identifier
            value: Data value to store privately
            event_metadata: Event metadata including endorsements
            submitter_org_id: Organization submitting the data
            
        Returns:
            True if data was successfully added
        """
        try:
            # Verify submitter is a collection member
            if submitter_org_id not in self.organizations:
                return False
            
            # Verify endorsements
            endorsements = event_metadata.get("endorsements", [])
            if not self._verify_endorsements(endorsements):
                self.statistics["failed_endorsements"] += 1
                return False
            
            # Encrypt the data
            value_json = json.dumps(value, sort_keys=True)
            encrypted_value = self.cipher_suite.encrypt(value_json.encode())
            
            # Calculate hash for integrity
            hash_value = hashlib.sha256(value_json.encode()).hexdigest()
            
            # Create private data entry
            entry = PrivateDataEntry(
                key=key,
                encrypted_value=encrypted_value,
                metadata={
                    **event_metadata,
                    "submitter_org": submitter_org_id,
                    "collection_name": self.name
                },
                timestamp=time.time(),
                block_height=self.current_block_height,
                endorsements=endorsements,
                hash_value=hash_value
            )
            
            # Store the data
            self.data_store[key] = entry
            
            # Update statistics
            self.statistics["total_entries"] += 1
            self.statistics["entries_by_org"][submitter_org_id] += 1
            self.last_activity = time.time()
            
            return True
            
        except Exception as e:
            # Log error but don't expose details
            print(f"Failed to add private data: {str(e)}")
            return False
    
    def get_data(self, key: str, requester_org_id: str) -> Optional[Any]:
        """
        Retrieve private data if requester has access.
        
        Args:
            key: Data key to retrieve
            requester_org_id: Organization requesting the data
            
        Returns:
            Decrypted data if authorized, None otherwise
        """
        # Verify requester is a collection member
        if requester_org_id not in self.organizations:
            return None
            
        # Check if data exists
        if key not in self.data_store:
            return None
            
        entry = self.data_store[key]
        
        # Check if data should be purged
        if self._should_purge_entry(entry):
            self._purge_entry(key)
            return None
        
        try:
            # Decrypt and return data
            decrypted_bytes = self.cipher_suite.decrypt(entry.encrypted_value)
            decrypted_json = decrypted_bytes.decode()
            return json.loads(decrypted_json)
            
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError):
            return None
    
    def get_data_hash(self, key: str, requester_org_id: str) -> Optional[str]:
        """
        Get hash of private data without revealing the data itself.
        
        Args:
            key: Data key
            requester_org_id: Organization requesting the hash
            
        Returns:
            Hash value if authorized, None otherwise
        """
        # Even non-members can get hashes for verification purposes
        if key not in self.data_store:
            return None
            
        entry = self.data_store[key]
        
        # Check if data should be purged
        if self._should_purge_entry(entry):
            return None
            
        return entry.hash_value
    
    def get_metadata(self, key: str, requester_org_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for private data entry.
        
        Args:
            key: Data key
            requester_org_id: Organization requesting metadata
            
        Returns:
            Metadata if authorized, None otherwise
        """
        if key not in self.data_store:
            return None
            
        entry = self.data_store[key]
        
        # Check if data should be purged
        if self._should_purge_entry(entry):
            return None
        
        # Return filtered metadata (remove sensitive fields)
        filtered_metadata = {
            "timestamp": entry.timestamp,
            "block_height": entry.block_height,
            "hash_value": entry.hash_value,
            "endorsement_count": len(entry.endorsements)
        }
        
        # Members get additional metadata
        if requester_org_id in self.organizations:
            filtered_metadata.update({
                "submitter_org": entry.metadata.get("submitter_org"),
                "collection_name": entry.metadata.get("collection_name"),
                "endorsements": entry.endorsements
            })
        
        return filtered_metadata
    
    def query_keys(self, query_params: Dict[str, Any], requester_org_id: str) -> List[str]:
        """
        Query private data keys based on criteria.
        
        Args:
            query_params: Query parameters for filtering
            requester_org_id: Organization making the request
            
        Returns:
            List of matching keys if authorized
        """
        # Only collection members can query keys
        if requester_org_id not in self.organizations:
            return []
        
        matching_keys = []
        
        for key, entry in self.data_store.items():
            # Skip purged entries
            if self._should_purge_entry(entry):
                continue
                
            # Apply filters
            if "submitter_org" in query_params:
                if entry.metadata.get("submitter_org") != query_params["submitter_org"]:
                    continue
                    
            if "min_timestamp" in query_params:
                if entry.timestamp < query_params["min_timestamp"]:
                    continue
                    
            if "max_timestamp" in query_params:
                if entry.timestamp > query_params["max_timestamp"]:
                    continue
                    
            if "min_block_height" in query_params:
                if entry.block_height < query_params["min_block_height"]:
                    continue
                    
            matching_keys.append(key)
        
        # Apply limit if specified
        limit = query_params.get("limit", len(matching_keys))
        return matching_keys[:limit]
    
    def update_block_height(self, new_height: int) -> None:
        """Update current block height for purging calculations"""
        self.current_block_height = new_height
        
        # Trigger purging if needed
        self._purge_expired_data()
    
    def add_organization(self, org_id: str, organization: Any) -> bool:
        """
        Add organization to the private collection.
        
        Args:
            org_id: Organization ID
            organization: Organization object
            
        Returns:
            True if successfully added
        """
        if org_id in self.organizations:
            return False
            
        self.organizations[org_id] = organization
        self.statistics["entries_by_org"][org_id] = 0
        
        return True
    
    def remove_organization(self, org_id: str) -> bool:
        """
        Remove organization from the private collection.
        
        Args:
            org_id: Organization ID to remove
            
        Returns:
            True if successfully removed
        """
        if org_id not in self.organizations:
            return False
            
        # Remove organization
        self.organizations.pop(org_id)
        
        # Clean up statistics
        if org_id in self.statistics["entries_by_org"]:
            del self.statistics["entries_by_org"][org_id]
        
        return True
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get comprehensive collection information"""
        return {
            "name": self.name,
            "status": self.status.value,
            "members": list(self.organizations.keys()),
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "current_block_height": self.current_block_height,
            "configuration": self.metadata,
            "statistics": self.statistics
        }
    
    def _verify_endorsements(self, endorsements: List[str]) -> bool:
        """
        Verify that endorsements meet the collection policy.
        
        Args:
            endorsements: List of endorsing organization IDs
            
        Returns:
            True if endorsements are sufficient
        """
        # Filter to only valid member endorsements
        valid_endorsements = [org_id for org_id in endorsements if org_id in self.organizations]
        
        policy = self.metadata["endorsement_policy"]
        total_members = len(self.organizations)
        
        if policy == EndorsementPolicy.MAJORITY:
            return len(valid_endorsements) > total_members // 2
        elif policy == EndorsementPolicy.UNANIMOUS:
            return len(valid_endorsements) == total_members
        elif policy == EndorsementPolicy.ANY:
            return len(valid_endorsements) > 0
        elif policy == EndorsementPolicy.SPECIFIC_COUNT:
            min_endorsements = self.metadata.get("min_endorsements", 2)
            return len(valid_endorsements) >= min_endorsements
        else:
            return len(valid_endorsements) >= 1
    
    def _should_purge_entry(self, entry: PrivateDataEntry) -> bool:
        """
        Check if a data entry should be purged based on block height.
        
        Args:
            entry: Private data entry to check
            
        Returns:
            True if entry should be purged
        """
        block_to_purge = self.metadata["block_to_purge"]
        if block_to_purge <= 0:
            return False  # No purging configured
            
        blocks_since_creation = self.current_block_height - entry.block_height
        return blocks_since_creation >= block_to_purge
    
    def _purge_entry(self, key: str) -> bool:
        """
        Purge a specific data entry.
        
        Args:
            key: Key of entry to purge
            
        Returns:
            True if entry was purged
        """
        if key in self.data_store:
            del self.data_store[key]
            self.statistics["purged_entries"] += 1
            return True
        return False
    
    def _purge_expired_data(self) -> int:
        """
        Purge all expired data entries.
        
        Returns:
            Number of entries purged
        """
        if self.metadata["block_to_purge"] <= 0:
            return 0
            
        keys_to_purge = []
        
        for key, entry in self.data_store.items():
            if self._should_purge_entry(entry):
                keys_to_purge.append(key)
        
        # Purge the entries
        for key in keys_to_purge:
            self._purge_entry(key)
            
        return len(keys_to_purge)
    
    def __str__(self) -> str:
        """String representation of private collection"""
        return f"PrivateCollection(name={self.name}, members={len(self.organizations)}, entries={len(self.data_store)})"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return (f"PrivateCollection(name='{self.name}', "
                f"members={len(self.organizations)}, "
                f"entries={len(self.data_store)}, "
                f"status='{self.status.value}')")