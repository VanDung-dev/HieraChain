from __future__ import annotations

import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from hierachain.hierarchical.hierarchy_manager.contracts import HierarchyHost

if TYPE_CHECKING:
    from hierachain.domains.chains.domain_chain import DomainChain

logger = logging.getLogger(__name__)


class ChainOperationsMixin(HierarchyHost):
    def create_sub_chain(
        self, name: str, domain_type: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        existing = self.sub_chains.get(name)
        if existing is not None and (
            callable(getattr(existing, "prepare_transaction", None))
            or getattr(existing, "domain_type", None) != domain_type
        ):
            return False

        from hierachain.domains.chains.domain_chain import DomainChain

        sub_chain = DomainChain(name, domain_type, metadata=metadata)

        try:
            if existing is None:
                self.add_sub_chain(name, sub_chain)
            else:
                self._replace_sub_chain_placeholder(name, existing, sub_chain)
        except Exception:
            sub_chain.shutdown()
            raise

        return True

    def _replace_sub_chain_placeholder(self, name: str, placeholder: Any, chain: DomainChain) -> None:
        """Replace a restored generic chain with its concrete DomainChain participant."""
        # Keep the placeholder running until its replacement is connected. Rewriting
        # existing chain metadata here could delete SQLite block rows via REPLACE.
        if not chain.connect_to_main_chain(self.main_chain):
            raise RuntimeError(f"Failed to connect sub-chain to main chain: {name}")

        self.sub_chains[name] = chain
        if self.cross_level_sync:
            self.cross_level_sync.connect_subchain(name, chain)

        try:
            placeholder.shutdown()
        except Exception:
            logger.exception("Could not shut down replaced sub-chain placeholder %s", name)

        self.transaction_manager.retry_pending()

    def add_sub_chain(self, chain_name, sub_chain, *, persist: bool = True):
        with self._registry_lock:
            if chain_name in self.sub_chains:
                raise ValueError(f"Sub-chain {chain_name} already exists")

            if hasattr(sub_chain, "auto_proof_submission"):
                sub_chain.auto_proof_submission = self.auto_proof_submission
                sub_chain.proof_submission_interval = self.proof_submission_interval

            main_chain = self.main_chain
            registered_before = chain_name in main_chain.registered_sub_chains
            pending_before = deepcopy(main_chain.pending_events)
            previous_connection = getattr(
                sub_chain, "main_chain_connection", None
            )
            sync_before = (
                getattr(self.cross_level_sync, "_subchains", {}).get(chain_name)
                if self.cross_level_sync
                else None
            )
            try:
                connected = sub_chain.connect_to_main_chain(main_chain)
            except Exception:
                self._rollback_new_main_chain_registration(
                    chain_name,
                    sub_chain,
                    registered_before,
                    pending_before,
                    previous_connection,
                )
                raise
            if not connected:
                self._rollback_new_main_chain_registration(
                    chain_name,
                    sub_chain,
                    registered_before,
                    pending_before,
                    previous_connection,
                )
                raise RuntimeError(
                    f"Failed to connect sub-chain to main chain: {chain_name}"
                )

            persist_attempted = False
            try:
                if self.cross_level_sync:
                    self.cross_level_sync.connect_subchain(chain_name, sub_chain)
                if persist and self.storage is not None:
                    persist_attempted = True
                    if self.storage.store_chain(sub_chain) is not True:
                        self._rollback_new_main_chain_registration(
                            chain_name,
                            sub_chain,
                            registered_before,
                            pending_before,
                            previous_connection,
                        )
                        self._restore_cross_level_registration(chain_name, sync_before)
                        raise RuntimeError(
                            f"Failed to persist sub-chain metadata: {chain_name}"
                        )
                self.sub_chains[chain_name] = sub_chain
            except Exception:
                if self.sub_chains.get(chain_name) is sub_chain:
                    del self.sub_chains[chain_name]
                self._restore_cross_level_registration(chain_name, sync_before)
                if not persist_attempted:
                    self._rollback_new_main_chain_registration(
                        chain_name,
                        sub_chain,
                        registered_before,
                        pending_before,
                        previous_connection,
                    )
                raise

        # A participant retry failure does not invalidate the successfully
        # connected and persisted sub-chain registration.
        try:
            self.transaction_manager.retry_pending()
        except Exception:
            logger.exception(
                "Sub-chain %s was registered, but pending transaction retries failed",
                chain_name,
            )

    def _restore_cross_level_registration(
        self, chain_name: str, previous: Any | None
    ) -> None:
        """Restore the cross-level mapping after a pre-commit registration failure."""
        if not self.cross_level_sync:
            return
        try:
            if previous is None:
                disconnect = getattr(
                    self.cross_level_sync, "disconnect_subchain", None
                )
                if callable(disconnect):
                    disconnect(chain_name)
            else:
                self.cross_level_sync.connect_subchain(chain_name, previous)
        except Exception:
            logger.exception(
                "Could not restore cross-level registration for %s", chain_name
            )

    def _rollback_new_main_chain_registration(
        self,
        chain_name: str,
        sub_chain: Any,
        registered_before: bool,
        pending_before: list[dict[str, Any]],
        previous_connection: Any | None,
    ) -> None:
        """Undo an unpersisted registration that is still only pending in memory."""
        if registered_before:
            return

        main_chain = self.main_chain
        with main_chain.lock:
            from hierachain.core.utils import get_block_events

            for block in main_chain.chain:
                if any(
                    event.get("event") == "sub_chain_registration"
                    and event.get("entity_id") == chain_name
                    for event in get_block_events(block)
                ):
                    # A concurrent finalization made this registration durable.
                    return

            main_chain.registered_sub_chains.discard(chain_name)
            main_chain.sub_chain_metadata.pop(chain_name, None)
            remove_authority = getattr(main_chain.consensus, "remove_authority", None)
            if callable(remove_authority):
                remove_authority(chain_name)

            new_pending = [
                event
                for event in main_chain.pending_events
                if event not in pending_before
                and event.get("event") == "sub_chain_registration"
                and event.get("entity_id") == chain_name
            ]
            if new_pending:
                main_chain.pending_events[:] = [
                    event
                    for event in main_chain.pending_events
                    if event not in new_pending
                ]
            if getattr(sub_chain, "main_chain_connection", None) is main_chain:
                sub_chain.main_chain_connection = previous_connection
