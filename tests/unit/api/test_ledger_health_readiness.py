from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from hierachain.api import create_app
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.consensus.ordering.types import OrderingStatus


def _client_for(sub_chains: dict[str, object]) -> TestClient:
    manager = SimpleNamespace(get_all_sub_chains=lambda: sub_chains)
    app = create_app()
    app.dependency_overrides[get_hierarchy_manager] = lambda: manager
    return TestClient(app)


def test_liveness_stays_healthy_during_ordering_recovery() -> None:
    chain = SimpleNamespace(
        ordering_service=SimpleNamespace(status=OrderingStatus.MAINTENANCE)
    )

    with _client_for({"recovering": chain}) as client:
        response = client.get("/api/ledger/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_readiness_is_healthy_when_no_chains_have_started() -> None:
    with _client_for({}) as client:
        response = client.get("/api/ledger/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.parametrize("ordering_status", [OrderingStatus.MAINTENANCE, OrderingStatus.ERROR])
def test_readiness_fails_until_ordering_recovery_is_active(
    ordering_status: OrderingStatus,
) -> None:
    chains = {
        "active": SimpleNamespace(
            ordering_service=SimpleNamespace(status=OrderingStatus.ACTIVE)
        ),
        "recovering": SimpleNamespace(
            ordering_service=SimpleNamespace(status=ordering_status)
        ),
    }

    with _client_for(chains) as client:
        response = client.get("/api/ledger/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_readiness_succeeds_when_every_ordering_service_is_active() -> None:
    chain = SimpleNamespace(
        ordering_service=SimpleNamespace(status=OrderingStatus.ACTIVE)
    )

    with _client_for({"active": chain}) as client:
        response = client.get("/api/ledger/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readiness_returns_503_when_manager_bootstrap_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hierachain.api.ledger.depds as dependencies

    monkeypatch.setattr(dependencies, "_hierarchy_manager", None)
    monkeypatch.setattr(dependencies, "_hierarchy_retry_at", 0.0)

    def fail_bootstrap(**_kwargs: object) -> None:
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(dependencies, "HierarchyManager", fail_bootstrap)
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/ledger/ready")

    assert response.status_code == 503


def test_manager_recovery_does_not_queue_requests_behind_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading
    from unittest.mock import Mock
    import hierachain.api.ledger.depds as dependencies

    lock = threading.Lock()
    factory = Mock()
    monkeypatch.setattr(dependencies, "_hierarchy_manager", None)
    monkeypatch.setattr(dependencies, "_hierarchy_manager_lock", lock)
    monkeypatch.setattr(dependencies, "HierarchyManager", factory)
    responses = []
    app = create_app()
    lock.acquire()
    with TestClient(app) as client:
        worker = threading.Thread(target=lambda: responses.append(client.get("/api/ledger/ready")))
        worker.start()
        try:
            worker.join(timeout=1)
            completed_while_recovering = not worker.is_alive()
        finally:
            lock.release()
            worker.join(timeout=2)
    assert completed_while_recovering
    assert responses[0].status_code == 503
    factory.assert_not_called()


def test_failed_manager_bootstrap_has_a_retry_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import HTTPException
    from unittest.mock import Mock
    import hierachain.api.ledger.depds as dependencies

    now = [100.0]
    manager = object()
    factory = Mock(side_effect=[RuntimeError("broken history"), manager])
    monkeypatch.setattr(dependencies, "_hierarchy_manager", None)
    monkeypatch.setattr(dependencies, "_hierarchy_retry_at", 0.0)
    monkeypatch.setattr(dependencies, "time", SimpleNamespace(monotonic=lambda: now[0]))
    monkeypatch.setattr(dependencies, "load_node_identity", lambda: None)
    monkeypatch.setattr(dependencies, "HierarchyManager", factory)

    for _ in range(2):
        with pytest.raises(HTTPException) as error:
            dependencies.get_hierarchy_manager()
        assert error.value.status_code == 503
    assert factory.call_count == 1
    assert not dependencies._hierarchy_manager_lock.locked()
    now[0] += 5.0
    assert dependencies.get_hierarchy_manager() is manager
    assert dependencies.get_hierarchy_manager() is manager
    assert factory.call_count == 2
