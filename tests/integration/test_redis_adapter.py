"""Opt-in Redis regressions against a disposable instance."""

import os
import uuid
from types import SimpleNamespace

import pytest
import redis

from hierachain.adapters.database.redis_adapter import (
    RedisEventManager,
    RedisProofManager,
    RedisStorageError,
)


@pytest.mark.integration
def test_live_redis_proof_history_and_fail_closed_event_queries() -> None:
    url = os.getenv("HRC_P2_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set HRC_P2_TEST_REDIS_URL to a disposable Redis instance")
    client = redis.from_url(url, decode_responses=True)
    sub_chain = f"p2-{uuid.uuid4().hex}"
    event_type = f"p2-event-{uuid.uuid4().hex}"
    proof_key = f"hierachain:proofs:{sub_chain}"
    event_key = f"hierachain:event:type:{event_type}:1"
    manager = RedisProofManager(SimpleNamespace(client=client))
    events = RedisEventManager(SimpleNamespace(client=client))
    try:
        assert manager.store_proof("main", sub_chain, "first", 7, {"revision": 1})
        assert manager.store_proof("main", sub_chain, "second", 7, {"revision": 2})
        assert [entry["proof_hash"] for entry in manager.get_proof_history(sub_chain)] == ["second", "first"]
        client.set(event_key, '{"entity_id":"E","timestamp":1,"event":"accepted"}')
        assert events.get_events_by_type(event_type)[0]["entity_id"] == "E"
        client.set(event_key, "{corrupt")
        with pytest.raises(RedisStorageError):
            events.get_events_by_type(event_type)
    finally:
        client.delete(proof_key, event_key)
        client.close()
