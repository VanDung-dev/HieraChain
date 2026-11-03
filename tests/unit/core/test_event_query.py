from types import SimpleNamespace
from typing import Any

import pytest

from hierachain.core import event_query
from hierachain.core.block import Block
from hierachain.core.blockchain import Blockchain


def _append(chain: Blockchain, events: list[dict[str, Any]]) -> None:
    assert chain.add_block(chain.create_block(events))


@pytest.fixture
def chain() -> Blockchain:
    chain = Blockchain("query-chain")
    for start in (0, 60):
        _append(chain, [
            {"entity_id": "shared" if index % 2 == 0 else "other", "event": "created",
             "timestamp": float(index), "details": {"nested": {"index": index}}}
            for index in range(start, start + 60)
        ])
    chain.add_event({"entity_id": "shared", "event": "created", "timestamp": 121.0})
    return chain


@pytest.mark.parametrize("filters,expected", [
    ({"entity_id": "absent"}, 0), ({"event_type": "absent"}, 0),
    ({"entity_id": "shared"}, 1), ({"event_type": "created"}, 1),
])
def test_index_queries_do_not_read_blocks(
    chain: Blockchain, monkeypatch: pytest.MonkeyPatch, filters: dict[str, str], expected: int,
) -> None:
    def unexpected(_block: Block) -> Any:
        pytest.fail("Indexed query must not read block event data")

    monkeypatch.setattr(Block, "events", property(unexpected))
    assert len(chain.get_event_page(limit=1, **filters)) == expected


def test_combined_filters_and_payload_ownership(chain: Blockchain) -> None:
    _append(chain, [{"entity_id": "alias", "event": "base", "event_type": "displayed",
                     "timestamp": 0.0, "details": {"nested": {"value": "owned"}}}])
    page = chain.get_event_page(entity_id="alias", event_type="displayed", from_timestamp=0, to_timestamp=0)
    assert len(page) == 1
    assert chain.get_event_page(entity_id="alias", event_type="base") == []
    assert [row["event"]["timestamp"] for row in chain.get_event_page(
        entity_id="shared", from_timestamp=0, to_timestamp=0,
    )] == [0.0]
    assert chain.get_event_page(from_timestamp=20, to_timestamp=10) == []
    page[0]["event"]["details"]["nested"]["value"] = "changed"
    assert chain.get_event_page(entity_id="alias")[0]["event"]["details"]["nested"]["value"] == "owned"


def test_arrow_time_filter_decodes_only_selected_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    block = Block(0, [{"entity_id": "item", "event": "created", "timestamp": float(index),
                       "details": {"index": index}} for index in range(5000)])
    decoded = []
    decode = event_query.table_to_list_of_dicts

    def capture(table: Any) -> list[dict[str, Any]]:
        decoded.append(len(table))
        return decode(table)

    monkeypatch.setattr(event_query, "table_to_list_of_dicts", capture)
    rows = event_query.select_event_page([block], from_timestamp=4998, to_timestamp=4999, limit=2)
    assert [row["event"]["timestamp"] for row in rows] == [4998.0, 4999.0]
    assert sum(decoded) == 2
    decoded.clear()
    assert event_query.select_event_page([block], from_timestamp=6000, limit=1) == []
    assert decoded == []
    assert len(event_query.select_event_page([block], limit=1)) == 1
    assert sum(decoded) == 1


@pytest.mark.parametrize("indexed", [True, False])
def test_event_pages_keep_order_and_exclude_pending(chain: Blockchain, indexed: bool) -> None:
    timestamps = []
    after = None
    for _ in range(5):
        if indexed:
            rows = chain.get_event_page(entity_id="shared", limit=17, after=after)
        else:
            rows = event_query.select_event_page(chain.chain, entity_id="shared", limit=17, after=after)
        if not rows:
            break
        timestamps.extend(row["event"]["timestamp"] for row in rows)
        after = rows[-1]["block_index"], rows[-1]["event_index"]
    assert timestamps == [float(index) for index in range(0, 120, 2)]
    assert rows == []


def test_recovery_rebuilds_event_query_index(chain: Blockchain) -> None:
    restored = Blockchain.from_dict(chain.to_dict(), node_identity=chain.node_identity,
                                    trusted_public_keys=chain.trusted_public_keys)
    page = restored.get_event_page(event_type="created", limit=200)
    assert len(page) == 120
    assert page[60]["block_index"] == 2 and page[60]["event_index"] == 0
    assert restored.get_event_page(entity_id="shared") == chain.get_event_page(entity_id="shared")


def test_equal_timestamps_and_new_blocks_do_not_repeat_positions(chain: Blockchain) -> None:
    _append(chain, [{"entity_id": "ties", "event": "tied", "timestamp": 5.0, "details": {"order": index}}
                    for index in range(2)])
    first = chain.get_event_page(entity_id="ties", limit=1)
    _append(chain, [{"entity_id": "ties", "event": "tied", "timestamp": 5.0, "details": {"order": index}}
                    for index in range(2, 4)])
    after = first[-1]["block_index"], first[-1]["event_index"]
    second = chain.get_event_page(entity_id="ties", after=after)
    assert [row["event"]["details"]["order"] for row in first + second] == list(range(4))


def test_external_object_events_keep_legacy_payload() -> None:
    block = SimpleNamespace(index=0, events=[
        SimpleNamespace(entity_id="item", event_type="created", timestamp=0.0, data={"value": "owned"}),
    ])
    rows = event_query.select_event_page([block], entity_id="item", from_timestamp=0, to_timestamp=0)
    assert len(rows) == 1 and rows[0]["event"].data == {"value": "owned"}
    rows[0]["event"].data["value"] = "changed"
    assert block.events[0].data == {"value": "owned"}
