"""
Test suite for the Hierachain API server module.
"""

import logging
from unittest.mock import patch
from fastapi.testclient import TestClient

from hierachain.api import create_app
from hierachain.config import DevelopmentSettings, ProductionSettings


def test_global_exception_handler_dev_debug():
    """Test exception handler in dev with DEBUG logging (shows details)"""
    with (
        patch.object(DevelopmentSettings, 'LOG_LEVEL', 'DEBUG'),
        patch.object(DevelopmentSettings, 'ENV', 'dev', create=True),
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
        patch.object(ProductionSettings, 'ENV', 'product', create=True),
        patch.object(ProductionSettings, 'AUTH_ENABLED', False),
        patch('os.getenv', side_effect=lambda k, d=None: 'product' if k == 'HRC_ENV' else d),
    ):
        app = create_app()
        
        @app.get("/test-error-prod")
        async def throw_error_prod():
            raise ValueError("Secret database connection string failed!")
            
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-error-prod")
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "Internal server error"
        assert data["message"] == "An unexpected error occurred"
        assert data["detail"] == "Contact system administrator"
        assert "Secret database" not in data["detail"]


def test_global_exception_handler_dev_info():
    """Test exception handler in dev with INFO logging (hides details)"""
    with (
        patch.object(DevelopmentSettings, 'LOG_LEVEL', 'INFO'),
        patch.object(DevelopmentSettings, 'ENV', 'dev', create=True),
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
        patch.object(DevelopmentSettings, 'CORS_ALLOW_ALL', True),
        patch.object(DevelopmentSettings, 'ENV', 'dev', create=True),
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
        patch.object(ProductionSettings, 'AUTH_ENABLED', False),
        patch('os.getenv', side_effect=lambda k, d=None: 'product' if k == 'HRC_ENV' else d),
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
        patch.object(ProductionSettings, 'AUTH_ENABLED', False),
        patch('os.getenv',side_effect=lambda k, d=None: 'product' if k == 'HRC_ENV' else d),
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
        patch.object(ProductionSettings, 'AUTH_ENABLED', False),
        patch('os.getenv', side_effect=lambda k, d=None: 'product' if k == 'HRC_ENV' else d),
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
        patch.object(ProductionSettings, 'AUTH_ENABLED', False),
        patch('os.getenv',side_effect=lambda k, d=None: 'product' if k == 'HRC_ENV' else d),
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
