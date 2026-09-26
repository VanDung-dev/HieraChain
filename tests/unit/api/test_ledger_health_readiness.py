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

    def fail_bootstrap(**_kwargs: object) -> None:
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(dependencies, "HierarchyManager", fail_bootstrap)
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/ledger/ready")

    assert response.status_code == 503
