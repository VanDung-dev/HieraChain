"""API v1 — FastAPI dependencies (singleton providers).

Lazy-initialised HierarchyManager and EntityTracer shared
across all v1 endpoint modules.
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
    if _hierarchy_manager is None:
        raise RuntimeError("HierarchyManager initialization failed")
    return _hierarchy_manager


def get_entity_tracer(
    manager: HierarchyManager = Depends(get_hierarchy_manager)
) -> EntityTracer:
    global _entity_tracer
    if _entity_tracer is None:
        _entity_tracer = EntityTracer(manager)
    if _entity_tracer is None:
        raise RuntimeError("EntityTracer initialization failed")
    return _entity_tracer


def reset_instances() -> None:
    global _hierarchy_manager, _entity_tracer
    _hierarchy_manager = None
    _entity_tracer = None
