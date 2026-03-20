"""
Blockchain Explorer for HieraChain Ledger

This module provides comprehensive blockchain exploration and visualization
capabilities for developer experience and data analysis.

IPFS Integration:
- Detects and displays off-chain data indicators
- Provides CID resolution UI
- Caches resolved data for performance
"""

import time
import logging
from typing import Any
from dataclasses import dataclass, field

from hierachain.api.storage.explorer_helpers import (
    format_event_for_display,
    get_explorer_css_styles,
    get_explorer_javascript
)


class ExplorerError(Exception):
    """Exception raised for explorer-related errors"""
    pass


@dataclass
class ComponentConfig:
    """Configuration for explorer components"""
    title: str
    enabled: bool = True
    refresh_interval: int = 5000
    max_items: int = 100
    filters: dict[str, Any] = field(default_factory=dict)


class BlockchainExplorer:
    """Integration with blockchain explorer for visualization and analysis"""
    
    def __init__(self, chain: Any, config: dict[str, Any] | None = None):
        """
        Initialize blockchain explorer
        
        Args:
            chain: The blockchain instance to explore
            config: Configuration for the explorer
        """
        self.chain = chain
        self.config = config or {}
        self.ui_components: dict[str, Any] = {}
        self.data_processors: dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
        self.register_default_components()
    
    def register_default_components(self):
        """Register default explorer components"""
        self.register_component(
            "chain_overview", 
            ChainOverviewComponent(self.chain)
        )
        self.register_component(
            "entity_tracer", 
            EntityTracerComponent(self.chain)
        )
        self.register_component(
            "event_analytics", 
            EventAnalyticsComponent(self.chain)
        )
        self.register_component(
            "proof_visualizer", 
            ProofVisualizerComponent(self.chain)
        )
    
    def register_component(self, component_id: str, component: Any):
        """Register a custom explorer component"""
        self.ui_components[component_id] = component
    
    def get_component(self, component_id: str) -> Any | None:
        """Get a registered component"""
        return self.ui_components.get(component_id)
    
    def render(self, component_id: str | None = None, **kwargs) -> dict[str, Any]:
        """
        Render explorer UI
        
        If component_id is None, renders the main dashboard
        """
        if component_id:
            component = self.get_component(component_id)
            if not component:
                raise ExplorerError(f"Component {component_id} not found")
            return component.render(**kwargs)
        
        # Render main dashboard
        return self._render_dashboard(**kwargs)
    
    def _render_dashboard(self, **kwargs) -> dict[str, Any]:
        """Render the main explorer dashboard"""
        # Use kwargs to customize the title if provided
        title = kwargs.get('title', 'HieraChain Explorer')

        # Use kwargs to filter elements if specified
        included_components = kwargs.get(
            'components', ['chain_overview', 'entity_tracer', 'event_analytics']
        )

        dashboard = {
            "title": title,
            "components": [],
            "assets": {
                "css": get_explorer_css_styles(),
                "js": get_explorer_javascript()
            }
        }

        if (
            'chain_overview' in included_components and
            'chain_overview' in self.ui_components
        ):
            dashboard["components"].append({
                "id": "chain_overview",
                "title": "Chain Overview",
                "content": self.ui_components["chain_overview"].render_summary()
            })

        if (
            'entity_tracer' in included_components and
            'entity_tracer' in self.ui_components
        ):
            dashboard["components"].append({
                "id": "entity_tracer",
                "title": "Entity Tracer",
                "content": self.ui_components["entity_tracer"].render_input_form()
            })

        if (
            'event_analytics' in included_components and
            'event_analytics' in self.ui_components
        ):
            dashboard["components"].append({
                "id": "event_analytics",
                "title": "Event Analytics",
                "content": self.ui_components["event_analytics"].render_summary()
            })

        return dashboard


class ChainOverviewComponent:
    """Component for chain overview"""
    
    def __init__(self, chain: Any):
        self.chain = chain
        self.logger = logging.getLogger(__name__)
    
    def render_summary(self) -> dict[str, Any]:
        """Render chain summary"""
        try:
            summary = {
                "main_chain": self._get_main_chain_stats(),
                "sub_chains": self._get_sub_chain_stats(),
                "recent_activity": self._get_recent_activity()
            }
            return summary
        except Exception as e:
            self.logger.error(f"ChainOverviewComponent render_summary error: {e}")
            return {"error": "An internal error occurred"}
    
    def _get_main_chain_stats(self) -> dict[str, Any]:
        """Get main chain statistics"""
        if hasattr(self.chain, 'main_chain'):
            chain = self.chain.main_chain
            # Use pre-calculated total_events for O(1) performance
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
        """Get sub-chain statistics"""
        if hasattr(self.chain, 'sub_chains'):
            stats = []
            for name, sub_chain in self.chain.sub_chains.items():
                # Use pre-calculated total_events for O(1) performance
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
        """Get recent blockchain activity"""
        activities = []
        # Add recent block activities
        if hasattr(self.chain, 'main_chain') and self.chain.main_chain.chain:
            latest_blocks = self.chain.main_chain.chain[-5:]  # Last 5 blocks
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
    """Component for entity tracing"""
    
    def __init__(self, chain: Any):
        self.chain = chain
        self.logger = logging.getLogger(__name__)
    
    @staticmethod
    def render_input_form() -> dict[str, Any]:
        """Render entity input form"""
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
            "submit_endpoint": "/api/v1/trace_entity"
        }
    
    def trace_entity(
        self,
        entity_id: str,
        chain_type: str = "all",
        resolve_cid: bool = False
    ) -> dict[str, Any]:
        """Trace entity across chains"""
        try:
            events = []
            
            # Search main chain
            if chain_type in ["all", "main"] and hasattr(self.chain, 'main_chain'):
                main_events = self._search_main_chain(
                    entity_id, resolve_cid=resolve_cid
                )
                events.extend(main_events)
            
            # Search sub-chains
            if chain_type in ["all", "sub"] and hasattr(self.chain, 'sub_chains'):
                sub_events = self._search_sub_chains(
                    entity_id, resolve_cid=resolve_cid
                )
                events.extend(sub_events)
            
            # Sort by timestamp
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
        """Search main chain for entity"""
        if not hasattr(self.chain, 'main_chain'):
            return []
            
        # Use indexed search for O(1) performance
        indexed_events = self.chain.main_chain.get_indexed_entity_events(entity_id)
        result = []
        for e in indexed_events:
            ev = e.get("event", {})
            # Format event for display (handles IPFS indicators)
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
        """Search sub-chains for entity"""
        events = []
        if not hasattr(self.chain, 'sub_chains'):
            return []
            
        for chain_name, sub_chain in self.chain.sub_chains.items():
            indexed_events = sub_chain.get_indexed_entity_events(entity_id)
            for e in indexed_events:
                ev = e.get("event", {})
                # Format event for display (handles IPFS indicators)
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
        """Check if event contains entity"""
        return (event.get("entity_id") == entity_id or
                entity_id in str(event.get("details", {})))


class EventAnalyticsComponent:
    """Component for event analytics"""
    
    def __init__(self, chain: Any) -> None:
        self.chain = chain
        self.logger = logging.getLogger(__name__)
    
    def render_summary(self) -> dict[str, Any]:
        """Render analytics summary"""
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
        """Get event type statistics"""
        stats = {}
        
        # Helper to merge counts
        def merge_counts(chain_obj):
            counts = getattr(chain_obj, 'event_type_counts', {})
            for etype, count in counts.items():
                stats[etype] = stats.get(etype, 0) + count

        # Analyze main chain
        if hasattr(self.chain, 'main_chain'):
            merge_counts(self.chain.main_chain)
        
        # Analyze sub-chains
        if hasattr(self.chain, 'sub_chains'):
            for sub_chain in self.chain.sub_chains.values():
                merge_counts(sub_chain)
        
        return stats
    
    def _get_activity_timeline(self) -> list[dict[str, Any]]:
        """Get activity timeline"""
        timeline = []
        current_time = time.time()
        
        # Create hourly buckets for last 24 hours
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
        """Count events in time range"""
        count = 0
        
        # Count main chain events
        if hasattr(self.chain, 'main_chain'):
            for block in self.chain.main_chain.chain:
                block_time = getattr(block, 'timestamp', time.time())
                if start <= block_time <= end:
                    count += len(block.events)
        
        return count
    
    def _get_chain_distribution(self) -> dict[str, int]:
        """Get event distribution by chain"""
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
    """Component for proof visualization"""
    
    def __init__(self, chain: Any):
        self.chain = chain
        self.logger = logging.getLogger(__name__)
    
    def render_proof_flow(self) -> dict[str, Any]:
        """Render proof submission flow"""
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
        """Get recent proof submissions"""
        if hasattr(self.chain, 'main_chain'):
            # Use pre-calculated recent proofs for O(1) performance
            return getattr(self.chain.main_chain, 'recent_proofs', [])
        return []
    
    def _get_validation_status(self) -> dict[str, Any]:
        """Get validation status"""
        return {
            "total_proofs": self._count_total_proofs(),
            "recent_proofs": len(self._get_proof_submissions()),
            "validation_rate": 100.0  # Simplified
        }
    
    def _count_total_proofs(self) -> int:
        """Count total proof submissions"""
        if hasattr(self.chain, 'main_chain'):
            return getattr(self.chain.main_chain, 'proof_count', 0)
        return 0
    
    def _get_hierarchy_view(self) -> dict[str, Any]:
        """Get hierarchical view of chains"""
        hierarchy = {
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
        """Get latest proof for specific chain"""
        if hasattr(self.chain, 'main_chain'):
            # Use pre-calculated latest proofs for O(1) performance
            latest_proofs = getattr(self.chain.main_chain, 'latest_proofs', {})
            return latest_proofs.get(chain_name)
        return None
