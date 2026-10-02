"""API Ledger — FastAPI dependencies (singleton providers).

Lazy-initialised HierarchyManager and EntityTracer shared
across all Ledger endpoint modules.
"""

import threading
import time

from fastapi import Depends, HTTPException, status

from hierachain.domains.utils.entity_tracer import EntityTracer
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.identity_loader import load_node_identity

_hierarchy_manager: HierarchyManager | None = None
_entity_tracer: EntityTracer | None = None
_hierarchy_manager_lock = threading.Lock()
_hierarchy_retry_at = 0.0


def get_hierarchy_manager() -> HierarchyManager:
    global _hierarchy_manager, _hierarchy_retry_at
    if _hierarchy_manager is None:
        if not _hierarchy_manager_lock.acquire(blocking=False):
            raise HTTPException(status_code=503, detail="Hierarchy recovery is in progress")
        try:
            if _hierarchy_manager is None:
                if time.monotonic() < _hierarchy_retry_at:
                    raise HTTPException(status_code=503, detail="Hierarchy recovery is not ready")
                try:
                    node_identity = load_node_identity()
                    _hierarchy_manager = HierarchyManager(node_identity=node_identity)
                except Exception as exc:
                    # Bound recovery attempts during a request storm; allow later retries.
                    _hierarchy_retry_at = time.monotonic() + 5.0
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Hierarchy recovery is not ready",
                    ) from exc
        finally:
            _hierarchy_manager_lock.release()
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
