from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hierachain.hierarchical.channel import Channel
from hierachain.hierarchical.hierarchy_manager import recovery, registry
from hierachain.hierarchical.hierarchy_manager.contracts import HierarchyHost


class StateOperationsMixin(HierarchyHost):
    def _restore_main_chain(self) -> None:
        return recovery._restore_main_chain(self)

    def _hierarchy_registry_snapshot(self) -> dict[str, Any]:
        return registry._hierarchy_registry_snapshot(self)

    def _persist_hierarchy_registry(self) -> bool:
        return registry._persist_hierarchy_registry(self)

    def _restore_hierarchy_registry(self) -> None:
        return registry._restore_hierarchy_registry(self)

    def _channel_registry_revision(self) -> str | None:
        return (self._registry_state or {}).get("_revision")

    def _bind_channel_ledger(self, channel: Channel) -> None:
        channel.ledger._lock = self._registry_lock
        if self.storage is not None:
            channel.ledger.bind_storage(self.storage, self._channel_registry_revision)

    def _apply_hierarchy_registry(self, state: dict[str, Any]) -> None:
        return registry._apply_hierarchy_registry(self, state)

    def _mutate_registry(self, change: Callable[[], Any], failure_message: str) -> Any:
        return registry._mutate_registry(self, change, failure_message)

    def _restore_sub_chains(self) -> None:
        return recovery._restore_sub_chains(self)
