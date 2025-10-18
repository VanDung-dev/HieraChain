"""
Cross-Chain Validator for Hierarchical-Blockchain Framework.

This module provides validation capabilities across the hierarchical blockchain
system to ensure data consistency and integrity between Main Chain and Sub-Chains
while maintaining framework guidelines.
"""

import time
from typing import Dict, Any, List, Callable

from hierarchical.hierarchy_manager import HierarchyManager


class CrossChainValidator:
    """
    Cross-chain validation utility for the hierarchical blockchain framework.
    
    This class provides comprehensive validation capabilities:
    - Validate proof consistency between Main Chain and Sub-Chains
    - Check data integrity across the hierarchical system
    - Verify entity consistency across multiple chains
    - Detect anomalies and inconsistencies
    - Generate validation reports and recommendations
    """
    
    def __init__(self, hierarchy_manager: HierarchyManager):
        """
        Initialize the Cross-Chain Validator.
        
        Args:
            hierarchy_manager: HierarchyManager instance to validate across
        """
        self.hierarchy_manager = hierarchy_manager
        self.validation_cache: Dict[str, Dict[str, Any]] = {}
        self.last_validation = 0.0
        self.validation_rules: Dict[str, callable] = {}
        
        # Setup default validation rules
        self._setup_default_validation_rules()
    
    def _setup_default_validation_rules(self) -> None:
        """Setup default validation rules for cross-chain validation."""
        
        def proof_hash_consistency(main_chain_event: Dict[str, Any], 
                                 sub_chain_block: Dict[str, Any]) -> bool:
            """Validate that proof hash matches Sub-Chain block hash."""
            proof_hash = main_chain_event.get("details", {}).get("proof_hash")
            block_hash = sub_chain_block.get("hash")
            return proof_hash == block_hash
        
        def proof_timestamp_consistency(main_chain_event: Dict[str, Any], 
                                      sub_chain_block: Dict[str, Any]) -> bool:
            """Validate that proof timestamp is after Sub-Chain block timestamp."""
            proof_timestamp = main_chain_event.get("timestamp", 0)
            block_timestamp = sub_chain_block.get("timestamp", 0)
            return proof_timestamp >= block_timestamp
        
        def entity_id_metadata_usage(event: Dict[str, Any]) -> bool:
            """Validate that entity_id is used as metadata, not as identifier."""
            # entity_id should be in the event data, not used as block/chain identifier
            return "entity_id" in event and isinstance(event["entity_id"], str)
        
        def no_cryptocurrency_terms(data: Dict[str, Any]) -> bool:
            """Validate that data doesn't contain cryptocurrency terminology."""
            forbidden_terms = [
                "transaction", "mining", "coin", "token", "wallet", 
                "address", "sender", "receiver", "amount", "fee"
            ]
            
            data_str = str(data).lower()
            return not any(term in data_str for term in forbidden_terms)
        
        # Register validation rules
        self.validation_rules.update({
            "proof_hash_consistency": proof_hash_consistency,
            "proof_timestamp_consistency": proof_timestamp_consistency,
            "entity_id_metadata_usage": entity_id_metadata_usage,
            "no_cryptocurrency_terms": no_cryptocurrency_terms
        })
    
    def validate_proof_consistency(self) -> Dict[str, Any]:
        """
        Validate consistency between Main Chain proofs and Sub-Chain blocks.
        
        Returns:
            Validation results for proof consistency
        """
        validation_results = {
            "timestamp": time.time(),
            "total_proofs_checked": 0,
            "consistent_proofs": 0,
            "inconsistent_proofs": 0,
            "missing_blocks": 0,
            "inconsistencies": [],
            "overall_consistent": True
        }
        
        # Get all proof submission events from Main Chain
        proof_events = self.hierarchy_manager.main_chain.get_events_by_type("proof_submission")
        validation_results["total_proofs_checked"] = len(proof_events)
        
        for proof_event in proof_events:
            details = proof_event.get("details", {})
            sub_chain_name = details.get("sub_chain_name")
            proof_hash = details.get("proof_hash")
            
            if not sub_chain_name or not proof_hash:
                continue
            
            # Get corresponding Sub-Chain
            sub_chain = self.hierarchy_manager.get_sub_chain(sub_chain_name)
            if not sub_chain:
                validation_results["missing_blocks"] += 1
                validation_results["inconsistencies"].append({
                    "type": "missing_sub_chain",
                    "sub_chain_name": sub_chain_name,
                    "proof_hash": proof_hash,
                    "timestamp": proof_event.get("timestamp")
                })
                continue
            
            # Find the corresponding block in Sub-Chain
            corresponding_block = None
            for block in sub_chain.chain:
                if block.hash == proof_hash:
                    corresponding_block = block
                    break
            
            if not corresponding_block:
                validation_results["missing_blocks"] += 1
                validation_results["inconsistencies"].append({
                    "type": "missing_block",
                    "sub_chain_name": sub_chain_name,
                    "proof_hash": proof_hash,
                    "timestamp": proof_event.get("timestamp")
                })
                continue
            
            # Validate consistency using rules
            block_dict = corresponding_block.to_dict()
            
            # Check proof hash consistency
            if not self.validation_rules["proof_hash_consistency"](proof_event, block_dict):
                validation_results["inconsistent_proofs"] += 1
                validation_results["inconsistencies"].append({
                    "type": "hash_mismatch",
                    "sub_chain_name": sub_chain_name,
                    "expected_hash": proof_hash,
                    "actual_hash": block_dict.get("hash"),
                    "timestamp": proof_event.get("timestamp")
                })
                continue
            
            # Check timestamp consistency
            if not self.validation_rules["proof_timestamp_consistency"](proof_event, block_dict):
                validation_results["inconsistent_proofs"] += 1
                validation_results["inconsistencies"].append({
                    "type": "timestamp_inconsistency",
                    "sub_chain_name": sub_chain_name,
                    "proof_timestamp": proof_event.get("timestamp"),
                    "block_timestamp": block_dict.get("timestamp"),
                    "proof_hash": proof_hash
                })
                continue
            
            validation_results["consistent_proofs"] += 1
        
        # Determine overall consistency
        validation_results["overall_consistent"] = (
            validation_results["inconsistent_proofs"] == 0 and 
            validation_results["missing_blocks"] == 0
        )
        
        return validation_results
    
    def validate_entity_consistency(self, entity_id: str) -> Dict[str, Any]:
        """
        Validate consistency of an entity across all chains.
        
        Args:
            entity_id: Entity identifier to validate
            
        Returns:
            Entity consistency validation results
        """
        validation_results = {
            "entity_id": entity_id,
            "timestamp": time.time(),
            "chains_checked": 0,
            "total_events": 0,
            "consistent_events": 0,
            "inconsistent_events": 0,
            "inconsistencies": [],
            "entity_found": False,
            "overall_consistent": True
        }
        
        # Get entity trace across all chains
        entity_trace = self.hierarchy_manager.trace_entity_across_chains(entity_id)
        
        if not entity_trace:
            return validation_results
        
        validation_results["entity_found"] = True
        validation_results["chains_checked"] = len(entity_trace)
        
        # Validate each event in each chain
        for chain_name, events in entity_trace.items():
            validation_results["total_events"] += len(events)
            
            for event in events:
                # Validate entity_id usage
                if not self.validation_rules["entity_id_metadata_usage"](event):
                    validation_results["inconsistent_events"] += 1
                    validation_results["inconsistencies"].append({
                        "type": "entity_id_misuse",
                        "chain_name": chain_name,
                        "event": event,
                        "issue": "entity_id not used as metadata field"
                    })
                    continue
                
                # Validate no cryptocurrency terms
                if not self.validation_rules["no_cryptocurrency_terms"](event):
                    validation_results["inconsistent_events"] += 1
                    validation_results["inconsistencies"].append({
                        "type": "cryptocurrency_terms",
                        "chain_name": chain_name,
                        "event": event,
                        "issue": "contains forbidden cryptocurrency terminology"
                    })
                    continue
                
                # Validate event structure
                if not self._validate_event_structure(event):
                    validation_results["inconsistent_events"] += 1
                    validation_results["inconsistencies"].append({
                        "type": "invalid_event_structure",
                        "chain_name": chain_name,
                        "event": event,
                        "issue": "event structure doesn't follow framework guidelines"
                    })
                    continue
                
                validation_results["consistent_events"] += 1
        
        # Check for logical inconsistencies across chains
        logical_inconsistencies = self._check_logical_consistency(entity_trace)
        validation_results["inconsistencies"].extend(logical_inconsistencies)
        validation_results["inconsistent_events"] += len(logical_inconsistencies)
        
        # Determine overall consistency
        validation_results["overall_consistent"] = validation_results["inconsistent_events"] == 0
        
        return validation_results
    
    @staticmethod
    def _validate_event_structure(event: Dict[str, Any]) -> bool:
        """Validate that event follows framework structure guidelines."""
        # Required fields
        required_fields = ["entity_id", "event", "timestamp"]
        for field in required_fields:
            if field not in event:
                return False
        
        # Event type should be string
        if not isinstance(event["event"], str):
            return False
        
        # Timestamp should be numeric
        if not isinstance(event["timestamp"], (int, float)):
            return False
        
        # entity_id should be string (metadata field)
        if not isinstance(event["entity_id"], str):
            return False
        
        return True
    
    @staticmethod
    def _check_logical_consistency(entity_trace: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Check for logical inconsistencies in entity events across chains."""
        inconsistencies = []
        
        # Collect all events and sort by timestamp
        all_events = []
        for chain_name, events in entity_trace.items():
            for event in events:
                event_with_chain = event.copy()
                event_with_chain["_chain_name"] = chain_name
                all_events.append(event_with_chain)
        
        all_events.sort(key=lambda x: x.get("timestamp", 0))
        
        # Check for logical inconsistencies
        entity_status = None
        current_operation = None
        
        for event in all_events:
            event_type = event.get("event")
            details = event.get("details", {})
            chain_name = event.get("_chain_name")
            
            # Check operation consistency
            if event_type == "operation_start":
                if current_operation is not None:
                    inconsistencies.append({
                        "type": "concurrent_operations",
                        "chain_name": chain_name,
                        "event": event,
                        "issue": f"Operation started while {current_operation} is still active"
                    })
                current_operation = details.get("operation_type")
            
            elif event_type == "operation_complete":
                if current_operation is None:
                    inconsistencies.append({
                        "type": "operation_complete_without_start",
                        "chain_name": chain_name,
                        "event": event,
                        "issue": "Operation completed without corresponding start event"
                    })
                current_operation = None
            
            # Check status consistency
            elif event_type == "status_update":
                old_status = details.get("old_status")
                new_status = details.get("new_status")
                
                if entity_status is not None and entity_status != old_status:
                    inconsistencies.append({
                        "type": "status_inconsistency",
                        "chain_name": chain_name,
                        "event": event,
                        "issue": f"Expected old_status to be {entity_status}, but got {old_status}"
                    })
                
                entity_status = new_status
        
        return inconsistencies
    
    def validate_system_integrity(self) -> Dict[str, Any]:
        """
        Validate the integrity of the entire hierarchical system.
        
        Returns:
            Comprehensive system integrity validation results
        """
        validation_results = dict(
            timestamp=time.time(),
            main_chain_valid=False,
            sub_chains_valid={},
            proof_consistency={},
            framework_compliance={},
            overall_integrity=False,
            recommendations=[]
        )
        
        # Validate Main Chain
        validation_results["main_chain_valid"] = self.hierarchy_manager.main_chain.is_chain_valid()
        
        # Validate each Sub-Chain
        for sub_chain_name, sub_chain in self.hierarchy_manager.sub_chains.items():
            validation_results["sub_chains_valid"][sub_chain_name] = sub_chain.is_chain_valid()
        
        # Validate proof consistency
        validation_results["proof_consistency"] = self.validate_proof_consistency()
        
        # Validate framework compliance
        validation_results["framework_compliance"] = self._validate_framework_compliance()
        
        # Generate recommendations
        validation_results["recommendations"] = self._generate_system_recommendations(validation_results)
        
        # Determine overall integrity
        validation_results["overall_integrity"] = (
            validation_results["main_chain_valid"] and
            all(validation_results["sub_chains_valid"].values()) and
            validation_results["proof_consistency"]["overall_consistent"] and
            validation_results["framework_compliance"]["overall_compliant"]
        )
        
        return validation_results
    
    def _validate_framework_compliance(self) -> Dict[str, Any]:
        """Validate compliance with framework guidelines."""
        compliance_results = {
            "timestamp": time.time(),
            "chains_checked": 0,
            "compliant_chains": 0,
            "violations": [],
            "overall_compliant": True
        }
        
        # Check Main Chain compliance
        main_chain_violations = self._check_chain_compliance(
            self.hierarchy_manager.main_chain, "MainChain"
        )
        compliance_results["violations"].extend(main_chain_violations)
        compliance_results["chains_checked"] += 1
        
        if not main_chain_violations:
            compliance_results["compliant_chains"] += 1
        
        # Check Sub-Chain compliance
        for sub_chain_name, sub_chain in self.hierarchy_manager.sub_chains.items():
            sub_chain_violations = self._check_chain_compliance(sub_chain, sub_chain_name)
            compliance_results["violations"].extend(sub_chain_violations)
            compliance_results["chains_checked"] += 1
            
            if not sub_chain_violations:
                compliance_results["compliant_chains"] += 1
        
        compliance_results["overall_compliant"] = len(compliance_results["violations"]) == 0
        
        return compliance_results
    
    def _check_chain_compliance(self, chain: Any, chain_name: str) -> List[Dict[str, Any]]:
        """Check a single chain for framework compliance."""
        violations = []
        
        # Check all blocks in the chain
        for block in chain.chain:
            # Validate block structure
            if not isinstance(block.events, list):
                violations.append({
                    "type": "invalid_block_structure",
                    "chain_name": chain_name,
                    "block_index": block.index,
                    "issue": "Block events should be a list, not a single event"
                })
            
            # Check each event in the block
            for event in block.events:
                # Check for cryptocurrency terms
                if not self.validation_rules["no_cryptocurrency_terms"](event):
                    violations.append({
                        "type": "cryptocurrency_terms",
                        "chain_name": chain_name,
                        "block_index": block.index,
                        "event": event,
                        "issue": "Event contains forbidden cryptocurrency terminology"
                    })
                
                # Check entity_id usage
                if "entity_id" in event:
                    if not self.validation_rules["entity_id_metadata_usage"](event):
                        violations.append({
                            "type": "entity_id_misuse",
                            "chain_name": chain_name,
                            "block_index": block.index,
                            "event": event,
                            "issue": "entity_id should be used as metadata field"
                        })
        
        return violations
    
    @staticmethod
    def _generate_system_recommendations(validation_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on system validation results."""
        recommendations = []
        
        # Main Chain recommendations
        if not validation_results["main_chain_valid"]:
            recommendations.append("Main Chain integrity is compromised - immediate investigation required")
        
        # Sub-Chain recommendations
        invalid_sub_chains = [
            name for name, valid in validation_results["sub_chains_valid"].items() 
            if not valid
        ]
        if invalid_sub_chains:
            recommendations.append(f"Sub-Chains with integrity issues: {', '.join(invalid_sub_chains)}")
        
        # Proof consistency recommendations
        proof_consistency = validation_results["proof_consistency"]
        if not proof_consistency["overall_consistent"]:
            if proof_consistency["missing_blocks"] > 0:
                recommendations.append("Missing blocks detected - check Sub-Chain synchronization")
            if proof_consistency["inconsistent_proofs"] > 0:
                recommendations.append("Proof inconsistencies detected - verify proof submission process")
        
        # Framework compliance recommendations
        framework_compliance = validation_results["framework_compliance"]
        if not framework_compliance["overall_compliant"]:
            violation_types = set(v["type"] for v in framework_compliance["violations"])
            if "cryptocurrency_terms" in violation_types:
                recommendations.append("Remove cryptocurrency terminology from events and data")
            if "entity_id_misuse" in violation_types:
                recommendations.append("Ensure entity_id is used as metadata field, not as identifier")
            if "invalid_block_structure" in violation_types:
                recommendations.append("Fix block structures to contain multiple events, not single events")
        
        return recommendations
    
    def generate_validation_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive validation report for the hierarchical system.
        
        Returns:
            Comprehensive validation report
        """
        # Perform all validations
        system_integrity = self.validate_system_integrity()
        
        # Get additional statistics
        system_stats = self.hierarchy_manager.get_system_integrity_report()
        
        return {
            "report_generated_at": time.time(),
            "system_overview": system_stats["system_overview"],
            "validation_results": system_integrity,
            "summary": {
                "overall_healthy": system_integrity["overall_integrity"],
                "main_chain_status": "healthy" if system_integrity["main_chain_valid"] else "compromised",
                "sub_chains_status": f"{system_integrity['proof_consistency']['consistent_proofs']}/{system_integrity['proof_consistency']['total_proofs_checked']} proofs consistent",
                "framework_compliance": "compliant" if system_integrity["framework_compliance"]["overall_compliant"] else "violations detected",
                "total_recommendations": len(system_integrity["recommendations"])
            },
            "recommendations": system_integrity["recommendations"]
        }
    
    def add_validation_rule(self, rule_name: str, rule_function: Callable) -> None:
        """
        Add a custom validation rule.
        
        Args:
            rule_name: Name of the validation rule
            rule_function: Function that implements the validation logic
        """
        self.validation_rules[rule_name] = rule_function
    
    def __str__(self) -> str:
        """String representation of the Cross-Chain Validator."""
        return f"CrossChainValidator(hierarchy_manager={self.hierarchy_manager.main_chain.name})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the Cross-Chain Validator."""
        return (f"CrossChainValidator(main_chain={self.hierarchy_manager.main_chain.name}, "
                f"sub_chains={len(self.hierarchy_manager.sub_chains)}, "
                f"validation_rules={len(self.validation_rules)})")