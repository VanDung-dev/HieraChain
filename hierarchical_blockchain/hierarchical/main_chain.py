"""
Main Chain implementation for Hierarchical-Blockchain Framework.

This module implements the Main Chain class that acts as the root authority
in the hierarchical blockchain structure. The Main Chain only stores proofs
from Sub-Chains, never detailed domain data, following framework guidelines.
"""

import time
from typing import Dict, Any, List, Optional, Set

from hierarchical_blockchain.core.blockchain import Blockchain
from hierarchical_blockchain.core.consensus.proof_of_authority import ProofOfAuthority
from hierarchical_blockchain.core.utils import sanitize_metadata_for_main_chain, validate_proof_metadata


class MainChain(Blockchain):
    """
    Main Chain implementation for the hierarchical blockchain framework.
    
    The Main Chain acts as the root authority (like a CEO in an organization) and:
    - Only stores proofs from Sub-Chains, NOT detailed domain data
    - Maintains the integrity of the entire hierarchical system
    - Provides proof verification and chain coordination
    - Uses Proof of Authority consensus suitable for business applications
    """
    
    def __init__(self, name: str = "MainChain"):
        """
        Initialize the Main Chain.
        
        Args:
            name: Name identifier for the Main Chain
        """
        super().__init__(name)
        self.consensus = ProofOfAuthority("MainChain_PoA")
        self.registered_sub_chains: Set[str] = set()
        self.sub_chain_metadata: Dict[str, Dict[str, Any]] = {}
        self.proof_count: int = 0
        
        # Register Main Chain as the primary authority
        self.consensus.add_authority("main_chain", {
            "role": "root_authority",
            "permissions": ["proof_validation", "sub_chain_registration"],
            "created_at": time.time()
        })
    
    def register_sub_chain(self, sub_chain_name: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Register a Sub-Chain with the Main Chain.
        
        Args:
            sub_chain_name: Name of the Sub-Chain to register
            metadata: Metadata about the Sub-Chain
            
        Returns:
            True if Sub-Chain was registered successfully, False otherwise
        """
        if sub_chain_name in self.registered_sub_chains:
            return False
        
        self.registered_sub_chains.add(sub_chain_name)
        self.sub_chain_metadata[sub_chain_name] = metadata or {}
        
        # Add Sub-Chain as an authority for proof submission
        self.consensus.add_authority(sub_chain_name, {
            "role": "sub_chain",
            "permissions": ["proof_submission"],
            "registered_at": time.time(),
            "metadata": metadata
        })
        
        # Create registration event
        registration_event = {
            "event": "sub_chain_registration",
            "timestamp": time.time(),
            "details": {
                "sub_chain_name": sub_chain_name,
                "registered_by": "main_chain",
                "metadata": sanitize_metadata_for_main_chain(metadata or {})
            }
        }
        
        self.add_event(registration_event)
        return True
    
    def add_proof(self, sub_chain_name: str, proof_hash: str, metadata: Dict[str, Any]) -> bool:
        """
        Add a proof from a Sub-Chain to the Main Chain.
        
        This is the critical method that follows framework guidelines:
        - Only stores proof evidence, NOT domain data
        - Metadata contains summary data only
        
        Args:
            sub_chain_name: Name of the Sub-Chain submitting the proof
            proof_hash: Hash of the block being proven
            metadata: Summary metadata (NOT detailed domain data)
            
        Returns:
            True if proof was added successfully, False otherwise
        """
        # Validate Sub-Chain is registered
        if sub_chain_name not in self.registered_sub_chains:
            return False
        
        # Validate metadata is suitable for Main Chain (no detailed data)
        if not validate_proof_metadata(metadata):
            return False
        
        # Sanitize metadata to ensure only summary data
        sanitized_metadata = sanitize_metadata_for_main_chain(metadata)
        
        # Create proof submission event (following guidelines pattern)
        event = {
            "type": "sub_chain_proof",
            "sub_chain": sub_chain_name,
            "proof_hash": proof_hash,
            "metadata": sanitized_metadata  # Summary data only
        }
        
        # Add required fields for proper event structure
        event.update({
            "event": "proof_submission",
            "timestamp": time.time(),
            "details": {
                "sub_chain_name": sub_chain_name,
                "proof_hash": proof_hash,
                "proof_id": f"PROOF-{self.proof_count + 1}",
                "submitted_at": time.time()
            }
        })
        
        # Add the event to Main Chain
        self.add_event(event)
        self.proof_count += 1
        
        return True
    
    def verify_proof(self, proof_hash: str, sub_chain_name: str) -> bool:
        """
        Verify a proof exists in the Main Chain.
        
        Args:
            proof_hash: Hash of the proof to verify
            sub_chain_name: Name of the Sub-Chain that submitted the proof
            
        Returns:
            True if proof exists and is valid, False otherwise
        """
        # Search for proof in all blocks
        for block in self.chain:
            for event in block.events:
                if (event.get("event") == "proof_submission" and
                    event.get("details", {}).get("proof_hash") == proof_hash and
                    event.get("details", {}).get("sub_chain_name") == sub_chain_name):
                    return True
        
        # Search in pending events as well
        for event in self.pending_events:
            if (event.get("event") == "proof_submission" and
                event.get("details", {}).get("proof_hash") == proof_hash and
                event.get("details", {}).get("sub_chain_name") == sub_chain_name):
                return True
        
        return False
    
    def get_proofs_by_sub_chain(self, sub_chain_name: str) -> List[Dict[str, Any]]:
        """
        Get all proofs submitted by a specific Sub-Chain.
        
        Args:
            sub_chain_name: Name of the Sub-Chain
            
        Returns:
            List of proof events from the specified Sub-Chain
        """
        proofs = []
        for block in self.chain:
            for event in block.events:
                if (event.get("event") == "proof_submission" and
                    event.get("details", {}).get("sub_chain_name") == sub_chain_name):
                    proofs.append(event)
        
        # Add pending proofs as well
        for event in self.pending_events:
            if (event.get("event") == "proof_submission" and
                event.get("details", {}).get("sub_chain_name") == sub_chain_name):
                proofs.append(event)
        
        return proofs
    
    def get_sub_chain_summary(self, sub_chain_name: str) -> Dict[str, Any]:
        """
        Get summary information about a Sub-Chain.
        
        Args:
            sub_chain_name: Name of the Sub-Chain
            
        Returns:
            Summary information about the Sub-Chain
        """
        if sub_chain_name not in self.registered_sub_chains:
            return {}
        
        proofs = self.get_proofs_by_sub_chain(sub_chain_name)
        
        return {
            "sub_chain_name": sub_chain_name,
            "registered": True,
            "total_proofs": len(proofs),
            "metadata": self.sub_chain_metadata.get(sub_chain_name, {}),
            "latest_proof": proofs[-1] if proofs else None,
            "registration_time": self.sub_chain_metadata.get(sub_chain_name, {}).get("registered_at")
        }
    
    def get_main_chain_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the Main Chain.
        
        Returns:
            Dictionary containing Main Chain statistics
        """
        base_stats = self.get_chain_stats()
        
        # Count proof submissions
        proof_events = self.get_events_by_type("proof_submission")
        
        return {
            **base_stats,
            "role": "main_chain",
            "registered_sub_chains": len(self.registered_sub_chains),
            "sub_chains": list(self.registered_sub_chains),
            "total_proofs": len(proof_events),
            "consensus_type": self.consensus.name,
            "authorities": len(self.consensus.authorities)
        }
    
    def finalize_main_chain_block(self) -> Optional[Dict[str, Any]]:
        """
        Finalize a block on the Main Chain using PoA consensus.
        
        Returns:
            Information about the finalized block, or None if no pending events
        """
        if not self.pending_events:
            return None
        
        # Create block with pending events
        new_block = self.create_block()
        
        # Finalize block using PoA consensus
        finalized_block = self.consensus.finalize_block(new_block, "main_chain")
        
        # Add finalized block to chain
        if self.add_block(finalized_block):
            return {
                "block_index": finalized_block.index,
                "block_hash": finalized_block.hash,
                "events_count": len(finalized_block.events),
                "finalized_at": time.time()
            }
        
        return None
    
    def validate_sub_chain_proof_format(self, proof_data: Dict[str, Any]) -> bool:
        """
        Validate the format of a Sub-Chain proof submission.
        
        Args:
            proof_data: Proof data to validate
            
        Returns:
            True if proof format is valid, False otherwise
        """
        required_fields = ["sub_chain_name", "proof_hash", "metadata"]
        
        for field in required_fields:
            if field not in proof_data:
                return False
        
        # Validate Sub-Chain is registered
        if proof_data["sub_chain_name"] not in self.registered_sub_chains:
            return False
        
        # Validate metadata doesn't contain detailed domain data
        if not validate_proof_metadata(proof_data["metadata"]):
            return False
        
        return True
    
    def get_hierarchical_integrity_report(self) -> Dict[str, Any]:
        """
        Generate an integrity report for the entire hierarchical system.
        
        Returns:
            Comprehensive integrity report
        """
        report = {
            "main_chain": {
                "name": self.name,
                "blocks": len(self.chain),
                "valid": self.is_chain_valid(),
                "latest_hash": self.get_latest_block().hash
            },
            "sub_chains": {},
            "total_proofs": self.proof_count,
            "registered_sub_chains": len(self.registered_sub_chains),
            "system_integrity": "healthy" if self.is_chain_valid() else "compromised"
        }
        
        # Add Sub-Chain summaries
        for sub_chain_name in self.registered_sub_chains:
            report["sub_chains"][sub_chain_name] = self.get_sub_chain_summary(sub_chain_name)
        
        return report
    
    def __str__(self) -> str:
        """String representation of the Main Chain."""
        return f"MainChain(blocks={len(self.chain)}, sub_chains={len(self.registered_sub_chains)}, proofs={self.proof_count})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the Main Chain."""
        return (f"MainChain(name={self.name}, blocks={len(self.chain)}, "
                f"sub_chains={len(self.registered_sub_chains)}, proofs={self.proof_count}, "
                f"valid={self.is_chain_valid()})")