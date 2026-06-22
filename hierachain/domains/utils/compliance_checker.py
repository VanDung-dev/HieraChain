"""
Compliance checker for HieraChain domains.
"""

import time
from typing import Any, Callable
from hierachain.hierarchical.hierarchy_manager import HierarchyManager


def _try_extract_pyarrow_events(events_obj: Any) -> list[dict[str, Any]] | None:
    """Attempt to extract events using PyArrow method."""
    if hasattr(events_obj, "to_pylist"):
        try:
            raw_events = events_obj.to_pylist()
            return [
                ev.as_py() if hasattr(ev, "as_py") and not isinstance(ev, dict) else ev
                for ev in raw_events
            ]
        except (AttributeError, TypeError, ValueError):
            pass
    return None


def _extract_events_manually(events_obj: Any) -> list[dict[str, Any]]:
    """Extract events from a block manually (fallback)."""
    events_list: list[dict[str, Any]] = []
    try:
        for event in events_obj:
            if hasattr(event, "as_py"):
                event = event.as_py()
            events_list.append(event)
    except (AttributeError, TypeError, ValueError):
        try:
            events_list = list(events_obj)
        except (TypeError, ValueError):
            events_list = []
    return events_list


def _get_block_events(block: Any) -> list[dict[str, Any]]:
    """Extract events from a block."""
    if isinstance(block.events, list):
        return block.events

    pyarrow_events = _try_extract_pyarrow_events(block.events)
    if pyarrow_events is not None:
        return pyarrow_events

    return _extract_events_manually(block.events)


class ComplianceChecker:
    """Checks Ledger guideline compliance across chains."""

    def __init__(
        self,
        hierarchy_manager: HierarchyManager,
        validation_rules: dict[str, Callable],
    ):
        self._hm = hierarchy_manager
        self._rules = validation_rules

    def validate(self) -> dict[str, Any]:
        """Check all chains for Ledger compliance."""
        results: dict[str, Any] = {
            "timestamp": time.time(),
            "chains_checked": 0,
            "compliant_chains": 0,
            "violations": [],
            "overall_compliant": True,
        }

        self._check_single_chain(self._hm.main_chain, "MainChain", results)

        for name, sub in self._hm.sub_chains.items():
            self._check_single_chain(sub, name, results,)

        results["overall_compliant"] = (len(results["violations"]) == 0)
        return results

    # -- internals -------------------------------------------------

    def _check_single_chain(
        self,
        chain: Any,
        chain_name: str,
        results: dict[str, Any],
    ) -> None:
        """Check one chain and update *results*."""
        violations = self._collect_violations(chain, chain_name)
        results["violations"].extend(violations)
        results["chains_checked"] += 1
        if not violations:
            results["compliant_chains"] += 1

    def _collect_violations(self, chain: Any, chain_name: str) -> list[dict[str, Any]]:
        """Collect Ledger compliance violations."""
        violations: list[dict[str, Any]] = []
        for block in chain.chain:
            if (
                not isinstance(block.events, list) and
                not hasattr(block.events, "to_pylist")
            ):
                violations.append({
                    "type": "invalid_block_structure",
                    "chain_name": chain_name,
                    "block_index": block.index,
                    "issue": "Block events should be a list or PyArrow object",
                })

            events = _get_block_events(block)
            for event in events:
                self._check_event(event, chain_name, block.index, violations)
        return violations

    def _check_event(
        self,
        event: dict[str, Any],
        chain_name: str,
        block_index: int,
        violations: list[dict[str, Any]],
    ) -> None:
        """Check a single event for violations."""
        crypto_rule = self._rules["no_cryptocurrency_terms"]
        if not crypto_rule(event):
            violations.append({
                "type": "cryptocurrency_terms",
                "chain_name": chain_name,
                "block_index": block_index,
                "event": event,
                "issue": "Event contains forbidden cryptocurrency terminology",
            })

        if event.get("entity_id") is not None:
            entity_rule = self._rules["entity_id_metadata_usage"]
            if not entity_rule(event):
                violations.append({
                    "type": "entity_id_misuse",
                    "chain_name": chain_name,
                    "block_index": block_index,
                    "event": event,
                    "issue": "entity_id should be used as metadata field",
                })
