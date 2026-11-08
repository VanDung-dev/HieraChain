"""P3 regressions for public data, cache, logging and reporting contracts."""

import logging
from unittest.mock import patch

import pytest

from hierachain.core.block import Block
from hierachain.core.cache import AdvancedCache
from hierachain.security.secure_logging import (
    SecureLogger,
    log_user_action,
    sanitize_for_log,
)


def test_zero_timestamp_round_trips_with_identical_hash() -> None:
    block = Block(0, [], timestamp=0, previous_hash="0")
    assert block.timestamp == 0
    restored = Block.from_dict(block.to_dict())
    assert restored.timestamp == 0
    assert restored.hash == block.hash


@pytest.mark.parametrize("policy", ["lru", "lfu", "fifo", "ttl"])
def test_cache_mapping_operations_share_the_eviction_store(policy: str) -> None:
    cache = AdvancedCache(max_size=3, eviction_policy=policy)
    cache.update({"none": None, "value": 2})
    assert cache["none"] is None
    assert dict(cache) == {"none": None, "value": 2}
    assert cache == {"none": None, "value": 2}
    assert set(cache) == {"none", "value"}
    assert list(cache.values()) == [None, 2]
    assert cache.setdefault("third", 3) == 3
    assert cache.setdefault("third", 4) == 3
    assert cache.pop("none") is None
    assert cache.popitem() in [("value", 2), ("third", 3)]
    cache.clear()
    assert dict(cache) == {}
    with pytest.raises(KeyError):
        _ = cache["missing"]


def test_cache_ttl_and_empty_key_eviction_affect_mapping_views() -> None:
    cache = AdvancedCache(max_size=1)
    cache[""] = None
    cache.update({"live": 1})
    assert len(cache) == 1
    assert dict(cache) == {"live": 1}
    cache.set("live", None, ttl=0)
    assert list(cache.items()) == []
    assert len(cache) == 0


def test_cache_methods_normalize_keys_consistently() -> None:
    cache = AdvancedCache()
    cache.set(12, "value")
    assert cache.get(12) == cache[12] == cache["12"] == "value"
    assert cache.contains(12) and 12 in cache
    assert cache.delete(12)
    assert not cache


@pytest.mark.parametrize("method", [
    "info", "warning", "error", "debug", "critical", "security_event", "audit", "user_action",
])
def test_every_log_context_redacts_values_by_sensitive_field_name(method: str) -> None:
    logger = SecureLogger("p3.logging", level=logging.DEBUG)
    payload = {
        "password": {"opaque": "secret-password"},
        "apiKey": "secret-api", "credentials": ["secret-list"],
        "clientSecret": "secret-camel", "aws_secret_access_key": "secret-scoped",
        "nested": [{"private_key": "secret-private", "client_secret": "secret-client", "public_key": "public"}],
    }
    with patch.object(logger.logger, "log") as captured:
        if method == "security_event":
            logger.security_event("test", "message", **payload)
        elif method == "audit":
            logger.audit("read", "record", **payload)
        elif method == "user_action":
            log_user_action(logger.logger, logging.INFO, "message", user_input=payload, **payload)
        else:
            getattr(logger, method)("message", **payload)
    output = captured.call_args.args[1]
    assert "secret-" not in output
    assert "public" in output
    assert "secret-" not in sanitize_for_log(payload)
