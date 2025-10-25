"""
Pytest configuration for hierarchical-blockchain project.

Ensures project root is on sys.path so test imports like `import api`, `import core`,
`import hierarchical` resolve correctly during test collection.
"""
import os
import sys

# Compute project root (parent of this tests directory)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
