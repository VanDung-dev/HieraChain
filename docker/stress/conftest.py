"""
Pytest configuration for HieraChain stress testing suite.

Ensures project root and docker directory are on sys.path.
"""

import os
import sys

import pytest

_STRESS_DIR = os.path.dirname(os.path.abspath(__file__))
_DOCKER_DIR = os.path.dirname(_STRESS_DIR)
_PROJECT_ROOT = os.path.dirname(_DOCKER_DIR)

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _DOCKER_DIR not in sys.path:
    sys.path.insert(0, _DOCKER_DIR)
if _STRESS_DIR not in sys.path:
    sys.path.insert(0, _STRESS_DIR)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Check authentication before any live Docker test mutates or loads the cluster."""
    if os.getenv("HRC_STRESS_ENV") == "docker" and os.getenv("REAL_REQUESTS", "true").lower() == "true":
        from docker.stress.real_stress_client import RealStressClient

        try:
            RealStressClient().preflight_auth()
        except RuntimeError as exc:
            raise pytest.UsageError(str(exc)) from None
