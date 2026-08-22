"""
Pytest configuration for HieraChain stress testing suite.

Ensures project root and docker directory are on sys.path.
"""

import os
import sys

_STRESS_DIR = os.path.dirname(os.path.abspath(__file__))
_DOCKER_DIR = os.path.dirname(_STRESS_DIR)
_PROJECT_ROOT = os.path.dirname(_DOCKER_DIR)

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _DOCKER_DIR not in sys.path:
    sys.path.insert(0, _DOCKER_DIR)
if _STRESS_DIR not in sys.path:
    sys.path.insert(0, _STRESS_DIR)
