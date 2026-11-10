"""Regression tests for shared nonce replay and rate-limit state."""

from pathlib import Path

from hierachain.adapters.database.auth_state import SQLiteApiStateStore


def test_nonce_replay_is_shared_between_store_instances(tmp_path: Path) -> None:
    path = tmp_path / "api-state.sqlite3"
    first = SQLiteApiStateStore(str(path))
    second = SQLiteApiStateStore(str(path))

    assert first.consume_nonce("nonce-0001", 1000.0, 600.0) is True
    assert second.consume_nonce("nonce-0001", 1001.0, 600.0) is False
    assert second.consume_nonce("nonce-0002", 1001.0, 600.0) is True
    assert first.consume_nonce("nonce-0001", 1601.0, 600.0) is True


def test_rate_limit_window_is_shared_between_store_instances(tmp_path: Path) -> None:
    path = tmp_path / "api-state.sqlite3"
    first = SQLiteApiStateStore(str(path))
    second = SQLiteApiStateStore(str(path))

    assert first.allow_request("verify:client", 1000.0, 60.0, 2) is True
    assert second.allow_request("verify:client", 1001.0, 60.0, 2) is True
    assert first.allow_request("verify:client", 1002.0, 60.0, 2) is False
    assert second.allow_request("verify:client", 1061.0, 60.0, 2) is True
    assert first.allow_request("verify:client", 1062.0, 60.0, 2) is True
    assert second.allow_request("verify:client", 1063.0, 60.0, 2) is False
