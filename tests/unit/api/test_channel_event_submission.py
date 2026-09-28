"""API regression coverage for authenticated channel event submission."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.api.business.router import business_router
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.api.ledger.events import router
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.key_manager import KeyManager
from hierachain.security.verify.api_key_verifier import APIKeyVerifier


def test_channel_event_submission_uses_verified_user_and_live_role_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: None))
    manager = HierarchyManager()
    org_id = "org-a"
    admin_id = "org-admin"
    member_id = "org-member"
    unknown_id = "not-a-member"
    org = manager.create_organization(org_id, "Organization A", [admin_id])
    org.register_member(
        member_id,
        {"user_id": member_id, "org_id": org_id, "role": "member"},
        "member",
    )
    channel = manager.create_channel("admin-only", [org_id])

    key_manager = KeyManager()
    keys = {
        user_id: key_manager.create_key(user_id=user_id, permissions=["events"])
        for user_id in (admin_id, member_id, unknown_id)
    }
    verifier = APIKeyVerifier(
        {
            "enabled": True,
            "key_location": "header",
            "key_name": "x-api-key",
            "cache_ttl": 0,
        }
    )
    verifier.key_manager = key_manager

    app = FastAPI()
    app.state.auth_verifier = verifier
    app.include_router(router)
    app.dependency_overrides[get_hierarchy_manager] = lambda: manager
    path = f"/channels/{channel.channel_id}/organizations/{org_id}/events"
    body = {
        "entity_id": "entity-1",
        "event_type": "created",
        "sender": "a" * 64,
        "details": {"status": "new"},
    }

    with TestClient(app) as client:
        accepted = client.post(path, headers={"x-api-key": keys[admin_id]}, json=body)
        assert accepted.status_code == 200, accepted.text
        assert channel.ledger.current_block_events[0]["submitted_by"] == admin_id

        stored_events = list(channel.ledger.current_block_events)
        add_event = channel.ledger.add_event
        monkeypatch.setattr(channel.ledger, "add_event", lambda _event: False)
        rejected_ledger = client.post(
            path,
            headers={"x-api-key": keys[admin_id]},
            json={**body, "entity_id": "entity-ledger-rejected"},
        )
        assert rejected_ledger.status_code == 403, rejected_ledger.text
        assert channel.ledger.current_block_events == stored_events
        assert channel.event_statistics["total_events"] == 1
        monkeypatch.setattr(channel.ledger, "add_event", add_event)

        denied_principal = client.post(
            path,
            headers={"x-api-key": keys[unknown_id]},
            json={**body, "entity_id": "entity-2"},
        )
        assert denied_principal.status_code == 403, denied_principal.text
        assert channel.ledger.current_block_events == stored_events

        denied_role = client.post(
            path,
            headers={"x-api-key": keys[member_id]},
            json={**body, "entity_id": "entity-3"},
        )
        assert denied_role.status_code == 403, denied_role.text
        assert channel.ledger.current_block_events == stored_events

        denied_key = client.post(
            path,
            headers={"x-api-key": "invalid-api-key"},
            json={**body, "entity_id": "entity-4"},
        )
        assert denied_key.status_code == 401, denied_key.text
        assert channel.ledger.current_block_events == stored_events

    assert channel.event_statistics["total_events"] == 1
    assert channel.event_statistics["events_by_org"][org_id] == 1


def test_business_provisioning_connects_to_authenticated_channel_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: None))
    manager = HierarchyManager()
    org_id = "provisioned-org"
    channel_id = "provisioned-channel"
    admin_id = "provisioning-admin"
    member_id = "provisioned-member"
    outsider_id = "provisioning-outsider"

    key_manager = KeyManager()
    permissions = {
        admin_id: ["chains", "events", "organizations:manage", "channels:manage"],
        member_id: ["chains", "events"],
        outsider_id: ["chains", "events"],
    }
    keys = {
        user_id: key_manager.create_key(user_id=user_id, permissions=user_permissions)
        for user_id, user_permissions in permissions.items()
    }
    verifier = APIKeyVerifier(
        {
            "enabled": True,
            "key_location": "header",
            "key_name": "x-api-key",
            "cache_ttl": 0,
        }
    )
    verifier.key_manager = key_manager

    app = FastAPI()
    app.state.auth_verifier = verifier
    app.include_router(business_router)
    app.include_router(router)
    app.dependency_overrides[get_hierarchy_manager] = lambda: manager

    with TestClient(app) as client:
        admin_headers = {"x-api-key": keys[admin_id]}
        member_headers = {"x-api-key": keys[member_id]}
        outsider_headers = {"x-api-key": keys[outsider_id]}

        created_org = client.post(
            "/api/business/organizations",
            headers=admin_headers,
            json={"org_id": org_id, "ca_config": {}},
        )
        assert created_org.status_code == 200, created_org.text
        organization = manager.get_organization(org_id)
        assert organization is not None
        assert organization.members[admin_id]["role"] == "admin"

        denied_org = client.post(
            "/api/business/organizations",
            headers=outsider_headers,
            json={"org_id": "outsider-org", "ca_config": {}},
        )
        assert denied_org.status_code == 403, denied_org.text
        assert manager.get_organization("outsider-org") is None

        denied_member = client.post(
            f"/api/business/organizations/{org_id}/members",
            headers=member_headers,
            json={"member_id": outsider_id},
        )
        assert denied_member.status_code == 403, denied_member.text

        registered_member = client.post(
            f"/api/business/organizations/{org_id}/members",
            headers=admin_headers,
            json={"member_id": member_id, "role": "member"},
        )
        assert registered_member.status_code == 200, registered_member.text
        assert organization.members[member_id]["role"] == "member"

        denied_registered_member = client.post(
            f"/api/business/organizations/{org_id}/members",
            headers=member_headers,
            json={"member_id": outsider_id, "role": "admin"},
        )
        assert denied_registered_member.status_code == 403, denied_registered_member.text
        assert outsider_id not in organization.members

        denied_channel = client.post(
            "/api/business/channels",
            headers=outsider_headers,
            json={
                "channel_id": "outsider-channel",
                "organizations": [org_id],
                "policy": {"write": "ADMIN"},
            },
        )
        assert denied_channel.status_code == 403, denied_channel.text
        assert manager.get_channel("outsider-channel") is None

        created_channel = client.post(
            "/api/business/channels",
            headers=admin_headers,
            json={
                "channel_id": channel_id,
                "organizations": [org_id],
                "policy": {"read": "MEMBER", "write": "ADMIN"},
            },
        )
        assert created_channel.status_code == 200, created_channel.text
        channel = manager.get_channel(channel_id)
        assert channel is not None

        event_path = f"/channels/{channel_id}/organizations/{org_id}/events"
        event_body = {
            "entity_id": "entity-1",
            "event_type": "created",
            "sender": "a" * 64,
            "details": {"status": "new"},
        }
        accepted_event = client.post(event_path, headers=admin_headers, json=event_body)
        assert accepted_event.status_code == 200, accepted_event.text
        assert channel.ledger.current_block_events[0]["submitted_by"] == admin_id

        existing_events = list(channel.ledger.current_block_events)
        denied_event = client.post(event_path, headers=member_headers, json=event_body)
        assert denied_event.status_code == 403, denied_event.text
        assert channel.ledger.current_block_events == existing_events


def test_channel_event_rest_submission_uses_restored_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = str(tmp_path / "channel-registry.sqlite")
    monkeypatch.setattr(
        HierarchyManager,
        "_create_storage",
        staticmethod(lambda: SQLiteAdapter(db_path)),
    )
    initial_manager = HierarchyManager()
    initial_manager.create_organization("org-a", "Organization A", ["admin-a"])
    initial_manager.register_organization_member(
        "org-a",
        "member-a",
        {"user_id": "member-a", "org_id": "org-a", "role": "member"},
        "member",
    )
    initial_manager.create_channel("admin-only", ["org-a"])
    initial_manager.storage.close()

    manager = HierarchyManager()
    key_manager = KeyManager()
    admin_key = key_manager.create_key(
        user_id="admin-a", permissions=["chains", "events"]
    )
    member_key = key_manager.create_key(user_id="member-a", permissions=["events"])
    verifier = APIKeyVerifier(
        {
            "enabled": True,
            "key_location": "header",
            "key_name": "x-api-key",
            "cache_ttl": 0,
        }
    )
    verifier.key_manager = key_manager

    app = FastAPI()
    app.state.auth_verifier = verifier
    app.include_router(business_router)
    app.include_router(router)
    app.dependency_overrides[get_hierarchy_manager] = lambda: manager

    event_path = "/channels/admin-only/organizations/org-a/events"
    event_body = {"entity_id": "entity-1", "event_type": "created"}
    admin_headers = {"x-api-key": admin_key}
    with TestClient(app) as client:
        assert client.get(
            "/api/business/organizations/org-a", headers=admin_headers
        ).status_code == 200
        assert client.get(
            "/api/business/channels/admin-only", headers=admin_headers
        ).status_code == 200
        accepted = client.post(
            event_path, headers=admin_headers, json=event_body
        )
        assert accepted.status_code == 200, accepted.text
        denied = client.post(
            event_path, headers={"x-api-key": member_key}, json=event_body
        )
        assert denied.status_code == 403, denied.text

    channel = manager.get_channel("admin-only")
    assert channel is not None
    assert len(channel.ledger.current_block_events) == 1
    assert channel.event_statistics["events_by_org"]["org-a"] == 1
    manager.storage.close()
