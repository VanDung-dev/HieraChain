"""
Domain Chain implementation for HieraChain Ledger.

This module provides a concrete implementation of BaseChain that can be used
directly for common business scenarios or as a reference for creating
custom domain-specific chains.

Behavior is composed from responsibility-specific mixins:
    - ``DomainOperationsMixin``    - business operations and statistics
    - ``TransactionOperationsMixin`` - 2PC participant lifecycle
    - ``OperationMetricsTracker``  - recording & querying metrics
    - ``TransactionManager``       - pending 2PC state
"""

import threading
from typing import Any

from hierachain.domains.chains.base_chain import BaseChain
from hierachain.domains.chains.domain_operations import DomainOperationsMixin
from hierachain.domains.chains.metrics import OperationMetricsTracker
from hierachain.domains.chains.operation_validation import validate_operation_data
from hierachain.domains.chains.transaction_operations import TransactionOperationsMixin
from hierachain.domains.chains.tx_manager import TransactionManager

__all__ = ["DomainChain", "validate_operation_data"]


class DomainChain(DomainOperationsMixin, TransactionOperationsMixin, BaseChain):
    """
    Concrete domain chain implementation for general business operations.

    This class provides a ready-to-use domain chain that handles common
    business operations while following Ledger guidelines. It can be
    used directly or extended for specific domain requirements.
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
        self._tx_commit_lock = threading.RLock()
        self._transaction_event_markers: dict[
            tuple[str, str], dict[str, Any] | None
        ] | None = None

        # Replay domain projections only after this class has initialized its
        # state. Derived classes with additional deterministic projections can
        # register handlers and call rebuild_domain_state() once initialized.
        self.rebuild_domain_state()

    # -- backward-compatible properties --------------------------------

    @property
    def operation_metrics(self) -> dict[str, int]:
        """Backward-compatible dict view of operation metrics."""
        return self._metrics.copy()

    @property
    def pending_transactions(self) -> dict[str, dict[str, Any]]:
        """Read-only access to pending transactions."""
        return self._tx_manager.pending_transactions

    # -- string representations ----------------------------------------

    def __str__(self) -> str:
        """String representation of the domain chain."""
        return (
            f"DomainChain(name={self.name}, "
            f"domain={self.domain_type}, "
            f"entities={len(self.entity_registry)}, "
            f"operations={self._metrics['total_operations']})"
        )

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"DomainChain(name={self.name}, "
            f"domain_type={self.domain_type}, "
            f"entities={len(self.entity_registry)}, "
            f"blocks={len(self.chain)}, "
            f"total_operations={self._metrics['total_operations']}, "
            f"success_rate={self._metrics.success_rate:.2f})"
        )
