"""
Test suite for the Hierachain API server module.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from hierachain.api import create_app, server
from hierachain.config import (
    DevelopmentSettings,
    ProductionSettings,
    Settings,
    TestingSettings,
)
from hierachain.security.key_manager import KeyManager


def _run_server_lifespan() -> None:
    async def run() -> None:
        async with server.lifespan(server.app):
            pass

    asyncio.run(run())


def test_global_exception_handler_dev_debug():
    """Test exception handler in dev with DEBUG logging (shows details)"""
    with (
        patch.dict(os.environ, {"HRC_ENV": "dev"}),
        patch.object(DevelopmentSettings, 'LOG_LEVEL', 'DEBUG'),
        patch.object(DevelopmentSettings, 'ENV', 'dev', create=True),
        patch.object(TestingSettings, 'LOG_LEVEL', 'DEBUG'),
        patch.object(TestingSettings, 'ENV', 'dev', create=True),
        patch.object(Settings, 'LOG_LEVEL', 'DEBUG'),
        patch.object(Settings, 'ENV', 'dev', create=True),
    ):
        app = create_app()
        
        @app.get("/test-error")
        async def throw_error():
            raise ValueError("Secret database connection string failed!")
            
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-error")
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "Internal server error"
        assert data["message"] == "An unexpected error occurred"
        assert "Secret database connection string" in data["detail"]


def test_global_exception_handler_production():
    """Test exception handler in production (hides details)"""
    with (
        patch.object(ProductionSettings, 'LOG_LEVEL', 'DEBUG'),
        patch.object(server, '_load_production_key_manager', return_value=KeyManager()),
        patch(
            'os.getenv',
            side_effect=lambda k, d=None: (
                'production' if k == 'ENV' else 'sqlite' if k == 'HRC_STORAGE_BACKEND' else d
            ),
        ),
    ):
        app = create_app()
        api_key = app.state.auth_verifier.key_manager.create_key("test_user", ["all"])
        
        @app.get("/test-error-prod")
        async def throw_error_prod():
            raise ValueError("Secret database connection string failed!")
            
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-error-prod", headers={"X-API-Key": api_key})
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "Internal server error"
        assert data["message"] == "An unexpected error occurred"
        assert data["detail"] == "Contact system administrator"
        assert "Secret database" not in data["detail"]


def test_global_exception_handler_dev_info():
    """Test exception handler in dev with INFO logging (hides details)"""
    with (
        patch.dict(os.environ, {"HRC_ENV": "dev"}),
        patch.object(DevelopmentSettings, 'LOG_LEVEL', 'INFO'),
        patch.object(DevelopmentSettings, 'ENV', 'dev', create=True),
        patch.object(TestingSettings, 'LOG_LEVEL', 'INFO'),
        patch.object(TestingSettings, 'ENV', 'dev', create=True),
        patch.object(Settings, 'LOG_LEVEL', 'INFO'),
        patch.object(Settings, 'ENV', 'dev', create=True),
    ):
        app = create_app()
        
        @app.get("/test-error-info")
        async def throw_error_info():
            raise ValueError("Secret database connection string failed!")
            
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-error-info")
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "Internal server error"
        assert data["message"] == "An unexpected error occurred"
        assert data["detail"] == "Contact system administrator"
        assert "Secret database" not in data["detail"]


def test_cors_middleware_dev_allow_all():
    """Test CORS in dev: wildcard origins, credentials=False"""
    with (
        patch.dict(os.environ, {"HRC_ENV": "dev"}),
        patch.object(DevelopmentSettings, 'CORS_ALLOW_ALL', True),
        patch.object(DevelopmentSettings, 'ENV', 'dev', create=True),
        patch.object(TestingSettings, 'CORS_ALLOW_ALL', True),
        patch.object(TestingSettings, 'ENV', 'dev', create=True),
        patch.object(Settings, 'CORS_ALLOW_ALL', True),
        patch.object(Settings, 'ENV', 'dev', create=True),
    ):
        app = create_app()
        client = TestClient(app)
        response = client.options("/", headers={
            "Origin": "http://localhost:2661",
            "Access-Control-Request-Method": "GET"
        })

        assert response.status_code == 200
        # Wildcard origins should return the origin or "*"
        acao = response.headers.get("access-control-allow-origin")
        assert acao in ("http://localhost:2661", "*")
        # When CORS_ALLOW_ALL=True, credentials must be disabled
        # (CORS spec forbids allow_origins=["*"] with credentials)
        acac = response.headers.get("access-control-allow-credentials")
        assert acac is None or acac == "false"


def test_cors_middleware_prod_allow_origins():
    """Test CORS in production: only explicit origins allowed"""
    allowed = ['https://dashboard.hierachain.com']
    with (
        patch.object(ProductionSettings, 'CORS_ALLOW_ALL', False),
        patch.object(ProductionSettings, 'CORS_ORIGINS', allowed),
        patch.object(ProductionSettings, 'ENV', 'product', create=True),
        patch.object(server, '_load_production_key_manager', return_value=KeyManager()),
        patch(
            'os.getenv',
            side_effect=lambda k, d=None: (
                'product' if k == 'HRC_ENV' else 'sqlite' if k == 'HRC_STORAGE_BACKEND' else d
            ),
        ),
    ):
        app = create_app()
        client = TestClient(app)

        # Request from allowed origin
        response = client.options("/", headers={
            "Origin": "https://dashboard.hierachain.com",
            "Access-Control-Request-Method": "GET"
        })
        assert response.status_code == 200
        assert (response.headers.get("access-control-allow-origin") == "https://dashboard.hierachain.com")
        assert (response.headers.get("access-control-allow-credentials") == "true")

        # Request from disallowed origin
        response2 = client.options("/", headers={
            "Origin": "https://malicious.com",
            "Access-Control-Request-Method": "GET"
        })
        # Disallowed origins should NOT get ACAO header
        assert (
            response2.headers.get("access-control-allow-origin")
            is None
            or response2.headers.get("access-control-allow-origin") != "https://malicious.com"
        )


def test_cors_prod_restricted_methods():
    """Test CORS in production: only configured methods allowed"""
    allowed_methods = ["GET", "POST", "OPTIONS"]
    with (
        patch.object(ProductionSettings, 'CORS_ALLOW_ALL', False),
        patch.object(ProductionSettings, 'CORS_ORIGINS', ['https://dashboard.hierachain.com']),
        patch.object(ProductionSettings, 'CORS_ALLOW_METHODS', allowed_methods),
        patch.object(ProductionSettings, 'ENV', 'product', create=True),
        patch.object(server, '_load_production_key_manager', return_value=KeyManager()),
        patch(
            'os.getenv',
            side_effect=lambda k, d=None: (
                'product' if k == 'HRC_ENV' else 'sqlite' if k == 'HRC_STORAGE_BACKEND' else d
            ),
        ),
    ):
        app = create_app()
        client = TestClient(app)

        # Preflight for allowed method
        response = client.options("/", headers={
            "Origin": "https://dashboard.hierachain.com",
            "Access-Control-Request-Method": "GET"
        })
        assert response.status_code == 200
        methods_header = response.headers.get("access-control-allow-methods", "")
        assert "GET" in methods_header


def test_cors_prod_wildcard_warning(caplog):
    """Test that production with CORS_ALLOW_ALL=True logs a warning"""
    with (
        patch.object(ProductionSettings, 'CORS_ALLOW_ALL', True),
        patch.object(ProductionSettings, 'ENV', 'product', create=True),
        patch.object(server, '_load_production_key_manager', return_value=KeyManager()),
        patch(
            'os.getenv',
            side_effect=lambda k, d=None: (
                'product' if k == 'HRC_ENV' else 'sqlite' if k == 'HRC_STORAGE_BACKEND' else d
            ),
        ),
    ):
        app = create_app()
        with caplog.at_level(logging.WARNING, logger="hierachain.api.server"):
            # TestClient triggers lifespan startup/shutdown
            with TestClient(app):
                pass

        assert any(
            "CORS_ALLOW_ALL is True in production" in msg
            for msg in caplog.messages
        )


def test_cors_prod_empty_origins_warning(caplog):
    """Test that production with empty CORS_ORIGINS logs a warning"""
    with (
        patch.object(ProductionSettings, 'CORS_ALLOW_ALL', False),
        patch.object(ProductionSettings, 'CORS_ORIGINS', []),
        patch.object(ProductionSettings, 'ENV', 'product', create=True),
        patch.object(server, '_load_production_key_manager', return_value=KeyManager()),
        patch(
            'os.getenv',
            side_effect=lambda k, d=None: (
                'product' if k == 'HRC_ENV' else 'sqlite' if k == 'HRC_STORAGE_BACKEND' else d
            ),
        ),
    ):
        app = create_app()
        with caplog.at_level(logging.WARNING, logger="hierachain.api.server"):
            # TestClient triggers lifespan startup/shutdown
            with TestClient(app):
                pass

        assert any(
            "CORS_ORIGINS is empty in production" in msg
            for msg in caplog.messages
        )


def test_production_postgres_startup_requires_explicit_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HRC_ENV", "prod")
    monkeypatch.setenv("HRC_AUTH_ENABLED", "true")
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "postgres")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("HRC_DATABASE_URL", raising=False)

    with (
        patch.object(server.ws_manager, "start", new=AsyncMock()) as start,
        patch.object(server.ws_manager, "stop", new=AsyncMock()),
        patch.object(server, "_start_p2p_network_layer", new=AsyncMock()),
        pytest.raises(RuntimeError, match="requires DATABASE_URL or HRC_DATABASE_URL"),
    ):
        _run_server_lifespan()

    start.assert_not_awaited()


def test_production_rejects_disabled_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HRC_ENV", "production")
    monkeypatch.setenv("HRC_AUTH_ENABLED", "false")

    with pytest.raises(ValueError, match="Production requires HRC_AUTH_ENABLED=true"):
        create_app()


def test_production_requires_provisioned_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HRC_ENV", "production")
    monkeypatch.setenv("HRC_AUTH_ENABLED", "true")
    monkeypatch.delenv("HRC_API_KEYS_FILE", raising=False)

    with pytest.raises(RuntimeError, match="requires HRC_API_KEYS_FILE"):
        create_app()


def test_production_key_file_survives_app_restart(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provisioner = KeyManager()
    api_key = provisioner.create_key("operator", ["chains", "events"])
    key_file = tmp_path / "api_keys.json"
    key_file.write_text(json.dumps(provisioner.storage), encoding="utf-8")
    monkeypatch.setenv("HRC_ENV", "production")
    monkeypatch.setenv("HRC_AUTH_ENABLED", "true")
    monkeypatch.setenv("HRC_API_KEYS_FILE", str(key_file))

    app = create_app()

    @app.get("/protected")
    async def protected() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/protected").status_code == 401
    assert client.get("/protected", headers={"X-API-Key": "invalid"}).status_code == 401
    assert client.get("/protected", headers={"X-API-Key": api_key}).status_code == 200
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws"):
            pass
    with client.websocket_connect("/ws", headers={"X-API-Key": api_key}) as websocket:
        assert websocket.receive_json()["type"] == "connected"

    restarted_app = create_app()
    assert restarted_app.state.auth_verifier.key_manager.get_user(api_key) == "operator"


def test_production_rejects_empty_key_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    key_file = tmp_path / "api_keys.json"
    key_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("HRC_ENV", "production")
    monkeypatch.setenv("HRC_AUTH_ENABLED", "true")
    monkeypatch.setenv("HRC_API_KEYS_FILE", str(key_file))

    with pytest.raises(RuntimeError, match="nonempty key map"):
        create_app()


def test_invalid_storage_backend_prevents_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HRC_ENV", "dev")
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "postgres_typo")

    with (
        patch.object(server.ws_manager, "start", new=AsyncMock()) as start,
        patch.object(server.ws_manager, "stop", new=AsyncMock()),
        patch.object(server, "_start_p2p_network_layer", new=AsyncMock()),
        pytest.raises(ValueError, match="Unsupported HRC_STORAGE_BACKEND value"),
    ):
        _run_server_lifespan()

    start.assert_not_awaited()


@pytest.mark.parametrize("variable", ["DATABASE_URL", "HRC_DATABASE_URL"])
def test_production_postgres_startup_accepts_explicit_database_url(
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
) -> None:
    monkeypatch.setenv("HRC_ENV", "production")
    monkeypatch.setenv("HRC_AUTH_ENABLED", "true")
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "postgres")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("HRC_DATABASE_URL", raising=False)
    monkeypatch.setenv(variable, "postgresql://node:secret@database/hierachain")

    with (
        patch.object(server.ws_manager, "start", new=AsyncMock()),
        patch.object(server.ws_manager, "stop", new=AsyncMock()),
        patch.object(server, "_start_p2p_network_layer", new=AsyncMock()),
    ):
        _run_server_lifespan()
