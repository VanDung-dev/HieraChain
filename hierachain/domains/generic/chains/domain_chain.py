"""
Domain Chain implementation for HieraChain Framework.

This module provides a concrete implementation of BaseChain that can be used
directly for common business scenarios or as a reference for creating
custom domain-specific chains.
"""

from typing import Any, Optional

from hierachain.domains.generic.chains.base_chain import BaseChain
from hierachain.domains.generic.events.domain_event import EventFactory


class DomainChain(BaseChain):
    """
    Concrete domain chain implementation for general business operations.
    
    This class provides a ready-to-use domain chain that handles common
    business operations while following framework guidelines. It can be
    used directly or extended for specific domain requirements.
    """
    
    def __init__(self, name: str, domain_type: str = "generic"):
        """
        Initialize a domain chain.
        
        Args:
            name: Name identifier for the chain
            domain_type: Type of domain this chain handles
        """
        super().__init__(name, domain_type)
        
        # Add domain-specific business rules
        self._setup_default_business_rules()
        
        # Track domain-specific metrics
        self.operation_metrics = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "quality_checks_passed": 0,
            "quality_checks_failed": 0,
            "approvals_granted": 0,
            "approvals_rejected": 0,
            "compliance_violations": 0
        }
        
        # Store pending 2PC transactions
        # Format: transaction_id -> payload
        self._pending_transactions: dict[str, dict[str, Any]] = {}
    
    def _setup_default_business_rules(self) -> None:
        """Setup default business rules for the domain chain."""
        
        def entity_must_be_registered(entity_info: dict[str, Any], _operation: str) -> bool:
            """Rule: Entity must be registered before operations."""
            return entity_info.get("status") != "unregistered"
        
        def no_concurrent_operations(entity_info: dict[str, Any], _operation: str) -> bool:
            """Rule: No concurrent operations on the same entity."""
            return entity_info.get("current_operation") is None
        
        def quality_check_before_approval(entity_info: dict[str, Any], operation: str) -> bool:
            """Rule: Quality check must pass before approval operations."""
            if operation.startswith("approval"):
                last_quality_check = entity_info.get("last_quality_check", {})
                return last_quality_check.get("result") == "passed"
            return True
        
        # Register default rules
        self.add_domain_rule("entity_registered", entity_must_be_registered)
        self.add_domain_rule("no_concurrent_ops", no_concurrent_operations)
        self.add_domain_rule("quality_before_approval", quality_check_before_approval)
    
    def start_domain_operation(self, entity_id: str, operation_type: str, 
                              details: Optional[dict[str, Any]] = None) -> bool:
        """
        Start a domain-specific operation with validation.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            operation_type: Type of operation to start
            details: Additional operation details
            
        Returns:
            True if operation was started successfully, False otherwise
        """
        # Validate domain rules
        if not self.validate_domain_rules(entity_id, f"start_{operation_type}"):
            return False
        
        # Validate domain-specific operation
        operation_data = details or {}
        if not self.validate_domain_operation(entity_id, operation_type, operation_data):
            return False
        
        # Start the operation
        success = self.start_operation(entity_id, operation_type, details)
        
        if success:
            self.operation_metrics["total_operations"] += 1
        
        return success
    
    def complete_domain_operation(self, entity_id: str, operation_type: str, 
                                 result: Optional[dict[str, Any]] = None) -> bool:
        """
        Complete a domain-specific operation with result tracking.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            operation_type: Type of operation to complete
            result: Operation result data
            
        Returns:
            True if operation was completed successfully, False otherwise
        """
        # Complete the operation
        success = self.complete_operation(entity_id, operation_type, result)
        
        if success:
            # Track operation success/failure
            operation_success = result and result.get("success", True)
            if operation_success:
                self.operation_metrics["successful_operations"] += 1
            else:
                self.operation_metrics["failed_operations"] += 1
        
        return success
    
    def allocate_resource(self, entity_id: str, resource_type: str, resource_id: str,
                         allocation_type: str = "assigned", 
                         details: Optional[dict[str, Any]] = None) -> bool:
        """
        Allocate a resource to an entity.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            resource_type: Type of resource being allocated
            resource_id: Identifier of the specific resource
            allocation_type: Type of allocation (assigned, released, reserved)
            details: Additional allocation details
            
        Returns:
            True if resource was allocated successfully, False otherwise
        """
        # Create resource allocation event
        event = EventFactory.create_resource_allocation(
            entity_id=entity_id,
            resource_type=resource_type,
            resource_id=resource_id,
            allocation_type=allocation_type,
            domain_type=self.domain_type,
            details=details
        )
        
        return self.add_domain_event(event)
    
    def perform_quality_check(self, entity_id: str, check_type: str, check_result: str,
                             inspector_id: Optional[str] = None,
                             details: Optional[dict[str, Any]] = None) -> bool:
        """
        Perform a quality check on an entity.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            check_type: Type of quality check performed
            check_result: Result of the quality check (passed, failed, pending)
            inspector_id: Identifier of the inspector/checker
            details: Additional check details
            
        Returns:
            True if quality check was recorded successfully, False otherwise
        """
        # Create quality check event
        event = EventFactory.create_quality_check(
            entity_id=entity_id,
            check_type=check_type,
            check_result=check_result,
            domain_type=self.domain_type,
            inspector_id=inspector_id,
            details=details
        )
        
        success = self.add_domain_event(event)
        
        if success:
            # Track quality check metrics
            if check_result == "passed":
                self.operation_metrics["quality_checks_passed"] += 1
            elif check_result == "failed":
                self.operation_metrics["quality_checks_failed"] += 1
        
        return success
    
    def update_entity_status(self, entity_id: str, status: str, 
                           details: Optional[dict[str, Any]] = None,
                           reason: Optional[str] = None) -> bool:
        """
        Update the status of an entity.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            status: New status for the entity
            details: Additional status details
            reason: Reason for the status change
            
        Returns:
            True if status was updated successfully, False otherwise
        """
        # Get current status
        entity_info = self.get_entity_info(entity_id)
        if not entity_info:
            return False
        
        old_status = entity_info.get("status", "unknown")
        
        # Create status update event
        event = EventFactory.create_status_update(
            entity_id=entity_id,
            old_status=old_status,
            new_status=status,
            domain_type=self.domain_type,
            reason=reason,
            details=details
        )
        
        return self.add_domain_event(event)
    
    def process_approval(self, entity_id: str, approval_type: str, approval_status: str,
                        approver_id: str, details: Optional[dict[str, Any]] = None) -> bool:
        """
        Process an approval for an entity.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            approval_type: Type of approval being processed
            approval_status: Status of the approval (approved, rejected, pending)
            approver_id: Identifier of the approver
            details: Additional approval details
            
        Returns:
            True if approval was processed successfully, False otherwise
        """
        # Validate domain rules for approval
        if not self.validate_domain_rules(entity_id, f"approval_{approval_type}"):
            return False
        
        # Create approval event
        event = EventFactory.create_approval(
            entity_id=entity_id,
            approval_type=approval_type,
            approval_status=approval_status,
            approver_id=approver_id,
            domain_type=self.domain_type,
            details=details
        )
        
        success = self.add_domain_event(event)
        
        if success:
            # Track approval metrics
            if approval_status == "approved":
                self.operation_metrics["approvals_granted"] += 1
            elif approval_status == "rejected":
                self.operation_metrics["approvals_rejected"] += 1
        
        return success
    
    def check_compliance(self, entity_id: str, compliance_type: str, compliance_status: str,
                        regulation_reference: Optional[str] = None,
                        details: Optional[dict[str, Any]] = None) -> bool:
        """
        Check compliance for an entity.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            compliance_type: Type of compliance being tracked
            compliance_status: Status of compliance (compliant, non_compliant, under_review)
            regulation_reference: Reference to specific regulation or standard
            details: Additional compliance details
            
        Returns:
            True if compliance check was recorded successfully, False otherwise
        """
        # Create compliance event
        event = EventFactory.create_compliance_check(
            entity_id=entity_id,
            compliance_type=compliance_type,
            compliance_status=compliance_status,
            domain_type=self.domain_type,
            regulation_reference=regulation_reference,
            details=details
        )
        
        success = self.add_domain_event(event)
        
        if success:
            # Track compliance violations
            if compliance_status == "non_compliant":
                self.operation_metrics["compliance_violations"] += 1
        
        return success
    
    def validate_domain_operation(self, entity_id: str, operation_type: str, 
                                 operation_data: dict[str, Any]) -> bool:
        """
        Validate a domain-specific operation.
        
        Args:
            entity_id: Entity identifier
            operation_type: Type of operation
            operation_data: Operation data
            
        Returns:
            True if operation is valid for this domain, False otherwise
        """
        # Basic validation - entity must exist
        if not self.get_entity_info(entity_id):
            return False
        
        # Operation-specific validation
        if operation_type == "quality_check":
            # Quality checks require check_type and result
            return ("check_type" in operation_data and 
                   "check_result" in operation_data)
        
        elif operation_type == "approval":
            # Approvals require approval_type and approver
            return ("approval_type" in operation_data and 
                   "approver_id" in operation_data)
        
        elif operation_type == "resource_allocation":
            # Resource allocation requires resource info
            return ("resource_type" in operation_data and 
                   "resource_id" in operation_data)
        
        elif operation_type == "compliance_check":
            # Compliance checks require compliance type
            return "compliance_type" in operation_data
        
        # Default validation for other operations
        return True
    
    def get_domain_statistics(self) -> dict[str, Any]:
        """
        Get domain-specific statistics.
        
        Returns:
            Domain-specific statistics
        """
        base_stats = self.get_base_domain_statistics()
        
        # Add operation metrics
        base_stats.update({
            "operation_metrics": self.operation_metrics.copy(),
            "success_rate": (
                self.operation_metrics["successful_operations"] / 
                max(self.operation_metrics["total_operations"], 1)
            ),
            "quality_pass_rate": (
                self.operation_metrics["quality_checks_passed"] / 
                max(self.operation_metrics["quality_checks_passed"] + 
                    self.operation_metrics["quality_checks_failed"], 1)
            ),
            "approval_rate": (
                self.operation_metrics["approvals_granted"] / 
                max(self.operation_metrics["approvals_granted"] + 
                    self.operation_metrics["approvals_rejected"], 1)
            )
        })
        
        return base_stats
    
    def get_entity_compliance_report(self, entity_id: str) -> dict[str, Any]:
        """
        Get a compliance report for a specific entity.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            Compliance report for the entity
        """
        entity_info = self.get_entity_info(entity_id)
        if not entity_info:
            return {}
        
        # Get compliance events for this entity
        compliance_events: list[dict[str, Any]] = []
        for block in self.chain:
            # Use to_event_list() if available to handle Arrow Tables
            events = block.to_event_list() if hasattr(block, 'to_event_list') else block.events
            for event in events:
                if (event.get("entity_id") == entity_id and 
                    event.get("event") == "compliance_check"):
                    compliance_events.append(event)
        
        # Analyze compliance status
        compliance_types: dict[str, dict[str, Any]] = {}
        for event in compliance_events:
            details = event.get("details", {})
            comp_type = details.get("compliance_type")
            comp_status = details.get("compliance_status")
            
            if comp_type:
                compliance_types[comp_type] = {
                    "status": comp_status,
                    "timestamp": event.get("timestamp"),
                    "regulation": details.get("regulation_reference")
                }
        
        return {
            "entity_id": entity_id,
            "domain_type": self.domain_type,
            "compliance_checks": len(compliance_events),
            "compliance_types": compliance_types,
            "overall_compliant": all(
                info["status"] == "compliant" 
                for info in compliance_types.values()
            ),
            "violations": sum(
                1 for info in compliance_types.values() 
                if info["status"] == "non_compliant"
            )
        }
    
    def get_entity_performance_metrics(self, entity_id: str) -> dict[str, Any]:
        """
        Get performance metrics for a specific entity.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            Performance metrics for the entity
        """
        entity_events = self.get_entity_history(entity_id)
        
        # Analyze performance
        operations_started = 0
        operations_completed = 0
        quality_checks = 0
        quality_passed = 0
        approvals_requested = 0
        approvals_granted = 0
        
        for event in entity_events:
            event_type = event.get("event")
            details = event.get("details", {})
            
            if event_type == "operation_start":
                operations_started += 1
            elif event_type == "operation_complete":
                operations_completed += 1
            elif event_type == "quality_check":
                quality_checks += 1
                if details.get("check_result") == "passed":
                    quality_passed += 1
            elif event_type == "approval":
                approvals_requested += 1
                if details.get("approval_status") == "approved":
                    approvals_granted += 1
        
        return {
            "entity_id": entity_id,
            "domain_type": self.domain_type,
            "operations_started": operations_started,
            "operations_completed": operations_completed,
            "completion_rate": operations_completed / max(operations_started, 1),
            "quality_checks": quality_checks,
            "quality_pass_rate": quality_passed / max(quality_checks, 1),
            "approvals_requested": approvals_requested,
            "approval_rate": approvals_granted / max(approvals_requested, 1),
            "total_events": len(entity_events)
        }
    
    
    # --- 2PC Transaction Methods ---

    def prepare_transaction(self, transaction_id: str, payload: dict[str, Any], is_source: bool = True) -> bool:
        """
        Phase 1: Prepare for a cross-chain transaction.
        
        Args:
            transaction_id: Unique transaction Identifier.
            payload: Transaction details.
            is_source: True if this is the source chain, False if destination.
            
        Returns:
            True if prepared successfully (resources locked/validated), False otherwise.
        """
        if transaction_id in self._pending_transactions:
            # Already prepared
            return True
            
        # Extract entity_id and operation details from payload
        entity_id = payload.get("entity_id")
        if not entity_id:
            return False
            
        operation_type = payload.get("operation_type")
        details = payload.get("details", {})
        
        # 1. Validate domain rules
        validation_op = f"prepare_{operation_type}"
        if not self.validate_domain_rules(entity_id, validation_op):
            return False
            
        if not self.validate_domain_operation(entity_id, operation_type, details):
            return False
            
        # 2. Lock resources / Store pending state
        self._pending_transactions[transaction_id] = {
            "payload": payload,
            "is_source": is_source,
            "timestamp": float(0)  # Using 0 as placeholder or time.time() if imported
        }
        
        return True

    def commit_transaction(self, transaction_id: str) -> bool:
        """
        Phase 2: Commit the transaction.
        
        Args:
            transaction_id: Transaction ID to commit.
            
        Returns:
            True if committed successfully.
        """
        if transaction_id not in self._pending_transactions:
            return False
            
        pending_data = self._pending_transactions[transaction_id]
        payload = pending_data["payload"]
        
        entity_id = payload.get("entity_id")
        operation_type = payload.get("operation_type")
        details = payload.get("details", {})
        
        try:
            # Record the operation on-chain
            success = self.start_domain_operation(entity_id, operation_type, details)
            if success:
                self.complete_domain_operation(entity_id, operation_type, {"status": "committed", "tx_id": transaction_id})
                
                # Cleanup pending
                del self._pending_transactions[transaction_id]
                return True
            return False
        except Exception:
            return False

    def rollback_transaction(self, transaction_id: str) -> bool:
        """
        Phase 2 (Alternative): Rollback the transaction.
        
        Args:
            transaction_id: Transaction ID to rollback.
            
        Returns:
            True if rolled back successfully.
        """
        if transaction_id in self._pending_transactions:
            del self._pending_transactions[transaction_id]
            return True
        return False

    def __str__(self) -> str:
        """String representation of the domain chain."""
        return f"DomainChain(name={self.name}, domain={self.domain_type}, entities={len(self.entity_registry)}, operations={self.operation_metrics['total_operations']})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the domain chain."""
        return (f"DomainChain(name={self.name}, domain_type={self.domain_type}, "
                f"entities={len(self.entity_registry)}, blocks={len(self.chain)}, "
                f"total_operations={self.operation_metrics['total_operations']}, "
                f"success_rate={self.operation_metrics['successful_operations'] / max(self.operation_metrics['total_operations'], 1):.2f})")
