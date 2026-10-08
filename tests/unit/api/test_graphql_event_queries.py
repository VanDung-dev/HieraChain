"""GraphQL event query work, payload ownership, pagination and HTTP auth contracts."""

import asyncio
import base64
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hierachain.api import graphql_handler
from hierachain.api.graphql import resolvers
from hierachain.api.graphql.schema import schema
from hierachain.api.ledger import depds
from hierachain.core import event_query
from hierachain.core.block import Block
from hierachain.core.blockchain import Blockchain
from hierachain.hierarchical import HierarchyManager
from hierachain.security.key_manager import KeyManager
from hierachain.security.verify.api_key_verifier import APIKeyVerifier
from hierachain.serialization import dumps_json


def _append(chain: Blockchain, events: list[dict[str, Any]]) -> None:
    assert chain.add_block(chain.create_block(events))


@pytest.fixture
def chain(monkeypatch: pytest.MonkeyPatch) -> Blockchain:
    chain = Blockchain("query-chain")
    for start in (0, 60):
        _append(chain, [{"entity_id": "shared" if index % 2 == 0 else "other", "event": "created",
                         "timestamp": float(index), "details": {"nested": {"index": index}}}
                        for index in range(start, start + 60)])
    chain.add_event({"entity_id": "shared", "event": "created", "timestamp": 121.0})
    monkeypatch.setattr(resolvers, "_get_chain_for_name", lambda _name: chain)
    return chain


@pytest.mark.parametrize("filters, expected", [
    ({"entity_id": "absent"}, 0), ({"event_type": "absent"}, 0),
    ({"entity_id": "shared"}, 1), ({"event_type": "created"}, 1),
])
def test_index_queries_never_read_blocks_or_convert_discarded_events(
    chain: Blockchain, monkeypatch: pytest.MonkeyPatch, filters: dict[str, str], expected: int,
) -> None:
    def unexpected(_block: Block) -> Any:
        pytest.fail("Indexed query must not read block event data")
    monkeypatch.setattr(Block, "events", property(unexpected))
    converted = []
    convert = resolvers._to_event_type
    def capture(event: dict[str, Any]) -> Any:
        converted.append(event)
        return convert(event)
    monkeypatch.setattr(resolvers, "_to_event_type", capture)
    results = resolvers.resolve_events(None, None, chain.name, limit=1, **filters)
    assert len(results) == len(converted) == expected


def test_combined_filters_use_inclusive_zero_bounds_and_alias_type(
    chain: Blockchain,
) -> None:
    _append(chain, [{"entity_id": "alias", "event": "base", "event_type": "displayed",
                     "timestamp": 0.0, "details": {"nested": {"value": "owned"}}}])
    result = resolvers.resolve_events(None, None, chain.name, entity_id="alias", event_type="displayed",
                                      from_timestamp=0, to_timestamp=0)
    assert [event.event_type for event in result] == ["displayed"]
    assert resolvers.resolve_events(None, None, chain.name, entity_id="alias", event_type="base") == []
    assert [event.timestamp for event in resolvers.resolve_events(
        None, None, chain.name, entity_id="shared", from_timestamp=0, to_timestamp=0,
    )] == [0.0]
    assert resolvers.resolve_events(None, None, chain.name, from_timestamp=20, to_timestamp=10) == []
    page = chain.get_event_page(entity_id="alias")
    page[0]["event"]["details"]["nested"]["value"] = "changed"
    assert chain.get_event_page(entity_id="alias")[0]["event"]["details"]["nested"]["value"] == "owned"


def test_arrow_time_filter_decodes_only_selected_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    block = Block(0, [{"entity_id": "item", "event": "created", "timestamp": float(index),
                       "details": {"index": index}} for index in range(5000)])
    external = SimpleNamespace(chain=[block])
    monkeypatch.setattr(resolvers, "_get_chain_for_name", lambda _name: external)
    decoded = []
    decode = event_query.table_to_list_of_dicts
    def capture(table: Any) -> list[dict[str, Any]]:
        decoded.append(len(table))
        return decode(table)
    monkeypatch.setattr(event_query, "table_to_list_of_dicts", capture)
    result = resolvers.resolve_events(None, None, "external", from_timestamp=4998, to_timestamp=4999, limit=2)
    assert [row.timestamp for row in result] == [4998.0, 4999.0]
    assert sum(decoded) == 2
    decoded.clear()
    assert resolvers.resolve_events(None, None, "external", from_timestamp=6000, limit=1) == []
    assert decoded == []
    assert len(resolvers.resolve_events(None, None, "external", limit=1)) == 1
    assert sum(decoded) == 1


@pytest.mark.parametrize("indexed", [True, False])
def test_cursor_pages_keep_order_and_exclude_pending_events(
    chain: Blockchain, monkeypatch: pytest.MonkeyPatch, indexed: bool,
) -> None:
    if not indexed:
        monkeypatch.setattr(resolvers, "_get_chain_for_name", lambda _name: SimpleNamespace(chain=chain.chain))
    query = '''query Page($after: String) {
      events(chainName: "query-chain", entityId: "shared", limit: 17, after: $after) {
        timestamp cursor
      }
    }'''
    timestamps = []
    cursor = None
    for _ in range(5):
        result = asyncio.run(schema.execute_async(query, variable_values={"after": cursor}))
        assert result.errors is None
        rows = result.data["events"]
        timestamps.extend(row["timestamp"] for row in rows)
        if not rows:
            break
        cursor = rows[-1]["cursor"]
    assert timestamps == [float(index) for index in range(0, 120, 2)]
    assert rows == []


def test_result_cap_and_recovery_rebuild_the_query_index(chain: Blockchain) -> None:
    result = asyncio.run(schema.execute_async(
        'query($limit: Int) { events(chainName: "query-chain", eventType: "created", limit: $limit) { cursor } }',
        variable_values={"limit": 10000},
    ))
    assert result.errors is None
    assert len(result.data["events"]) == 100
    assert resolvers.resolve_events(None, None, chain.name, limit=0) == []
    restored = Blockchain.from_dict(chain.to_dict(), node_identity=chain.node_identity,
                                    trusted_public_keys=chain.trusted_public_keys)
    page = restored.get_event_page(event_type="created", limit=200)
    assert len(page) == 120
    assert page[60]["block_index"] == 2 and page[60]["event_index"] == 0
    assert restored.get_event_page(entity_id="shared") == chain.get_event_page(entity_id="shared")


def test_equal_timestamps_and_new_blocks_do_not_repeat_cursor_positions(chain: Blockchain) -> None:
    _append(chain, [{"entity_id": "ties", "event": "tied", "timestamp": 5.0, "details": {"order": index}}
                    for index in range(2)])
    first = resolvers.resolve_events(None, None, chain.name, entity_id="ties", limit=1)
    _append(chain, [{"entity_id": "ties", "event": "tied", "timestamp": 5.0, "details": {"order": index}}
                    for index in range(2, 4)])
    second = resolvers.resolve_events(None, None, chain.name, entity_id="ties", after=first[-1].cursor)
    assert [row.details for row in first + second] == [dumps_json({"order": index}) for index in range(4)]
    assert resolvers.resolve_events(None, None, chain.name, entity_id="ties", after=second[-1].cursor) == []


def test_external_object_events_keep_legacy_payload_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    external = SimpleNamespace(chain=[SimpleNamespace(index=0, events=[
        SimpleNamespace(entity_id="item", event_type="created", timestamp=0.0, data={"value": "owned"}),
    ])])
    monkeypatch.setattr(resolvers, "_get_chain_for_name", lambda _name: external)
    rows = resolvers.resolve_events(None, None, "external", entity_id="item", from_timestamp=0, to_timestamp=0)
    assert len(rows) == 1 and rows[0].details == dumps_json({"value": "owned"})


@pytest.mark.parametrize("cursor", ["garbage", "", "x" * 1025,
    base64.urlsafe_b64encode(dumps_json([1, "other-chain", 0, 0]).encode()).decode(),
    base64.urlsafe_b64encode(dumps_json([1, "query-chain", True, -1]).encode()).decode(),
])
def test_invalid_cursors_return_errors_without_querying(
    chain: Blockchain, monkeypatch: pytest.MonkeyPatch, cursor: str,
) -> None:
    def unexpected(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("Invalid cursor must fail before chain lookup")
    monkeypatch.setattr(resolvers, "_get_chain_for_name", unexpected)
    result = schema.execute('query($after: String) { events(chainName: "query-chain", after: $after) { cursor } }',
                            variable_values={"after": cursor})
    assert result.errors and "Invalid event cursor" in result.errors[0].message


def test_http_event_pages_keep_verified_scope_checks(
    chain: Blockchain, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: None))
    manager = HierarchyManager()
    manager.sub_chains[chain.name] = chain
    monkeypatch.setattr(depds, "_hierarchy_manager", manager)
    # Use the actual manager lookup rather than the fixture resolver shortcut.
    monkeypatch.setattr(resolvers, "_get_chain_for_name", lambda name: manager.get_all_sub_chains().get(name))
    monkeypatch.setattr(graphql_handler.graphql_security, "check_rate_limit", lambda _ip: True)
    keys = KeyManager()
    read_key = keys.create_key("reader", ["events"])
    denied_key = keys.create_key("chain-reader", ["chains"])
    app = FastAPI()
    app.state.auth_verifier = APIKeyVerifier({"enabled": True, "cache_ttl": 0}, key_manager=keys)
    graphql_handler._register_graphql_router(app)
    query = '''query($after: String) {
      events(chainName: "query-chain", entityId: "shared", limit: 1, after: $after) { timestamp cursor }
    }'''
    try:
        with TestClient(app) as client:
            assert client.post("/graphql", json={"query": query}).status_code == 401
            assert client.post("/graphql", headers={"X-API-Key": denied_key}, json={"query": query}).status_code == 403
            first = client.post("/graphql", headers={"X-API-Key": read_key}, json={"query": query})
            assert first.status_code == 200, first.text
            row = first.json()["data"]["events"][0]
            second = client.post("/graphql", headers={"X-API-Key": read_key},
                                 json={"query": query, "variables": {"after": row["cursor"]}})
            assert second.status_code == 200, second.text
            assert [row["timestamp"], second.json()["data"]["events"][0]["timestamp"]] == [0.0, 2.0]
    finally:
        manager.sub_chains.clear()  # Blockchain test fixture owns no worker to shut down.
        manager.close()
        keys.key_cache.clear()
        keys.permission_cache.clear()
