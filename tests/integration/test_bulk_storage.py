"""Bulk storage loads retain signatures, ordering and gap/error detection."""

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from hierachain.consensus.ordering.storage import OrderingStorageHandler
from hierachain.core.block import Block
from hierachain.security.identity_loader import require_block_identity
from hierachain.security.verify.block_verifier import sign_block


@pytest.fixture(params=["sqlite", "postgres"])
def store(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[OrderingStorageHandler]:
    url = f"sqlite:///{tmp_path / 'bulk.db'}"
    if request.param == "postgres":
        url = os.getenv("HRC_TEST_POSTGRES_URL", "")
        if not url:
            pytest.skip("HRC_TEST_POSTGRES_URL is required")
    identity, trusted = require_block_identity(None, None)
    instance = OrderingStorageHandler(
        {
            "db_url": url,
            "chain_name": "bulk-" + uuid.uuid4().hex,
            "trusted_public_keys": trusted,
        }
    )
    previous_hash = "0"
    for index in range(12):
        block = Block(
            index,
            [
                {
                    "event_id": f"{instance.chain_name}-{index}-{offset}",
                    "entity_id": "item",
                    "event": "created",
                    "timestamp": float(index + 1),
                    "details": {"value": index, "offset": offset},
                }
                for offset in range(3)
            ],
            previous_hash=previous_hash,
        )
        sign_block(block, identity.node_id, identity.signing_keypair)
        instance.save_block(block, instance.chain_name)
        previous_hash = block.hash
    yield instance
    instance.close()


def test_bulk_reads_use_one_statement_and_preserve_event_order(
    store: OrderingStorageHandler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execute_calls: list[str] = []
    connect = store.storage._get_connection

    class Cursor:
        def __init__(self, cursor: Any) -> None:
            self.cursor = cursor

        def execute(self, query: str, params: tuple) -> None:
            execute_calls.append(query)
            self.cursor.execute(query, params)

        def __iter__(self) -> Iterator:
            return iter(self.cursor)

    class Connection:
        def __init__(self, connection: Any) -> None:
            self.connection = connection

        def cursor(self) -> Cursor:
            return Cursor(self.connection.cursor())

    @contextmanager
    def counted_connection() -> Iterator[Connection]:
        with connect() as connection:
            yield Connection(connection)

    monkeypatch.setattr(store.storage, "_get_connection", counted_connection)
    blocks = store.get_blocks_from_db(0)
    assert len(execute_calls) == 1
    assert [block.index for block in blocks] == list(range(12))
    assert [block.to_event_list()[0]["details"]["value"] for block in blocks] == list(
        range(12)
    )
    assert all(
        [event["details"]["offset"] for event in block.to_event_list()] == [0, 1, 2]
        for block in blocks
    )
    assert store.get_blocks_from_db(7)[0].index == 7
    assert all(
        len(block["events"]) == 3 for block in store.storage.get_blocks_from_index(0)
    )


def test_bulk_read_rejects_gaps_and_backend_failures(
    store: OrderingStorageHandler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = store.storage._block_range_placeholder
    with store.storage._get_connection() as connection:
        connection.cursor().execute(
            f'DELETE FROM blocks WHERE chain_name={p} AND "index"={p}',
            (store.chain_name, 5),
        )
        connection.commit()
    with pytest.raises(ValueError, match="gap at block 5"):
        store.get_blocks_from_db(0)

    def unavailable() -> None:
        raise OSError("backend unavailable")

    monkeypatch.setattr(store.storage, "_get_connection", unavailable)
    with pytest.raises(OSError, match="backend unavailable"):
        store.get_blocks_from_db(0)
