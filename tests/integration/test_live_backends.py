"""P2 acceptance paths against isolated PostgreSQL 16 and Redis 7."""

import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
import redis
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql

from hierachain.adapters.database.auth_state import (
    RedisLockoutStore,
    RedisRevocationStore,
    SQLiteRevocationStore,
)
from hierachain.api import server
from hierachain.api.middleware import add_rate_limit
from hierachain.config.settings import Settings
from hierachain.config.settings import settings as runtime_settings
from hierachain.security.brute_force_protector import BruteForceProtector
from hierachain.security.key_manager import KeyManager

pytestmark = pytest.mark.integration


@pytest.fixture
def redis_url() -> str:
    url = os.getenv("HRC_P2_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set HRC_P2_TEST_REDIS_URL for the isolated Redis backend")
    redis.from_url(url).ping()
    return url


@pytest.fixture
def postgres_url(monkeypatch: pytest.MonkeyPatch) -> str:
    base_url = os.getenv("HRC_P2_TEST_POSTGRES_URL")
    if not base_url:
        pytest.skip("Set HRC_P2_TEST_POSTGRES_URL for the isolated PostgreSQL backend")
    parsed = urlsplit(base_url)
    admin_url = urlunsplit(parsed._replace(path="/postgres"))
    db_name = f"p2_accept_{secrets.token_hex(6)}"
    db_url = urlunsplit(parsed._replace(path=f"/{db_name}"))
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
    monkeypatch.setattr(Settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(runtime_settings, "DATABASE_URL", db_url)
    try:
        yield db_url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(db_name)))


def test_revocation_and_lockout_survive_new_processes(redis_url: str, tmp_path: Path) -> None:
    key = secrets.token_urlsafe(32)
    ip = "192.0.2.123"

    for store_type, location in (
        (SQLiteRevocationStore, str(tmp_path / "revoked.db")),
        (RedisRevocationStore, redis_url),
    ):
        first = store_type(location)
        second = store_type(location)
        first.revoke(key)
        assert second.is_revoked(key)
        assert store_type(location).is_revoked(key)
        subprocess.run(
            [sys.executable, "-c",
             "import sys; from hierachain.adapters.database import auth_state; "
             "assert getattr(auth_state, sys.argv[1])(sys.argv[2]).is_revoked(sys.argv[3])",
             store_type.__name__, location, key],
            check=True, timeout=10,
        )

    for backend, location in (("sqlite", str(tmp_path / "lockouts.db")), ("redis", redis_url)):
        config = {"storage_backend": backend, "storage_path": location,
                  "redis_url": redis_url, "max_failures": 1, "lockout_duration": 7}
        first = BruteForceProtector(config)
        assert first.record_failure(ip)
        assert BruteForceProtector(config).is_locked_out(ip)
        subprocess.run(
            [sys.executable, "-c",
             "import json, sys; from hierachain.security.brute_force_protector import BruteForceProtector; "
             "assert BruteForceProtector(json.loads(sys.argv[1])).is_locked_out(sys.argv[2])",
             json.dumps(config), ip],
            check=True, timeout=10,
        )
        if backend == "redis":
            ttl = redis.from_url(redis_url).ttl(RedisLockoutStore._key(ip))
            assert 0 < ttl <= 7
        first.reset(ip)


def test_redis_rate_limiter_enforces_quota_and_fails_closed(redis_url: str) -> None:
    parsed = redis.from_url(redis_url).connection_pool.connection_kwargs
    settings = SimpleNamespace(RATE_LIMIT_ENABLED=True, RATE_LIMIT_BACKEND="redis",
                               RATE_LIMIT_REQUESTS_PER_MINUTE=2, REDIS_HOST=parsed["host"],
                               REDIS_PORT=parsed["port"], REDIS_DB=parsed["db"],
                               TRUSTED_PROXIES="testclient")
    app = FastAPI()
    add_rate_limit(app, settings, set())

    @app.get("/probe")
    def probe() -> dict[str, bool]:
        return {"ok": True}

    headers = {"x-forwarded-for": f"198.51.100.{secrets.randbelow(254) + 1}"}
    with TestClient(app) as client:
        assert client.get("/probe", headers=headers).status_code == 200
        assert client.get("/probe", headers=headers).status_code == 200
        assert client.get("/probe", headers=headers).status_code == 429

    # A separate app points at a closed port to exercise the chosen 503 policy.
    settings.REDIS_PORT = 1
    unavailable_app = FastAPI()
    add_rate_limit(unavailable_app, settings, set())

    @unavailable_app.get("/probe")
    def unavailable_probe() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(unavailable_app) as client:
        assert client.get("/probe").status_code == 503


def test_http_lockout_is_shared_across_workers(
    redis_url: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = server.get_settings()
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "get_p2p_config", lambda: {"enabled": False})
    monkeypatch.setattr(settings, "get_auth_config", lambda: {
        "enabled": True,
        "brute_force": {"storage_backend": "redis", "redis_url": redis_url,
                        "max_failures": 1, "lockout_duration": 7},
    })
    monkeypatch.setattr(server, "get_settings", lambda: settings)
    apps = [server.create_app(), server.create_app()]
    valid_key = apps[1].state.auth_verifier.key_manager.create_key("p2-tester", ["all"])
    lockouts = RedisLockoutStore(redis_url)
    lockouts.delete("testclient")
    try:
        with TestClient(apps[0]) as first, TestClient(apps[1]) as second:
            assert first.get("/api/ledger/chains", headers={"x-api-key": "invalid"}).status_code == 401
            assert second.get("/api/ledger/chains", headers={"x-api-key": valid_key}).status_code == 429
    finally:
        lockouts.delete("testclient")


def test_authenticated_http_event_and_cross_worker_revocation(
    redis_url: str, postgres_url: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = server.get_settings()
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "get_auth_config", lambda: {"enabled": True})
    monkeypatch.setattr(settings, "get_p2p_config", lambda: {"enabled": False})
    monkeypatch.setattr(server, "get_settings", lambda: settings)
    key = secrets.token_urlsafe(32)
    records = {key: {"user_id": "p2-tester", "permissions": ["all"],
                     "app_details": {"name": "P2 test"}, "created_at": time.time()}}
    apps = [server.create_app(), server.create_app()]
    for app in apps:
        app.state.auth_verifier.key_manager = KeyManager(
            storage_backend=records, revocation_store=RedisRevocationStore(redis_url),
        )
    chain_name = f"p2_{secrets.token_hex(4)}"
    headers = {"x-api-key": key}

    from hierachain.api.ledger.depds import get_hierarchy_manager
    try:
        get_hierarchy_manager()
    except Exception as exc:
        raise exc.__cause__ or exc

    with TestClient(apps[0]) as first, TestClient(apps[1]) as second:
        assert first.get("/api/ledger/chains").status_code == 401
        created = first.post(f"/api/ledger/chains/{chain_name}/create", headers=headers)
        assert created.status_code == 201, created.text

        chain = get_hierarchy_manager().get_sub_chain(chain_name)
        assert chain is not None
        pending_before = len(chain.pending_events)
        invalid = first.post(f"/api/ledger/chains/{chain_name}/events", headers=headers,
                             json={"entity_id": "item-1", "event_type": "transaction"})
        assert invalid.status_code == 422, invalid.text
        assert len(chain.pending_events) == pending_before

        valid = first.post(f"/api/ledger/chains/{chain_name}/events", headers=headers,
                           json={"entity_id": "item-1", "event_type": "created",
                                 "details": {"batch": "A"}})
        assert valid.status_code == 200, valid.text
        assert valid.json()["event_id"]
        chain.flush_pending_and_finalize(timeout=5.0)
        with psycopg.connect(postgres_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT event_type FROM events WHERE chain_name = %s AND entity_id = %s",
                    (chain_name, "item-1"),
                )
                event_types = [row[0] for row in cursor.fetchall()]
        assert event_types == ["created"]
        assert second.get("/api/ledger/chains", headers=headers).status_code == 200

        apps[0].state.auth_verifier.key_manager.revoke_key(key)
        assert second.get("/api/ledger/chains", headers=headers).status_code == 401
        restarted = KeyManager(storage_backend=records, revocation_store=RedisRevocationStore(redis_url))
        assert restarted.is_revoked(key)

    chain.stop()
