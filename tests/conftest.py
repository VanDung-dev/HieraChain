"""
Pytest configuration for HieraChain project.

Ensures project root is on sys.path so test imports like `import api`, `import core`,
`import hierarchical` resolve correctly during test collection.
"""
import os
import sys
import shutil
import pytest
import time

# Compute project root (parent of this tests directory)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Data directory containing journal files
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")


def _remove_data_dir_with_retry(max_retries=3, delay=0.5):
    """Remove data directory with retry logic for Windows file locks."""
    if not os.path.exists(_DATA_DIR):
        return
    
    for attempt in range(max_retries):
        try:
            shutil.rmtree(_DATA_DIR)
            return
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(delay)
            # On last attempt, ignore the error (files will be cleaned next run)
        except Exception:
            # Ignore other errors during cleanup
            return


@pytest.fixture(autouse=True, scope="session")
def clean_journal_data():
    """Remove journal data at start/end of test session to prevent state pollution."""
    _remove_data_dir_with_retry()
    yield
    # Cleanup after all tests complete (best effort)
    _remove_data_dir_with_retry()


