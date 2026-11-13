"""Host contract shared by the responsibility-specific HierarchyManager mixins."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, Protocol


class HierarchyHost(Protocol):
    """Attributes and collaborators provided by the concrete composition root."""

    main_chain: Any
    sub_chains: dict[str, Any]
    system_started_at: float
    system_stats: dict[str, Any]
    cross_level_sync: Any
    organizations: dict[str, Any]
    channels: dict[str, Any]
    chain_access: dict[str, dict[str, list[str]]]
    private_collections: dict[str, Any]
    network: Any
    _registry_lock: threading.RLock
    _registry_mutating: bool
    _transaction_manager: Any

    @property
    def transaction_manager(self) -> Any: ...

    def _mutate_registry(
        self, change: Callable[[], Any], failure_message: str
    ) -> Any: ...

    def _restore_hierarchy_registry(self) -> None: ...

    def _persist_hierarchy_registry(self) -> bool: ...

    def get_sub_chain(self, name: str) -> Any: ...

    def submit_proof_to_main_chain(self, sub_chain_name: str) -> bool: ...
