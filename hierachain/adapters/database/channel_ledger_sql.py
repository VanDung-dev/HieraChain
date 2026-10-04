"""Append-only channel records shared by SQLite and PostgreSQL adapters."""

from typing import Any

from hierachain.serialization import dumps_json, loads_json


def create_channel_ledger_tables(cursor: Any) -> None:
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS channel_ledger_heads "
        "(channel_id TEXT PRIMARY KEY, revision BIGINT NOT NULL)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS channel_ledger_records "
        "(channel_id TEXT NOT NULL, sequence BIGINT NOT NULL, payload TEXT NOT NULL, "
        "PRIMARY KEY (channel_id, sequence), "
        "FOREIGN KEY (channel_id) REFERENCES channel_ledger_heads(channel_id))"
    )


class ChannelLedgerSQLStorage:
    """Keep ledger writes independent of registry size, with atomic revision checks."""

    _ledger_placeholder = "?"
    _ledger_registry_lock_suffix = ""
    _ledger_begin = "BEGIN IMMEDIATE"

    def _initialize_channel_ledgers(self, conn: Any, snapshots: dict[str, Any]) -> None:
        """Called in the same transaction as registry creation or legacy migration."""
        p = self._ledger_placeholder
        cursor = conn.cursor()
        for channel_id, snapshot in snapshots.items():
            cursor.execute(
                f"INSERT INTO channel_ledger_heads (channel_id, revision) VALUES ({p}, 1)",
                (channel_id,),
            )
            cursor.execute(
                f"INSERT INTO channel_ledger_records (channel_id, sequence, payload) VALUES ({p}, 1, {p})",
                (channel_id, dumps_json({"kind": "snapshot", "data": snapshot})),
            )

    def append_channel_record(
        self, channel_id: str, record: dict[str, Any], *,
        expected_sequence: int, expected_registry_revision: str | None,
    ) -> bool:
        """Reject stale access/ledger state and commit exactly one new record."""
        encoded = dumps_json(record)
        p = self._ledger_placeholder
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if self._ledger_begin:
                cursor.execute(self._ledger_begin)
            # PostgreSQL shares this lock across appenders; metadata updates wait.
            cursor.execute(
                "SELECT value FROM chain_state WHERE key='hierarchy_registry'"
                + self._ledger_registry_lock_suffix
            )
            row = cursor.fetchone()
            raw = row["value"] if row is not None else None
            state = loads_json(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
            if (
                expected_registry_revision is None or not isinstance(state, dict)
                or state.get("_revision") != expected_registry_revision
                or state.get("_channel_ledger_version") != 1
                or channel_id not in state.get("channels", {})
            ):
                conn.rollback()
                return False
            cursor.execute(
                f"UPDATE channel_ledger_heads SET revision=revision+1 "
                f"WHERE channel_id={p} AND revision={p}",
                (channel_id, expected_sequence),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return False
            cursor.execute(
                f"INSERT INTO channel_ledger_records (channel_id, sequence, payload) VALUES ({p}, {p}, {p})",
                (channel_id, expected_sequence + 1, encoded),
            )
            conn.commit()
            return True

    def load_channel_records(self, channel_id: str, *, after_sequence: int = 0) -> dict[str, Any]:
        """Read only the durable suffix up to a captured head; missing rows fail closed."""
        p = self._ledger_placeholder
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT revision FROM channel_ledger_heads WHERE channel_id={p}", (channel_id,),
            )
            head = cursor.fetchone()
            if head is None or head["revision"] < max(1, after_sequence):
                raise RuntimeError("Persisted channel ledger is missing or truncated")
            revision = head["revision"]
            cursor.execute(
                f"SELECT sequence, payload FROM channel_ledger_records "
                f"WHERE channel_id={p} AND sequence>{p} AND sequence<={p} ORDER BY sequence",
                (channel_id, after_sequence, revision),
            )
            rows = cursor.fetchall()
        if len(rows) != revision - after_sequence or any(
            row["sequence"] != after_sequence + index + 1 for index, row in enumerate(rows)
        ):
            raise RuntimeError("Persisted channel ledger has missing records")
        return {"revision": revision, "records": [loads_json(row["payload"]) for row in rows]}
