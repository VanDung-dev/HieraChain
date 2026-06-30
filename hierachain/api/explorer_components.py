"""
Explorer Components for HieraChain Ledger

Each class provides a distinct visualization / analysis component
for the Blockchain Explorer dashboard.
"""

import time
import logging
from typing import Any
from dataclasses import dataclass, field

from hierachain.api.storage.explorer_helpers import (
    format_event_for_display,
)


class ExplorerError(Exception):
    pass


@dataclass
class ComponentConfig:
    title: str
    enabled: bool = True
    filters: dict[str, Any] = field(default_factory=dict)


class ChainOverviewComponent:
    def __init__(self, chain: Any):
        self.chain = chain
        self.logger = logging.getLogger(__name__)

    def render_summary(self) -> dict[str, Any]:
        try:
            return {
                "main_chain": self._get_main_chain_stats(),
                "sub_chains": self._get_sub_chain_stats(),
                "recent_activity": self._get_recent_activity()
            }
        except Exception as e:
            self.logger.error(f"ChainOverviewComponent render_summary error: {e}")
            return {"error": "An internal error occurred"}

    def _get_main_chain_stats(self) -> dict[str, Any]:
        if hasattr(self.chain, 'main_chain'):
            chain = self.chain.main_chain
            total_events = getattr(
                chain, 'total_events', sum(len(block.events) for block in chain.chain)
            )
            return {
                "block_count": len(chain.chain),
                "latest_block": chain.chain[-1].index if chain.chain else 0,
                "total_events": total_events
            }
        return {"error": "Main chain not found"}

    def _get_sub_chain_stats(self) -> list[dict[str, Any]]:
        if hasattr(self.chain, 'sub_chains'):
            stats = []
            for name, sub_chain in self.chain.sub_chains.items():
                total_events = getattr(
                    sub_chain, 'total_events',
                    sum(len(block.events) for block in sub_chain.chain)
                )
                stats.append({
                    "name": name,
                    "block_count": len(sub_chain.chain),
                    "events": total_events
                })
            return stats
        return []

    def _get_recent_activity(self) -> list[dict[str, Any]]:
        activities = []
        if hasattr(self.chain, 'main_chain') and self.chain.main_chain.chain:
            latest_blocks = self.chain.main_chain.chain[-5:]
            for block in latest_blocks:
                activities.append({
                    "type": "block_created",
                    "chain": "main",
                    "block_index": block.index,
                    "timestamp": getattr(block, 'timestamp', time.time()),
                    "events_count": len(block.events)
                })
        return sorted(activities, key=lambda x: x.get('timestamp', 0), reverse=True)


class EntityTracerComponent:
    def __init__(self, chain: Any):
        self.chain = chain
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def render_input_form() -> dict[str, Any]:
        return {
            "type": "form",
            "fields": [
                {
                    "name": "entity_id",
                    "type": "text",
                    "placeholder": "Enter entity ID to trace",
                    "required": True
                },
                {
                    "name": "chain_type",
                    "type": "select",
                    "options": ["all", "main", "sub"],
                    "default": "all"
                }
            ],
            "submit_endpoint": "/api/ledger/trace_entity"
        }

    def trace_entity(
        self,
        entity_id: str,
        chain_type: str = "all",
        resolve_cid: bool = False
    ) -> dict[str, Any]:
        try:
            events = []

            if chain_type in ["all", "main"] and hasattr(self.chain, 'main_chain'):
                main_events = self._search_main_chain(
                    entity_id, resolve_cid=resolve_cid
                )
                events.extend(main_events)

            if chain_type in ["all", "sub"] and hasattr(self.chain, 'sub_chains'):
                sub_events = self._search_sub_chains(
                    entity_id, resolve_cid=resolve_cid
                )
                events.extend(sub_events)

            events.sort(key=lambda x: x.get('timestamp', 0))

            return {
                "entity_id": entity_id,
                "total_events": len(events),
                "events": events,
                "chains_found": list(set(e['chain'] for e in events)),
                "resolved": resolve_cid
            }
        except Exception as e:
            self.logger.error(f"EntityTracerComponent trace_entity error: {e}")
            return {"error": "An internal error occurred"}

    def _search_main_chain(
        self,
        entity_id: str,
        resolve_cid: bool = False
    ) -> list[dict[str, Any]]:
        if not hasattr(self.chain, 'main_chain'):
            return []

        indexed_events = self.chain.main_chain.get_indexed_entity_events(entity_id)
        result = []
        for e in indexed_events:
            ev = e.get("event", {})
            formatted_ev = format_event_for_display(ev, resolve_cid=resolve_cid)
            ts = ev.get("timestamp") if isinstance(ev, dict) else 0
            result.append({
                "chain": "main_chain",
                "block_index": e.get("block_index", 0),
                "event": formatted_ev,
                "timestamp": ts or 0
            })
        return result

    def _search_sub_chains(
        self,
        entity_id: str,
        resolve_cid: bool = False
    ) -> list[dict[str, Any]]:
        events = []
        if not hasattr(self.chain, 'sub_chains'):
            return []

        for chain_name, sub_chain in self.chain.sub_chains.items():
            indexed_events = sub_chain.get_indexed_entity_events(entity_id)
            for e in indexed_events:
                ev = e.get("event", {})
                formatted_ev = format_event_for_display(ev, resolve_cid=resolve_cid)
                ts = ev.get("timestamp") if isinstance(ev, dict) else 0
                events.append({
                    "chain": chain_name,
                    "block_index": e.get("block_index", 0),
                    "event": formatted_ev,
                    "timestamp": ts or 0
                })
        return events

    @staticmethod
    def _event_contains_entity(event: dict[str, Any], entity_id: str) -> bool:
        return (event.get("entity_id") == entity_id or
                entity_id in str(event.get("details", {})))


class EventAnalyticsComponent:
    def __init__(self, chain: Any) -> None:
        self.chain = chain
        self.logger = logging.getLogger(__name__)

    def render_summary(self) -> dict[str, Any]:
        try:
            return {
                "event_types": self._get_event_type_stats(),
                "activity_timeline": self._get_activity_timeline(),
                "chain_distribution": self._get_chain_distribution()
            }
        except Exception as e:
            self.logger.error(f"EventAnalyticsComponent render_summary error: {e}")
            return {"error": "An internal error occurred"}

    def _get_event_type_stats(self) -> dict[str, int]:
        stats = {}

        def merge_counts(chain_obj):
            counts = getattr(chain_obj, 'event_type_counts', {})
            for etype, count in counts.items():
                stats[etype] = stats.get(etype, 0) + count

        if hasattr(self.chain, 'main_chain'):
            merge_counts(self.chain.main_chain)

        if hasattr(self.chain, 'sub_chains'):
            for sub_chain in self.chain.sub_chains.values():
                merge_counts(sub_chain)

        return stats

    def _get_activity_timeline(self) -> list[dict[str, Any]]:
        timeline = []
        current_time = time.time()

        for hour in range(24):
            bucket_start = current_time - (hour + 1) * 3600
            bucket_end = current_time - hour * 3600

            count = self._count_events_in_timerange(bucket_start, bucket_end)
            timeline.append({
                "hour": 24 - hour - 1,
                "timestamp": bucket_start,
                "events": count
            })

        return timeline

    def _count_events_in_timerange(self, start: float, end: float) -> int:
        count = 0

        if hasattr(self.chain, 'main_chain'):
            for block in self.chain.main_chain.chain:
                block_time = getattr(block, 'timestamp', time.time())
                if start <= block_time <= end:
                    count += len(block.events)

        return count

    def _get_chain_distribution(self) -> dict[str, int]:
        distribution = {}

        if hasattr(self.chain, 'main_chain'):
            main_events = getattr(self.chain.main_chain, 'total_events', 0)
            distribution["main_chain"] = main_events

        if hasattr(self.chain, 'sub_chains'):
            for name, sub_chain in self.chain.sub_chains.items():
                sub_events = getattr(sub_chain, 'total_events', 0)
                distribution[name] = sub_events

        return distribution


class ProofVisualizerComponent:
    def __init__(self, chain: Any):
        self.chain = chain
        self.logger = logging.getLogger(__name__)

    def render_proof_flow(self) -> dict[str, Any]:
        try:
            return {
                "proof_submissions": self._get_proof_submissions(),
                "validation_status": self._get_validation_status(),
                "hierarchy_view": self._get_hierarchy_view()
            }
        except Exception as e:
            self.logger.error(f"ProofVisualizerComponent render_proof_flow error: {e}")
            return {"error": "An internal error occurred"}

    def _get_proof_submissions(self) -> list[dict[str, Any]]:
        if hasattr(self.chain, 'main_chain'):
            return getattr(self.chain.main_chain, 'recent_proofs', [])
        return []

    def _get_validation_status(self) -> dict[str, Any]:
        return {
            "total_proofs": self._count_total_proofs(),
            "recent_proofs": len(self._get_proof_submissions()),
            "validation_rate": 100.0
        }

    def _count_total_proofs(self) -> int:
        if hasattr(self.chain, 'main_chain'):
            return getattr(self.chain.main_chain, 'proof_count', 0)
        return 0

    def _get_hierarchy_view(self) -> dict[str, Any]:
        hierarchy: dict[str, Any] = {
            "main_chain": {
                "type": "main",
                "blocks": (
                    len(self.chain.main_chain.chain)
                    if hasattr(self.chain, 'main_chain') else 0
                ),
                "sub_chains": []
            }
        }

        if hasattr(self.chain, 'sub_chains'):
            for name, sub_chain in self.chain.sub_chains.items():
                hierarchy["main_chain"]["sub_chains"].append({
                    "name": name,
                    "type": "sub",
                    "blocks": len(sub_chain.chain),
                    "latest_proof": self._get_latest_proof_for_chain(name)
                })

        return hierarchy

    def _get_latest_proof_for_chain(self, chain_name: str) -> dict[str, Any] | None:
        if hasattr(self.chain, 'main_chain'):
            latest_proofs = getattr(self.chain.main_chain, 'latest_proofs', {})
            return latest_proofs.get(chain_name)
        return None
