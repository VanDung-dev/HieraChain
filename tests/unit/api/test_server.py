import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hierachain.api.server import create_app

def test_global_exception_handler_dev_debug():
    """Test exception handler in development with DEBUG logging (shows details)"""
    with patch('hierachain.config.settings.DevelopmentSettings.LOG_LEVEL', 'DEBUG'), \
         patch('hierachain.config.settings.DevelopmentSettings.ENV', 'dev', create=True):
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
        assert "Secret database connection string failed!" in data["detail"]

def test_global_exception_handler_production():
    """Test exception handler in production (hides details)"""
    with patch('hierachain.config.settings.ProductionSettings.LOG_LEVEL', 'DEBUG'), \
         patch('hierachain.config.settings.ProductionSettings.ENV', 'product', create=True), \
         patch('hierachain.config.settings.ProductionSettings.AUTH_ENABLED', False), \
         patch('os.getenv', side_effect=lambda k, d=None: 'product' if k == 'HRC_ENV' else d):
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
        assert "Secret database connection string failed!" not in data["detail"]

def test_global_exception_handler_dev_info():
    """Test exception handler in development with INFO logging (hides details)"""
    with patch('hierachain.config.settings.DevelopmentSettings.LOG_LEVEL', 'INFO'), \
         patch('hierachain.config.settings.DevelopmentSettings.ENV', 'dev', create=True):
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
        assert "Secret database connection string failed!" not in data["detail"]
