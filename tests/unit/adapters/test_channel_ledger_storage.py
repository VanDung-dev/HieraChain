"""Durable channel migration and damaged-storage failure contracts."""

from typing import Any

import pytest

from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter


def test_registry_and_channel_seed_roll_back_together(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SQLiteAdapter(":memory:")
    try:
        legacy = {"_revision": "old", "organizations": {}, "channels": {"channel": {"ledger": {}}}}
        assert store.save_hierarchy_registry(legacy)
        upgraded = {"_revision": "new", "_channel_ledger_version": 1,
                    "organizations": {}, "channels": {"channel": {}}}
        initialize = store._initialize_channel_ledgers
        def fail_after_seed(conn: Any, snapshots: dict[str, Any]) -> None:
            initialize(conn, snapshots)
            raise RuntimeError("failure before commit")
        with monkeypatch.context() as patch:
            patch.setattr(store, "_initialize_channel_ledgers", fail_after_seed)
            assert not store.save_hierarchy_registry(
                upgraded, expected_revision="old", channel_ledgers={"channel": {"blocks": [], "pending_events": []}},
            )
        assert store.load_hierarchy_registry() == legacy
        with pytest.raises(RuntimeError, match="ledger is missing"):
            store.load_channel_records("channel")
        assert store.save_hierarchy_registry(
            upgraded, expected_revision="old", channel_ledgers={"channel": {"blocks": [], "pending_events": []}},
        )
        assert store.load_channel_records("channel")["revision"] == 1
    finally:
        store.close()


def test_missing_record_is_not_treated_as_an_empty_suffix() -> None:
    store = SQLiteAdapter(":memory:")
    try:
        state = {"_revision": "current", "_channel_ledger_version": 1,
                 "organizations": {}, "channels": {"channel": {}}}
        assert store.save_hierarchy_registry(
            state, channel_ledgers={"channel": {"blocks": [], "pending_events": []}},
        )
        assert store.append_channel_record(
            "channel", {"kind": "event", "data": {"entity_id": "item", "event": "created"}},
            expected_sequence=1, expected_registry_revision="current",
        )
        # Deliberately damage only this disposable adapter's storage.
        with store._get_connection() as conn:
            conn.execute("DELETE FROM channel_ledger_records WHERE channel_id=? AND sequence=2", ("channel",))
            conn.commit()
        with pytest.raises(RuntimeError, match="missing records"):
            store.load_channel_records("channel", after_sequence=1)
    finally:
        store.close()
