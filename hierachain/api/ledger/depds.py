"""API Ledger — FastAPI dependencies (singleton providers).

Lazy-initialised HierarchyManager and EntityTracer shared
across all Ledger endpoint modules.
"""

from fastapi import Depends

from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.domains.utils.entity_tracer import EntityTracer
from hierachain.security.identity_loader import load_node_identity

_hierarchy_manager: HierarchyManager | None = None
_entity_tracer: EntityTracer | None = None


def get_hierarchy_manager() -> HierarchyManager:
    global _hierarchy_manager
    if _hierarchy_manager is None:
        node_identity = load_node_identity()
        _hierarchy_manager = HierarchyManager(node_identity=node_identity)
    assert _hierarchy_manager is not None
    return _hierarchy_manager


def get_entity_tracer(
    manager: HierarchyManager = Depends(get_hierarchy_manager)
) -> EntityTracer:
    global _entity_tracer
    if _entity_tracer is None:
        _entity_tracer = EntityTracer(manager)
    assert _entity_tracer is not None
    return _entity_tracer
