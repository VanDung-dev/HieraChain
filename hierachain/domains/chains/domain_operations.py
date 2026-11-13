"""Domain business-operation behavior for :class:`DomainChain`.

The methods are kept in a mixin so ``DomainChain`` stays a thin composition
root while the public API remains unchanged.
"""

import logging
from typing import Any

from hierachain.core.utils import get_block_events as _get_block_events
from hierachain.domains.chains.base_chain import BaseChain
from hierachain.domains.chains.metrics import OperationMetricsTracker
from hierachain.domains.chains.operation_validation import validate_operation_data
from hierachain.domains.events.event_creators import (
    create_approval,
    create_quality_check,
    create_resource_allocation,
    create_status_update,
)

logger = logging.getLogger(__name__)


class DomainOperationsMixin(BaseChain):
    """Business operations, validation and statistics for a domain chain."""

    _metrics: OperationMetricsTracker

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
        details: dict[str, Any] | None = None,
        transaction_id: str | None = None,
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
        with self.lock:
            if not self.validate_domain_rules(
                entity_id, f"start_{operation_type}"
            ):
                return False

            operation_data = details or {}
            if not self.validate_domain_operation(
                entity_id, operation_type, operation_data
            ):
                return False

            success = self.start_operation(
                entity_id, operation_type, details, transaction_id=transaction_id
            )
            if success:
                self._metrics.record_operation_started()
            return success

    def complete_domain_operation(
        self,
        entity_id: str,
        operation_type: str,
        result: dict[str, Any] | None = None,
        transaction_id: str | None = None,
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
        success = self.complete_operation(
            entity_id, operation_type, result, transaction_id=transaction_id
        )
        if success:
            op_ok = result and result.get("success", True)
            self._metrics.record_operation_result(bool(op_ok))
        return success

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
        with self.lock:
            entity_info = self.get_entity_info(entity_id)
            if not entity_info:
                return False

            old_status = entity_info.get("status", "unknown")
            event = create_status_update(
                entity_id=entity_id,
                old_status=old_status,
                new_status=status,
                reason=reason,
                domain_type=self.domain_type,
                details=self._status_update_details(
                    old_status, status, reason, details
                ),
            )
            return self.add_domain_event(event)

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
        with self.lock:
            if not self.validate_domain_rules(
                entity_id, f"approval_{approval_type}"
            ):
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
            for event in _get_block_events(block):
                if (
                    event.get("entity_id") == entity_id and
                    event.get("event") == "compliance_check"
                ):
                    compliance_events.append(event)
        return compliance_events
