"""
Unit tests for ResourceGuardMiddleware.

These tests ensure that the ResourceGuardMiddleware behaves as expected under different
conditions.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from hierachain.security import ResourceGuardMiddleware
from hierachain.monitoring import PerformanceMonitor

# Mock Monitor
@pytest.fixture
def mock_monitor():
    monitor = MagicMock(spec=PerformanceMonitor)
    monitor.monitoring_active = True
    return monitor

# Test App Factory
@pytest.fixture
def test_app(mock_monitor):
    app = FastAPI()
    
    # Simple endpoint
    @app.get("/items")
    async def read_items():
        return {"message": "ok"}
        
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Add Middleware with mocked monitor
    app.add_middleware(
        ResourceGuardMiddleware, 
        monitor=mock_monitor,
        memory_threshold_percent=80.0,
        cpu_threshold_percent=90.0
    )
    return app

@pytest.fixture
def client(test_app):
    return TestClient(test_app)

def test_normal_request_passes(client, mock_monitor):
    # Setup: Metric values are low
    mock_monitor.get_current_metrics.return_value = {
        'memory_usage': {'current_value': 50.0},
        'cpu_usage': {'current_value': 20.0}
    }
    
    response = client.get("/items")
    assert response.status_code == 200
    assert response.json() == {"message": "ok"}

def test_high_memory_rejects(client, mock_monitor):
    # Setup: Memory is high (85% > 80%)
    mock_monitor.get_current_metrics.return_value = {
        'memory_usage': {'current_value': 85.0},
        'cpu_usage': {'current_value': 20.0}
    }
    
    response = client.get("/items")
    assert response.status_code == 503
    assert response.json()["message"] == "System overloaded (Memory)"

def test_high_cpu_rejects(client, mock_monitor):
    # Setup: CPU is high (95% > 90%)
    mock_monitor.get_current_metrics.return_value = {
        'memory_usage': {'current_value': 50.0},
        'cpu_usage': {'current_value': 95.0}
    }
    
    response = client.get("/items")
    assert response.status_code == 503
    assert response.json()["message"] == "System overloaded (CPU)"

def test_exempt_path_passes_even_if_overloaded(client, mock_monitor):
    # Setup: Memory is critical (99%)
    mock_monitor.get_current_metrics.return_value = {
        'memory_usage': {'current_value': 99.0},
        'cpu_usage': {'current_value': 99.0}
    }
    
    # /health should still pass
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_missing_metric_data_passes(client, mock_monitor):
    # Setup: Metrics are missing or empty
    mock_monitor.get_current_metrics.return_value = {}
    
    response = client.get("/items")
    assert response.status_code == 200
