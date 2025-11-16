"""
Blockchain Explorer for Hierarchical Blockchain Framework

This module provides comprehensive blockchain exploration and visualization
capabilities for developer experience and data analysis.
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import logging


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
    filters: Dict[str, Any] = field(default_factory=dict)


class BlockchainExplorer:
    """Integration with blockchain explorer for visualization and analysis"""
    
    def __init__(self, chain: Any, config: Optional[Dict[str, Any]] = None):
        """
        Initialize blockchain explorer
        
        Args:
            chain: The blockchain instance to explore
            config: Configuration for the explorer
        """
        self.chain = chain
        self.config = config or {}
        self.ui_components: Dict[str, Any] = {}
        self.data_processors: Dict[str, Any] = {}
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
    
    def get_component(self, component_id: str) -> Optional[Any]:
        """Get a registered component"""
        return self.ui_components.get(component_id)
    
    def render(self, component_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
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
    
    def _render_dashboard(self, **kwargs) -> Dict[str, Any]:
        """Render the main explorer dashboard"""
        # Use kwargs to customize the title if provided
        title = kwargs.get('title', 'Hierarchical Blockchain Explorer')

        # Use kwargs to filter elements if specified
        included_components = kwargs.get('components', ['chain_overview', 'entity_tracer', 'event_analytics'])

        dashboard = {
            "title": title,
            "components": []
        }

        if 'chain_overview' in included_components and 'chain_overview' in self.ui_components:
            dashboard["components"].append({
                "id": "chain_overview",
                "title": "Chain Overview",
                "content": self.ui_components["chain_overview"].render_summary()
            })

        if 'entity_tracer' in included_components and 'entity_tracer' in self.ui_components:
            dashboard["components"].append({
                "id": "entity_tracer",
                "title": "Entity Tracer",
                "content": self.ui_components["entity_tracer"].render_input_form()
            })

        if 'event_analytics' in included_components and 'event_analytics' in self.ui_components:
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
    
    def render_summary(self) -> Dict[str, Any]:
        """Render chain summary"""
        try:
            summary = {
                "main_chain": self._get_main_chain_stats(),
                "sub_chains": self._get_sub_chain_stats(),
                "recent_activity": self._get_recent_activity()
            }
            return summary
        except Exception as e:
            return {"error": str(e)}
    
    def _get_main_chain_stats(self) -> Dict[str, Any]:
        """Get main chain statistics"""
        if hasattr(self.chain, 'main_chain'):
            chain = self.chain.main_chain
            return {
                "block_count": len(chain.chain),
                "latest_block": chain.chain[-1].index if chain.chain else 0,
                "total_events": sum(len(block.events) for block in chain.chain)
            }
        return {"error": "Main chain not found"}
    
    def _get_sub_chain_stats(self) -> List[Dict[str, Any]]:
        """Get sub-chain statistics"""
        if hasattr(self.chain, 'sub_chains'):
            stats = []
            for name, sub_chain in self.chain.sub_chains.items():
                stats.append({
                    "name": name,
                    "block_count": len(sub_chain.chain),
                    "events": sum(len(block.events) for block in sub_chain.chain)
                })
            return stats
        return []
    
    def _get_recent_activity(self) -> List[Dict[str, Any]]:
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
    
    @staticmethod
    def render_input_form() -> Dict[str, Any]:
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
    
    def trace_entity(self, entity_id: str, chain_type: str = "all") -> Dict[str, Any]:
        """Trace entity across chains"""
        try:
            events = []
            
            # Search main chain
            if chain_type in ["all", "main"] and hasattr(self.chain, 'main_chain'):
                main_events = self._search_main_chain(entity_id)
                events.extend(main_events)
            
            # Search sub-chains
            if chain_type in ["all", "sub"] and hasattr(self.chain, 'sub_chains'):
                sub_events = self._search_sub_chains(entity_id)
                events.extend(sub_events)
            
            # Sort by timestamp
            events.sort(key=lambda x: x.get('timestamp', 0))
            
            return {
                "entity_id": entity_id,
                "total_events": len(events),
                "events": events,
                "chains_found": list(set(e['chain'] for e in events))
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _search_main_chain(self, entity_id: str) -> List[Dict[str, Any]]:
        """Search main chain for entity"""
        events = []
        for block in self.chain.main_chain.chain:
            for event in block.events:
                if self._event_contains_entity(event, entity_id):
                    events.append({
                        "chain": "main_chain",
                        "block_index": block.index,
                        "event": event,
                        "timestamp": event.get('timestamp', block.timestamp if hasattr(block, 'timestamp') else 0)
                    })
        return events
    
    def _search_sub_chains(self, entity_id: str) -> List[Dict[str, Any]]:
        """Search sub-chains for entity"""
        events = []
        for chain_name, sub_chain in self.chain.sub_chains.items():
            for block in sub_chain.chain:
                for event in block.events:
                    if self._event_contains_entity(event, entity_id):
                        events.append({
                            "chain": chain_name,
                            "block_index": block.index,
                            "event": event,
                            "timestamp": event.get('timestamp', block.timestamp if hasattr(block, 'timestamp') else 0)
                        })
        return events
    
    @staticmethod
    def _event_contains_entity(event: Dict[str, Any], entity_id: str) -> bool:
        """Check if event contains entity"""
        return (event.get("entity_id") == entity_id or 
                entity_id in str(event.get("details", {})))


class EventAnalyticsComponent:
    """Component for event analytics"""
    
    def __init__(self, chain: Any):
        self.chain = chain
    
    def render_summary(self) -> Dict[str, Any]:
        """Render analytics summary"""
        try:
            return {
                "event_types": self._get_event_type_stats(),
                "activity_timeline": self._get_activity_timeline(),
                "chain_distribution": self._get_chain_distribution()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _get_event_type_stats(self) -> Dict[str, int]:
        """Get event type statistics"""
        stats = {}
        
        # Analyze main chain
        if hasattr(self.chain, 'main_chain'):
            for block in self.chain.main_chain.chain:
                for event in block.events:
                    event_type = event.get('event', 'unknown')
                    stats[event_type] = stats.get(event_type, 0) + 1
        
        # Analyze sub-chains
        if hasattr(self.chain, 'sub_chains'):
            for sub_chain in self.chain.sub_chains.values():
                for block in sub_chain.chain:
                    for event in block.events:
                        event_type = event.get('event', 'unknown')
                        stats[event_type] = stats.get(event_type, 0) + 1
        
        return stats
    
    def _get_activity_timeline(self) -> List[Dict[str, Any]]:
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
    
    def _get_chain_distribution(self) -> Dict[str, int]:
        """Get event distribution by chain"""
        distribution = {}
        
        if hasattr(self.chain, 'main_chain'):
            main_events = sum(len(block.events) for block in self.chain.main_chain.chain)
            distribution["main_chain"] = main_events
        
        if hasattr(self.chain, 'sub_chains'):
            for name, sub_chain in self.chain.sub_chains.items():
                sub_events = sum(len(block.events) for block in sub_chain.chain)
                distribution[name] = sub_events
        
        return distribution


class ProofVisualizerComponent:
    """Component for proof visualization"""
    
    def __init__(self, chain: Any):
        self.chain = chain
    
    def render_proof_flow(self) -> Dict[str, Any]:
        """Render proof submission flow"""
        try:
            return {
                "proof_submissions": self._get_proof_submissions(),
                "validation_status": self._get_validation_status(),
                "hierarchy_view": self._get_hierarchy_view()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _get_proof_submissions(self) -> List[Dict[str, Any]]:
        """Get recent proof submissions"""
        proofs = []
        
        if hasattr(self.chain, 'main_chain'):
            for block in self.chain.main_chain.chain[-10:]:  # Last 10 blocks
                for event in block.events:
                    if event.get('type') == 'sub_chain_proof':
                        proofs.append({
                            "block_index": block.index,
                            "sub_chain": event.get('sub_chain'),
                            "proof_hash": event.get('proof_hash'),
                            "metadata": event.get('metadata', {}),
                            "timestamp": event.get('timestamp')
                        })
        
        return sorted(proofs, key=lambda x: x.get('timestamp', 0), reverse=True)
    
    def _get_validation_status(self) -> Dict[str, Any]:
        """Get validation status"""
        return {
            "total_proofs": self._count_total_proofs(),
            "recent_proofs": len(self._get_proof_submissions()),
            "validation_rate": 100.0  # Simplified
        }
    
    def _count_total_proofs(self) -> int:
        """Count total proof submissions"""
        count = 0
        if hasattr(self.chain, 'main_chain'):
            for block in self.chain.main_chain.chain:
                for event in block.events:
                    if event.get('type') == 'sub_chain_proof':
                        count += 1
        return count
    
    def _get_hierarchy_view(self) -> Dict[str, Any]:
        """Get hierarchical view of chains"""
        hierarchy = {
            "main_chain": {
                "type": "main",
                "blocks": len(self.chain.main_chain.chain) if hasattr(self.chain, 'main_chain') else 0,
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
    
    def _get_latest_proof_for_chain(self, chain_name: str) -> Optional[Dict[str, Any]]:
        """Get latest proof for specific chain"""
        if hasattr(self.chain, 'main_chain'):
            for block in reversed(self.chain.main_chain.chain):
                for event in block.events:
                    if (event.get('type') == 'sub_chain_proof' and 
                        event.get('sub_chain') == chain_name):
                        return {
                            "proof_hash": event.get('proof_hash'),
                            "timestamp": event.get('timestamp'),
                            "block_index": block.index
                        }
        return None