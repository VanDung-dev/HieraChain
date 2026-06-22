"""
Domain Chain implementation for HieraChain Ledger.

This module provides a concrete implementation of BaseChain that can be used
directly for common business scenarios or as a reference for creating
custom domain-specific chains.
"""

from typing import Any

from hierachain.domains.chains.base_chain import BaseChain
from hierachain.domains.events.domain_event import (
    create_resource_allocation,
    create_quality_check,
    create_status_update,
    create_approval,
    create_compliance_check
)

from hierachain.domains.chains.metrics import (
    OperationMetricsTracker,
    _calculate_performance_stats,
    _safe_ratio,
)
from hierachain.domains.chains.tx_manager import TransactionManager


def _analyze_compliance_status(
    events: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Process compliance events into a summary dictionary."""
    compliance_types: dict[str, dict[str, Any]] = {}
    for event in events:
        details = event.get("details", {})
        comp_type = details.get("compliance_type")
        if comp_type:
            compliance_types[comp_type] = {
                "status": details.get("compliance_status"),
                "timestamp": event.get("timestamp"),
                "regulation": details.get("regulation_reference")
            }
    return compliance_types


# Required fields per operation type
_OPERATION_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "quality_check": ("check_type", "check_result"),
    "approval": ("approval_type", "approver_id"),
    "resource_allocation": ("resource_type", "resource_id"),
    "compliance_check": ("compliance_type",),
}


def validate_operation_data(
    operation_type: str, operation_data: dict[str, Any]
) -> bool:
    """
    Validate that *operation_data* contains the fields required by
    *operation_type*.  Returns ``True`` for unknown operation types
    (default-allow).
    """
    required = _OPERATION_REQUIRED_FIELDS.get(operation_type)
    if required is None:
        return True
    return all(field in operation_data for field in required)


class DomainChain(BaseChain):
    """
    Concrete domain chain implementation for general business operations.

    This class provides a ready-to-use domain chain that handles common
    business operations while following Ledger guidelines. It can be
    used directly or extended for specific domain requirements.

    Responsibilities are delegated to helpers:
        - OperationMetricsTracker  - recording & querying metrics
        - TransactionManager       - 2PC transaction lifecycle
        - validate_operation_data  - operation-type validation
    """

    def __init__(
        self, name: str, domain_type: str = "generic", metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Initialize a domain chain.
    
        Args:
            name: Name identifier for the chain
            domain_type: Type of domain this chain handles
            metadata: Additional metadata for the chain
        """
        super().__init__(name, domain_type)
        
        # Store metadata if provided
        self.metadata = metadata or {}
        
        # Add domain-specific business rules
        self._setup_default_business_rules()
    
        # Track domain-specific metrics
        self._metrics = OperationMetricsTracker()

        # 2PC transaction manager
        self._tx_manager = TransactionManager()

    # -- backward-compatible properties --------------------------------

    @property
    def operation_metrics(self) -> dict[str, int]:
        """Backward-compatible dict view of operation metrics."""
        return self._metrics.copy()

    @property
    def pending_transactions(self) -> dict[str, dict[str, Any]]:
        """Read-only access to pending transactions."""
        return self._tx_manager.pending_transactions

    @property
    def _pending_transactions(self) -> dict[str, dict[str, Any]]:
        """Backward-compatible access to pending transactions."""
        return self._tx_manager.pending_transactions

    # -- business rules ------------------------------------------------

    def _setup_default_business_rules(self) -> None:
        """Setup default business rules for the domain chain."""
    
        def entity_must_be_registered(
            entity_info: dict[str, Any], _operation: str
        ) -> bool:
            """Rule: Entity must be registered before operations."""
            return entity_info.get("status") != "unregistered"
    
        def no_concurrent_operations(
            entity_info: dict[str, Any], _operation: str
        ) -> bool:
            """Rule: No concurrent operations on same entity."""
            return entity_info.get("current_operation") is None
    
        def quality_check_before_approval(
            entity_info: dict[str, Any], operation: str
        ) -> bool:
            """Rule: Quality check must pass before approval."""
            if operation.startswith("approval"):
                last_qc = entity_info.get("last_quality_check", {})
                return last_qc.get("result") == "passed"
            return True

        self.add_domain_rule("entity_registered", entity_must_be_registered)
        self.add_domain_rule("no_concurrent_ops", no_concurrent_operations)
        self.add_domain_rule("quality_before_approval", quality_check_before_approval)

    def start_domain_operation(
        self,
        entity_id: str,
        operation_type: str,
        details: dict[str, Any] | None = None
    ) -> bool:
        """
        Start a domain-specific operation with validation.
    
        Args:
            entity_id: Entity identifier (used as metadata)
            operation_type: Type of operation to start
            details: Additional operation details
        
        Returns:
            True if operation was started successfully
        """
        # Validate domain rules
        if not self.validate_domain_rules(entity_id, f"start_{operation_type}"):
            return False

        operation_data = details or {}
        if not self.validate_domain_operation(
            entity_id, operation_type, operation_data
        ):
            return False

        success = self.start_operation(entity_id, operation_type, details)
        if success:
            self._metrics.record_operation_started()
        return success

    def complete_domain_operation(
        self,
        entity_id: str,
        operation_type: str,
        result: dict[str, Any] | None = None
    ) -> bool:
        """
        Complete a domain-specific operation with result tracking.
    
        Args:
            entity_id: Entity identifier (used as metadata)
            operation_type: Type of operation to complete
            result: Operation result data
        
        Returns:
            True if operation was completed successfully
        """
        success = self.complete_operation(entity_id, operation_type, result)
        if success:
            op_ok = result and result.get("success", True)
            self._metrics.record_operation_result(bool(op_ok))
        return success

    # -- resource allocation -------------------------------------------

    def allocate_resource(
        self,
        entity_id: str,
        resource_type: str,
        resource_id: str,
        allocation_type: str = "assigned",
        details: dict[str, Any] | None = None
    ) -> bool:
        """
        Allocate a resource to an entity.
    
        Args:
            entity_id: Entity identifier (used as metadata)
            resource_type: Type of resource being allocated
            resource_id: Identifier of the specific resource
            allocation_type: Type of allocation
            details: Additional allocation details
        
        Returns:
            True if resource was allocated successfully
        """
        event = create_resource_allocation(
            entity_id=entity_id,
            resource_type=resource_type,
            resource_id=resource_id,
            allocation_type=allocation_type,
            domain_type=self.domain_type,
            details=details
        )
        return self.add_domain_event(event)

    # -- quality checks ------------------------------------------------

    def perform_quality_check(
        self,
        entity_id: str,
        check_type: str,
        check_result: str,
        inspector_id: str | None = None,
        details: dict[str, Any] | None = None
    ) -> bool:
        """
        Perform a quality check on an entity.
    
        Args:
            entity_id: Entity identifier (used as metadata)
            check_type: Type of quality check performed
            check_result: Result (passed, failed, pending)
            inspector_id: Identifier of the inspector
            details: Additional check details
        
        Returns:
            True if quality check was recorded successfully
        """
        event = create_quality_check(
            entity_id=entity_id,
            check_type=check_type,
            check_result=check_result,
            inspector_id=inspector_id,
            domain_type=self.domain_type,
            details=details
        )
        success = self.add_domain_event(event)
        if success:
            self._metrics.record_quality_result(check_result)
        return success

    # -- status updates ------------------------------------------------

    def update_entity_status(
        self,
        entity_id: str,
        status: str,
        details: dict[str, Any] | None = None,
        reason: str | None = None
    ) -> bool:
        """
        Update the status of an entity.
    
        Args:
            entity_id: Entity identifier (used as metadata)
            status: New status for the entity
            details: Additional status details
            reason: Reason for the status change
        
        Returns:
            True if status was updated successfully
        """
        entity_info = self.get_entity_info(entity_id)
        if not entity_info:
            return False
    
        old_status = entity_info.get("status", "unknown")
        event = create_status_update(
            entity_id=entity_id,
            old_status=old_status,
            new_status=status,
            reason=reason,
            details=details
        )
        return self.add_domain_event(event)

    # -- approvals -----------------------------------------------------

    def process_approval(
        self,
        entity_id: str,
        approval_type: str,
        approval_status: str,
        approver_id: str,
        details: dict[str, Any] | None = None
    ) -> bool:
        """
        Process an approval for an entity.

        Args:
            entity_id: Entity identifier (used as metadata)
            approval_type: Type of approval being processed
            approval_status: Status (approved, rejected, pending)
            approver_id: Identifier of the approver
            details: Additional approval details

        Returns:
            True if approval was processed successfully
        """
        if not self.validate_domain_rules(entity_id, f"approval_{approval_type}"):
            return False

        event = create_approval(
            entity_id=entity_id,
            approval_type=approval_type,
            approval_status=approval_status,
            approver_id=approver_id,
            domain_type=self.domain_type,
            details=details
        )
        success = self.add_domain_event(event)
        if success:
            self._metrics.record_approval_result(approval_status)
        return success

    # -- compliance ----------------------------------------------------

    def check_compliance(
        self,
        entity_id: str,
        compliance_type: str,
        compliance_status: str,
        regulation_reference: str | None = None,
        details: dict[str, Any] | None = None
    ) -> bool:
        """
        Check compliance for an entity.
    
        Args:
            entity_id: Entity identifier (used as metadata)
            compliance_type: Type of compliance being tracked
            compliance_status: Status (compliant, non_compliant)
            regulation_reference: Reference to regulation
            details: Additional compliance details
        
        Returns:
            True if compliance check was recorded successfully
        """
        event = create_compliance_check(
            entity_id=entity_id,
            compliance_type=compliance_type,
            compliance_status=compliance_status,
            regulation_reference=regulation_reference,
            domain_type=self.domain_type,
            details=details
        )
        success = self.add_domain_event(event)
        if success:
            self._metrics.record_compliance_result(compliance_status)
        return success

    # -- validation ----------------------------------------------------

    def validate_domain_operation(
        self,
        entity_id: str,
        operation_type: str,
        operation_data: dict[str, Any]
    ) -> bool:
        """
        Validate a domain-specific operation.
    
        Args:
            entity_id: Entity identifier
            operation_type: Type of operation
            operation_data: Operation data
        
        Returns:
            True if operation is valid for this domain
        """
        if not self.get_entity_info(entity_id):
            return False
        return validate_operation_data(operation_type, operation_data)

    # -- statistics / reports ------------------------------------------

    def get_domain_statistics(self) -> dict[str, Any]:
        """
        Get domain-specific statistics.
    
        Returns:
            Domain-specific statistics
        """
        base_stats = self.get_base_domain_statistics()
        base_stats.update({
            "operation_metrics": self._metrics.copy(),
            "success_rate": self._metrics.success_rate,
            "quality_pass_rate": self._metrics.quality_pass_rate,
            "approval_rate": self._metrics.approval_rate,
        })
        return base_stats

    def _get_compliance_events(self, entity_id: str) -> list[dict[str, Any]]:
        """Filter compliance check events for a specific entity."""
        compliance_events: list[dict[str, Any]] = []
        for block in self.chain:
            events = (
                block.to_event_list()
                if hasattr(block, 'to_event_list')
                else block.events
            )
            for event in events:
                if (
                    event.get("entity_id") == entity_id and
                    event.get("event") == "compliance_check"
                ):
                    compliance_events.append(event)
        return compliance_events

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
    
        compliance_events = self._get_compliance_events(entity_id)
        compliance_types = _analyze_compliance_status(compliance_events)
    
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
            ),
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
        stats = _calculate_performance_stats(entity_events)
    
        return {
            "entity_id": entity_id,
            "domain_type": self.domain_type,
            "operations_started": stats["started"],
            "operations_completed": stats["completed"],
            "completion_rate": _safe_ratio(stats["completed"], stats["started"]),
            "quality_checks": stats["quality_total"],
            "quality_pass_rate": (
                _safe_ratio(stats["quality_passed"], stats["quality_total"])
            ),
            "approvals_requested": stats["approvals_total"],
            "approval_rate": (
                _safe_ratio(stats["approvals_granted"], stats["approvals_total"])
            ),
            "total_events": len(entity_events),
        }

    # -- 2PC transaction methods (delegates to TransactionManager) -----

    def prepare_transaction(
        self,
        transaction_id: str,
        payload: dict[str, Any],
        is_source: bool = True
    ) -> bool:
        """
        Phase 1: Prepare for a cross-chain transaction.
    
        Args:
            transaction_id: Unique transaction identifier.
            payload: Transaction details.
            is_source: True if this is the source chain.

        Returns:
            True if prepared successfully.
        """
        if self._tx_manager.is_prepared(transaction_id):
            return True

        entity_id = payload.get("entity_id")
        if not isinstance(entity_id, str):
            return False
        
        operation_type = payload.get("operation_type")
        if not isinstance(operation_type, str):
            return False
            
        details = payload.get("details", {})

        if not self._validate_transaction_payload(entity_id, operation_type, details):
            return False

        self._tx_manager.store_pending(transaction_id, payload, is_source)
        return True

    def _validate_transaction_payload(
        self,
        entity_id: str,
        operation_type: str,
        details: dict[str, Any],
    ) -> bool:
        """Validate domain rules and operation data for a 2PC prepare."""
        validation_op = f"prepare_{operation_type}"
        if not self.validate_domain_rules(entity_id, validation_op):
            return False
        return self.validate_domain_operation(entity_id, operation_type, details)

    def commit_transaction(self, transaction_id: str) -> bool:
        """
        Phase 2: Commit the transaction.
    
        Args:
            transaction_id: Transaction ID to commit.
        
        Returns:
            True if committed successfully.
        """
        pending_data = self._tx_manager.pop_pending(transaction_id)
        if pending_data is None:
            return False

        return self._execute_commit(transaction_id, pending_data)

    def _execute_commit(
        self, transaction_id: str, pending_data: dict[str, Any]
    ) -> bool:
        """Execute the on-chain operations for a 2PC commit."""
        payload = pending_data["payload"]
        entity_id = payload.get("entity_id")
        operation_type = payload.get("operation_type")
        details = payload.get("details", {})
    
        try:
            success = self.start_domain_operation(entity_id, operation_type, details)
            if not success:
                return False

            self.complete_domain_operation(
                entity_id,
                operation_type,
                {
                    "status": "committed",
                    "tx_id": transaction_id,
                },
            )
            return True
        except (KeyError, ValueError, AttributeError, TypeError):
            return False

    def rollback_transaction(self, transaction_id: str) -> bool:
        """
        Phase 2 (Alternative): Rollback the transaction.
    
        Args:
            transaction_id: Transaction ID to rollback.
        
        Returns:
            True if rolled back successfully.
        """
        return self._tx_manager.rollback(transaction_id)

    # -- string representations ----------------------------------------

    def __str__(self) -> str:
        """String representation of the domain chain."""
        return (
            f"DomainChain(name={self.name}, "
            f"domain={self.domain_type}, "
            f"entities={len(self.entity_registry)}, "
            f"operations={self.operation_metrics['total_operations']})"
        )
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"DomainChain(name={self.name}, "
            f"domain_type={self.domain_type}, "
            f"entities={len(self.entity_registry)}, "
            f"blocks={len(self.chain)}, "
            f"total_operations="
            f"{self._metrics['total_operations']}, "
            f"success_rate="
            f"{self._metrics.success_rate:.2f})"
        )
