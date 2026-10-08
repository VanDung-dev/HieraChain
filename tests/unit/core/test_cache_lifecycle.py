"""Cache TTL and bounded storage must not require background ownership."""

import gc
import weakref

import pytest

import hierachain.core.cache as cache_module
from hierachain.core.cache import AdvancedCache


def test_discarded_caches_are_collectable_without_cleanup_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_thread(*args: object, **kwargs: object) -> None:
        raise AssertionError("A cache must not create a cleanup thread")

    monkeypatch.setattr(cache_module.threading, "Thread", unexpected_thread)
    references = [
        weakref.ref(AdvancedCache(eviction_policy=policy))
        for policy in ("ttl", "lru") * 10
    ]
    gc.collect()
    assert all(reference() is None for reference in references)


@pytest.mark.parametrize("policy", ["ttl", "lru", "lfu", "fifo"])
def test_expired_entries_do_not_evict_live_entries(
    monkeypatch: pytest.MonkeyPatch, policy: str
) -> None:
    now = [cache_module.time.time()]
    monkeypatch.setattr(cache_module.time, "time", lambda: now[0])
    cache = AdvancedCache(max_size=2, eviction_policy=policy)
    cache.set("live", "retained")
    cache.set("expired", "old", ttl=0)
    now[0] += 1
    cache.set("new", "value", ttl=5)
    assert cache.get("live") == "retained"
    assert cache.get("expired") is None
    now[0] += 6
    assert "new" not in cache
    assert cache.get_stats()["size"] == len(cache) == 1
    assert cache.get_keys() == ["live"]
