"""
Blockchain Explorer for HieraChain Ledger

Facade that orchestrates explorer components for dashboard rendering.
"""

import logging
from typing import Any, cast

from hierachain.api.explorer_components import (
    ExplorerError,
    ComponentConfig,
    ChainOverviewComponent,
    EntityTracerComponent,
    EventAnalyticsComponent,
    ProofVisualizerComponent,
)
from hierachain.api.storage.explorer_helpers import get_explorer_css_styles, get_explorer_javascript


__all__ = [
    "ExplorerError",
    "ComponentConfig",
    "BlockchainExplorer",
    "ChainOverviewComponent",
    "EntityTracerComponent",
    "EventAnalyticsComponent",
    "ProofVisualizerComponent",
]


class BlockchainExplorer:
    def __init__(self, chain: Any, config: dict[str, Any] | None = None):
        self.chain = chain
        self.config = config or {}
        self.ui_components: dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
        self.register_default_components()

    def register_default_components(self):
        self.register_component("chain_overview", ChainOverviewComponent(self.chain))
        self.register_component("entity_tracer", EntityTracerComponent(self.chain))
        self.register_component("event_analytics", EventAnalyticsComponent(self.chain))
        self.register_component("proof_visualizer", ProofVisualizerComponent(self.chain))

    def register_component(self, component_id: str, component: Any):
        self.ui_components[component_id] = component

    def get_component(self, component_id: str) -> Any | None:
        return self.ui_components.get(component_id)

    def render(self, component_id: str | None = None, **kwargs) -> dict[str, Any]:
        if component_id:
            component = self.get_component(component_id)
            if component is None:
                raise ExplorerError(f"Component {component_id} not found")
            if hasattr(component, 'render'):
                return cast(Any, component).render(**kwargs)
            elif hasattr(component, 'render_summary'):
                return cast(Any, component).render_summary(**kwargs)
            elif hasattr(component, 'render_proof_flow'):
                return cast(Any, component).render_proof_flow(**kwargs)
            elif hasattr(component, 'render_input_form'):
                return cast(Any, component).render_input_form(**kwargs)
            else:
                raise ExplorerError(f"Component {component_id} has no render method")

        return self._render_dashboard(**kwargs)

    def _render_dashboard(self, **kwargs) -> dict[str, Any]:
        title = kwargs.get('title', 'HieraChain Explorer')
        included_components = kwargs.get(
            'components', ['chain_overview', 'entity_tracer', 'event_analytics']
        )

        dashboard: dict[str, Any] = {
            "title": title,
            "components": [],
            "assets": {
                "css": get_explorer_css_styles(),
                "js": get_explorer_javascript()
            }
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
