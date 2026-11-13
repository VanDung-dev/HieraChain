from typing import Any, Protocol, runtime_checkable

from hierachain.core.blockchain import Blockchain


@runtime_checkable
class LedgerStorage(Protocol):
    def store_chain(self, chain: Blockchain) -> bool: ...

    def load_chain(self, chain_name: str) -> dict[str, Any] | None: ...

    def list_chains(self) -> list[dict[str, Any]]: ...

    def store_proof(
        self,
        main_chain_name: str,
        sub_chain_name: str,
        proof_hash: str,
        block_index: int,
        metadata: dict[str, Any],
    ) -> bool: ...

    def get_proof_history(self, sub_chain_name: str) -> list[dict[str, Any]]: ...

    def get_entity_events(
        self, entity_id: str, chain_name: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def get_events_by_type(
        self, event_type: str, chain_name: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def get_chain_statistics(self, chain_name: str) -> dict[str, Any]: ...

    def cleanup_old_data(self, days_to_keep: int = 30) -> bool: ...

    def close(self) -> None: ...
