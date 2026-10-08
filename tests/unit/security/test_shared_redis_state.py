"""Live Redis regression coverage for shared brute-force attempt counts."""

import os
import secrets
import socket

import pytest
import redis

from hierachain.security.brute_force_protector import BruteForceProtector


@pytest.fixture
def redis_url() -> str:
    url = os.getenv("HRC_P2_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set HRC_P2_TEST_REDIS_URL for shared Redis state coverage")
    redis.from_url(url).ping()
    return url


@pytest.mark.integration
def test_redis_attempt_window_is_shared_across_protector_instances(redis_url: str) -> None:
    config = {
        "max_failures": 3,
        "lockout_duration": 60,
        "tracking_window": 300,
        "storage_backend": "redis",
        "redis_url": redis_url,
    }
    first = BruteForceProtector(config)
    second = BruteForceProtector(config)
    ip = f"test-ip-{secrets.token_hex(8)}"

    try:
        assert not first.record_failure(ip)
        assert not second.record_failure(ip)
        assert second.get_failure_count(ip) == 2
        assert first.record_failure(ip)
        assert second.is_locked_out(ip)
    finally:
        first.reset(ip)


def test_configured_redis_failure_does_not_fall_back_to_local_tracking() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    protector = BruteForceProtector({
        "storage_backend": "redis",
        "redis_url": f"redis://127.0.0.1:{port}/0",
    })

    with pytest.raises(redis.exceptions.RedisError):
        protector.record_failure("192.0.2.50")

    assert protector._tracker.get_count("192.0.2.50") == 0
