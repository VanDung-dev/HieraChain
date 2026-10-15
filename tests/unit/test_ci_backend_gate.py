"""A required backend job cannot succeed by skipping its contract tests."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hierachain.adapters.database.redis_adapter import RedisStorageError
from tests.conftest import pytest_sessionfinish
from tests.integration import test_registry_multiworker as registry_tests


@pytest.mark.parametrize(("required", "skipped", "expected"), [(True, True, 1), (True, False, 0), (False, True, 0)])
def test_required_backend_skips_fail_the_session(required: bool, skipped: bool, expected: int) -> None:
    reporter = SimpleNamespace(stats={"skipped": [object()] if skipped else []})
    session = SimpleNamespace(exitstatus=0, config=SimpleNamespace(
        getoption=lambda name: required,
        pluginmanager=SimpleNamespace(getplugin=lambda name: reporter),
    ))
    pytest_sessionfinish(session, 0)
    assert session.exitstatus == expected


def test_redis_registry_cleanup_preserves_failed_ledger_setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    class Manager:
        _create_storage = staticmethod(lambda: None)

        def __init__(self, _name: str) -> None:
            self._create_storage()

    ledger = Mock(side_effect=RedisStorageError("unsafe ledger policy"))
    cleanup_store = Mock()
    cleanup_store.client.scan_iter.return_value = ["fixture-owned-key"]
    cache = Mock(return_value=cleanup_store)
    monkeypatch.setenv("HRC_TEST_REDIS_PORT", "16379")
    monkeypatch.setattr(registry_tests, "HierarchyManager", Manager)
    monkeypatch.setattr(registry_tests, "RedisLedgerAdapter", ledger)
    monkeypatch.setattr(registry_tests.redis_adapter, "RedisStorageAdapter", cache)

    fixture = registry_tests.managers.__wrapped__(SimpleNamespace(param="redis"), tmp_path, monkeypatch)
    with pytest.raises(RedisStorageError, match="unsafe ledger policy"):
        next(fixture)

    ledger.assert_called_once_with(port=16379, db=14)
    cache.assert_called_once_with(port=16379, db=14)
    cleanup_store.client.delete.assert_called_once_with("fixture-owned-key")
    cleanup_store.close.assert_called_once()
